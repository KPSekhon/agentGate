// Package tokens verifies AgentGate grant tokens at the network edge.
//
// The Rust core holds the Ed25519 private key and is the only component that
// can mint a token. The proxy holds nothing but the matching public key, which
// is enough to prove a token is authentic and unexpired but useless for forging
// one. That asymmetry is the reason the edge can reject bad tokens at all: with
// a shared-secret scheme the proxy would need the signing key, and any
// compromise of the edge would hand an attacker the ability to mint grants.
package tokens

import (
	"context"
	"crypto/ed25519"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"strings"
	"sync"
	"time"
)

// tokenVersion is the only token format this verifier accepts. Pinning it here
// means the token cannot tell us which algorithm to use, which is the flaw that
// produced the well-known "alg: none" attacks against JWT.
const tokenVersion = "ag2"

var (
	ErrNoKey        = errors.New("no verification key available")
	ErrMalformed    = errors.New("malformed token")
	ErrBadVersion   = errors.New("unsupported token version")
	ErrBadSignature = errors.New("signature verification failed")
	ErrExpired      = errors.New("token expired")
)

// Claims mirrors the signed payload the Rust core mints.
type Claims struct {
	GrantID     string `json:"grant_id"`
	Requester   string `json:"requester"`
	SecretRef   string `json:"secret_ref"`
	Environment string `json:"environment"`
	Task        string `json:"task"`
	IssuedAt    int64  `json:"issued_at"`
	ExpiresAt   int64  `json:"expires_at"`
	MaxUses     uint32 `json:"max_uses"`
	PolicyName  string `json:"policy_name"`
	KeyID       string `json:"key_id"`
}

type publicKeyResponse struct {
	Algorithm string `json:"algorithm"`
	KeyID     string `json:"key_id"`
	PublicKey string `json:"public_key"`
}

// Verifier checks grant tokens against the core's published public key.
type Verifier struct {
	mu       sync.RWMutex
	key      ed25519.PublicKey
	keyID    string
	endpoint string
	client   *http.Client
	now      func() time.Time
}

func NewVerifier(backendURL string) *Verifier {
	return &Verifier{
		endpoint: strings.TrimSuffix(backendURL, "/") + "/publickey",
		client:   &http.Client{Timeout: 5 * time.Second},
		now:      time.Now,
	}
}

// SetKey installs a hex-encoded Ed25519 public key directly, for deployments
// that pin the key by configuration rather than fetching it.
func (v *Verifier) SetKey(hexKey, keyID string) error {
	raw, err := hex.DecodeString(hexKey)
	if err != nil {
		return fmt.Errorf("public key is not valid hex: %w", err)
	}
	if len(raw) != ed25519.PublicKeySize {
		return fmt.Errorf("expected %d-byte Ed25519 public key, got %d", ed25519.PublicKeySize, len(raw))
	}
	v.mu.Lock()
	defer v.mu.Unlock()
	v.key = ed25519.PublicKey(raw)
	v.keyID = keyID
	return nil
}

// HasKey reports whether a usable verification key is loaded.
func (v *Verifier) HasKey() bool {
	v.mu.RLock()
	defer v.mu.RUnlock()
	return v.key != nil
}

// KeyID returns the id of the loaded key, for logging.
func (v *Verifier) KeyID() string {
	v.mu.RLock()
	defer v.mu.RUnlock()
	return v.keyID
}

// Refresh fetches the current public key from the backend.
func (v *Verifier) Refresh(ctx context.Context) error {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, v.endpoint, nil)
	if err != nil {
		return err
	}
	resp, err := v.client.Do(req)
	if err != nil {
		return fmt.Errorf("fetching %s: %w", v.endpoint, err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("%s returned %d", v.endpoint, resp.StatusCode)
	}

	var body publicKeyResponse
	if err := json.NewDecoder(resp.Body).Decode(&body); err != nil {
		return fmt.Errorf("decoding public key response: %w", err)
	}
	if body.Algorithm != "" && body.Algorithm != "Ed25519" {
		return fmt.Errorf("unsupported signing algorithm %q", body.Algorithm)
	}
	return v.SetKey(body.PublicKey, body.KeyID)
}

// Verify checks a token's version, signature, and expiry, returning its claims.
//
// It deliberately stops there. Use count and revocation are mutable facts that
// a signature cannot capture, so the backend remains the authority on those;
// this is a cheap filter that drops forged and stale tokens before they reach
// the application or its database.
func (v *Verifier) Verify(token string) (*Claims, error) {
	v.mu.RLock()
	key := v.key
	v.mu.RUnlock()
	if key == nil {
		return nil, ErrNoKey
	}

	parts := strings.SplitN(token, ".", 3)
	if len(parts) != 3 {
		return nil, fmt.Errorf("%w: expected 3 segments, got %d", ErrMalformed, len(parts))
	}
	if parts[0] != tokenVersion {
		return nil, fmt.Errorf("%w: %q", ErrBadVersion, parts[0])
	}

	payload, err := hex.DecodeString(parts[1])
	if err != nil {
		return nil, fmt.Errorf("%w: payload is not valid hex", ErrMalformed)
	}
	sig, err := hex.DecodeString(parts[2])
	if err != nil {
		return nil, fmt.Errorf("%w: signature is not valid hex", ErrMalformed)
	}
	if len(sig) != ed25519.SignatureSize {
		return nil, fmt.Errorf("%w: expected %d-byte signature, got %d", ErrMalformed, ed25519.SignatureSize, len(sig))
	}

	// Verify before parsing. The payload is attacker-controlled until the
	// signature says otherwise, so we never feed it to the JSON decoder first.
	if !ed25519.Verify(key, payload, sig) {
		return nil, ErrBadSignature
	}

	var claims Claims
	if err := json.Unmarshal(payload, &claims); err != nil {
		return nil, fmt.Errorf("%w: payload is not valid JSON", ErrMalformed)
	}
	if claims.ExpiresAt > 0 && v.now().Unix() > claims.ExpiresAt {
		return nil, ErrExpired
	}
	return &claims, nil
}

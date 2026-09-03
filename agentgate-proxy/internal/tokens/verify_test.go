package tokens

import (
	"context"
	"crypto/ed25519"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

func mint(t *testing.T, priv ed25519.PrivateKey, claims Claims) string {
	t.Helper()
	payload, err := json.Marshal(claims)
	if err != nil {
		t.Fatalf("marshal claims: %v", err)
	}
	sig := ed25519.Sign(priv, payload)
	return fmt.Sprintf("ag2.%s.%s", hex.EncodeToString(payload), hex.EncodeToString(sig))
}

func validClaims() Claims {
	return Claims{
		GrantID:     "grant-1",
		Requester:   "agent:github-actions",
		SecretRef:   "op://ci-vault/deploy-key/credential",
		Environment: "ci",
		Task:        "deploy",
		IssuedAt:    time.Now().Unix(),
		ExpiresAt:   time.Now().Add(5 * time.Minute).Unix(),
		MaxUses:     1,
		PolicyName:  "ci-deploy-access",
		KeyID:       "abc123",
	}
}

func newTestVerifier(t *testing.T) (*Verifier, ed25519.PrivateKey) {
	t.Helper()
	pub, priv, err := ed25519.GenerateKey(nil)
	if err != nil {
		t.Fatalf("generate key: %v", err)
	}
	v := NewVerifier("http://backend.invalid")
	if err := v.SetKey(hex.EncodeToString(pub), "test-key"); err != nil {
		t.Fatalf("set key: %v", err)
	}
	return v, priv
}

func TestVerifyAcceptsValidToken(t *testing.T) {
	v, priv := newTestVerifier(t)
	claims, err := v.Verify(mint(t, priv, validClaims()))
	if err != nil {
		t.Fatalf("expected valid token, got %v", err)
	}
	if claims.Requester != "agent:github-actions" {
		t.Errorf("requester = %q", claims.Requester)
	}
	if claims.MaxUses != 1 {
		t.Errorf("max_uses = %d", claims.MaxUses)
	}
}

func TestVerifyRejectsTamperedSignature(t *testing.T) {
	v, priv := newTestVerifier(t)
	token := mint(t, priv, validClaims())

	// Flip a bit in the signature.
	parts := splitToken(token)
	sig, _ := hex.DecodeString(parts[2])
	sig[0] ^= 0xff
	tampered := fmt.Sprintf("ag2.%s.%s", parts[1], hex.EncodeToString(sig))

	if _, err := v.Verify(tampered); !errors.Is(err, ErrBadSignature) {
		t.Fatalf("expected ErrBadSignature, got %v", err)
	}
}

func TestVerifyRejectsTamperedPayload(t *testing.T) {
	v, priv := newTestVerifier(t)
	parts := splitToken(mint(t, priv, validClaims()))
	payload, _ := hex.DecodeString(parts[1])
	payload[len(payload)/2] ^= 0x01
	tampered := fmt.Sprintf("ag2.%s.%s", hex.EncodeToString(payload), parts[2])

	if _, err := v.Verify(tampered); !errors.Is(err, ErrBadSignature) {
		t.Fatalf("expected ErrBadSignature, got %v", err)
	}
}

func TestVerifyRejectsWrongKey(t *testing.T) {
	v, _ := newTestVerifier(t)
	_, otherPriv, _ := ed25519.GenerateKey(nil)
	if _, err := v.Verify(mint(t, otherPriv, validClaims())); !errors.Is(err, ErrBadSignature) {
		t.Fatalf("expected ErrBadSignature, got %v", err)
	}
}

func TestVerifyRejectsExpiredToken(t *testing.T) {
	v, priv := newTestVerifier(t)
	claims := validClaims()
	claims.ExpiresAt = time.Now().Add(-time.Hour).Unix()
	if _, err := v.Verify(mint(t, priv, claims)); !errors.Is(err, ErrExpired) {
		t.Fatalf("expected ErrExpired, got %v", err)
	}
}

func TestVerifyRejectsUnsupportedVersion(t *testing.T) {
	v, priv := newTestVerifier(t)
	parts := splitToken(mint(t, priv, validClaims()))
	legacy := fmt.Sprintf("ag1.%s.%s", parts[1], parts[2])
	if _, err := v.Verify(legacy); !errors.Is(err, ErrBadVersion) {
		t.Fatalf("expected ErrBadVersion, got %v", err)
	}
}

func TestVerifyRejectsMalformedTokens(t *testing.T) {
	v, _ := newTestVerifier(t)
	for _, token := range []string{"", "nonsense", "ag2.onlytwo", "ag2.zz.zz", "ag2..", "...."} {
		if _, err := v.Verify(token); err == nil {
			t.Errorf("expected rejection for %q", token)
		}
	}
}

func TestVerifyWithoutKeyFails(t *testing.T) {
	v := NewVerifier("http://backend.invalid")
	if _, err := v.Verify("ag2.aa.bb"); !errors.Is(err, ErrNoKey) {
		t.Fatalf("expected ErrNoKey, got %v", err)
	}
}

func TestRefreshLoadsKeyFromBackend(t *testing.T) {
	pub, priv, _ := ed25519.GenerateKey(nil)
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/publickey" {
			w.WriteHeader(http.StatusNotFound)
			return
		}
		json.NewEncoder(w).Encode(publicKeyResponse{
			Algorithm: "Ed25519",
			KeyID:     "from-backend",
			PublicKey: hex.EncodeToString(pub),
		})
	}))
	defer srv.Close()

	v := NewVerifier(srv.URL)
	if v.HasKey() {
		t.Fatal("verifier should start without a key")
	}
	if err := v.Refresh(context.Background()); err != nil {
		t.Fatalf("refresh: %v", err)
	}
	if v.KeyID() != "from-backend" {
		t.Errorf("key_id = %q", v.KeyID())
	}
	if _, err := v.Verify(mint(t, priv, validClaims())); err != nil {
		t.Fatalf("token minted with the fetched key should verify: %v", err)
	}
}

func TestSetKeyRejectsWrongSize(t *testing.T) {
	v := NewVerifier("http://backend.invalid")
	if err := v.SetKey(hex.EncodeToString([]byte("too-short")), "k"); err == nil {
		t.Fatal("expected rejection of undersized key")
	}
	if err := v.SetKey("not-hex", "k"); err == nil {
		t.Fatal("expected rejection of non-hex key")
	}
}

func splitToken(token string) [3]string {
	var out [3]string
	i, start := 0, 0
	for pos := 0; pos < len(token) && i < 2; pos++ {
		if token[pos] == '.' {
			out[i] = token[start:pos]
			i++
			start = pos + 1
		}
	}
	out[2] = token[start:]
	return out
}

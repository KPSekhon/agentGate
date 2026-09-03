package middleware

import (
	"crypto/ed25519"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/KPSekhon/agentgate/agentgate-proxy/internal/tokens"
)

func testVerifier(t *testing.T) (*tokens.Verifier, ed25519.PrivateKey) {
	t.Helper()
	pub, priv, err := ed25519.GenerateKey(nil)
	if err != nil {
		t.Fatalf("generate key: %v", err)
	}
	v := tokens.NewVerifier("http://backend.invalid")
	if err := v.SetKey(hex.EncodeToString(pub), "test-key"); err != nil {
		t.Fatalf("set key: %v", err)
	}
	return v, priv
}

func mintToken(t *testing.T, priv ed25519.PrivateKey, expires time.Time) string {
	t.Helper()
	payload, err := json.Marshal(tokens.Claims{
		GrantID:   "grant-1",
		Requester: "agent:github-actions",
		ExpiresAt: expires.Unix(),
		MaxUses:   1,
	})
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	sig := ed25519.Sign(priv, payload)
	return fmt.Sprintf("ag2.%s.%s", hex.EncodeToString(payload), hex.EncodeToString(sig))
}

// spy records whether the request reached the backend, and what body it saw.
type spy struct {
	called bool
	body   string
	header string
}

func (s *spy) handler() http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		s.called = true
		b, _ := io.ReadAll(r.Body)
		s.body = string(b)
		s.header = r.Header.Get("X-Grant-Requester")
		w.WriteHeader(http.StatusOK)
	})
}

func exchangeRequest(body string) *http.Request {
	req := httptest.NewRequest(http.MethodPost, "/agent/exchange", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	return req
}

func TestValidTokenReachesBackend(t *testing.T) {
	v, priv := testVerifier(t)
	backend := &spy{}
	h := NewGrantVerifier(v).Middleware(backend.handler())

	body := fmt.Sprintf(`{"grant_id":%q}`, mintToken(t, priv, time.Now().Add(time.Hour)))
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, exchangeRequest(body))

	if !backend.called {
		t.Fatal("valid token should reach the backend")
	}
	if rec.Code != http.StatusOK {
		t.Errorf("status = %d", rec.Code)
	}
	// The proxy read the body to inspect it, so the backend must still get it.
	if backend.body != body {
		t.Errorf("backend saw a different body:\n got: %s\nwant: %s", backend.body, body)
	}
	if backend.header != "agent:github-actions" {
		t.Errorf("verified requester header = %q", backend.header)
	}
}

func TestForgedTokenIsRejectedAtEdge(t *testing.T) {
	v, _ := testVerifier(t)
	_, attackerKey, _ := ed25519.GenerateKey(nil)
	backend := &spy{}
	h := NewGrantVerifier(v).Middleware(backend.handler())

	body := fmt.Sprintf(`{"grant_id":%q}`, mintToken(t, attackerKey, time.Now().Add(time.Hour)))
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, exchangeRequest(body))

	if backend.called {
		t.Fatal("a forged token must never reach the backend")
	}
	if rec.Code != http.StatusUnauthorized {
		t.Errorf("status = %d, want 401", rec.Code)
	}
}

func TestExpiredTokenIsRejectedAtEdge(t *testing.T) {
	v, priv := testVerifier(t)
	backend := &spy{}
	h := NewGrantVerifier(v).Middleware(backend.handler())

	body := fmt.Sprintf(`{"grant_id":%q}`, mintToken(t, priv, time.Now().Add(-time.Hour)))
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, exchangeRequest(body))

	if backend.called {
		t.Fatal("an expired token must never reach the backend")
	}
	if rec.Code != http.StatusUnauthorized {
		t.Errorf("status = %d, want 401", rec.Code)
	}
}

func TestSpoofedIdentityHeaderIsStripped(t *testing.T) {
	v, _ := testVerifier(t)
	backend := &spy{}
	h := NewGrantVerifier(v).Middleware(backend.handler())

	req := httptest.NewRequest(http.MethodGet, "/policies", nil)
	req.Header.Set("X-Grant-Requester", "agent:admin")
	h.ServeHTTP(httptest.NewRecorder(), req)

	if backend.header != "" {
		t.Errorf("client-supplied identity header must be stripped, got %q", backend.header)
	}
}

func TestOpaqueDemoIdPassesThrough(t *testing.T) {
	v, _ := testVerifier(t)
	backend := &spy{}
	h := NewGrantVerifier(v).Middleware(backend.handler())

	// Demo mode issues plain UUIDs, which the edge cannot check and must not block.
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, exchangeRequest(`{"grant_id":"a4dbaf9e-42fa-414c-9a70-6cd65bc95fd3"}`))

	if !backend.called {
		t.Fatal("unsigned demo ids should pass through to the backend")
	}
}

func TestOtherRoutesAreUntouched(t *testing.T) {
	v, _ := testVerifier(t)
	backend := &spy{}
	h := NewGrantVerifier(v).Middleware(backend.handler())

	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, httptest.NewRequest(http.MethodPost, "/agent/request-secret", strings.NewReader(`{"x":1}`)))

	if !backend.called {
		t.Fatal("non-exchange routes must pass through untouched")
	}
}

func TestVerificationIsSkippedWithoutAKey(t *testing.T) {
	v := tokens.NewVerifier("http://backend.invalid") // no key loaded
	backend := &spy{}
	h := NewGrantVerifier(v).Middleware(backend.handler())

	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, exchangeRequest(`{"grant_id":"ag2.aa.bb"}`))

	// Fail open at the edge: the backend still verifies independently.
	if !backend.called {
		t.Fatal("without a key the edge should defer to the backend")
	}
}

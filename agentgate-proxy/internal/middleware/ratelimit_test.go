package middleware

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestRateLimiterAllow(t *testing.T) {
	rl := NewRateLimiter(5, 3) // 5/min, burst of 3

	// Burst of 3 should succeed
	for i := 0; i < 3; i++ {
		if !rl.Allow("agent:test") {
			t.Fatalf("request %d should be allowed within burst", i)
		}
	}

	// 4th should be denied (burst exhausted, not enough time to refill)
	if rl.Allow("agent:test") {
		t.Fatal("request after burst should be denied")
	}
}

func TestRateLimiterDifferentKeys(t *testing.T) {
	rl := NewRateLimiter(5, 2)

	if !rl.Allow("agent:alice") {
		t.Fatal("alice should be allowed")
	}
	if !rl.Allow("agent:bob") {
		t.Fatal("bob should be allowed independently")
	}
}

func TestRateLimiterMiddleware429(t *testing.T) {
	rl := NewRateLimiter(1, 1)

	backend := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	})

	handler := rl.Middleware(backend)

	// First request: OK
	req := httptest.NewRequest("POST", "/agent/request-secret", nil)
	req.Header.Set("X-Agent-Name", "fast-bot")
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", rec.Code)
	}

	// Second request: rate limited
	rec2 := httptest.NewRecorder()
	handler.ServeHTTP(rec2, req)

	if rec2.Code != http.StatusTooManyRequests {
		t.Fatalf("expected 429, got %d", rec2.Code)
	}

	var body map[string]string
	json.NewDecoder(rec2.Body).Decode(&body)
	if body["error"] != "rate_limited" {
		t.Fatalf("expected rate_limited error, got %s", body["error"])
	}
}

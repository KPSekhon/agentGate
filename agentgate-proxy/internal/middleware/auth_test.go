package middleware

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestAuthRejectsNoHeader(t *testing.T) {
	auth := NewAuth("secret-token")
	backend := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	})

	handler := auth.Middleware(backend)
	req := httptest.NewRequest("POST", "/agent/request-secret", nil)
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)

	if rec.Code != http.StatusUnauthorized {
		t.Fatalf("expected 401, got %d", rec.Code)
	}
}

func TestAuthRejectsWrongToken(t *testing.T) {
	auth := NewAuth("correct-token")
	backend := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	})

	handler := auth.Middleware(backend)
	req := httptest.NewRequest("POST", "/agent/request-secret", nil)
	req.Header.Set("Authorization", "Bearer wrong-token")
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)

	if rec.Code != http.StatusUnauthorized {
		t.Fatalf("expected 401, got %d", rec.Code)
	}

	var body map[string]string
	json.NewDecoder(rec.Body).Decode(&body)
	if body["error"] != "unauthorized" {
		t.Fatalf("expected unauthorized, got %s", body["error"])
	}
}

func TestAuthAllowsCorrectToken(t *testing.T) {
	auth := NewAuth("my-secret")
	backend := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Write([]byte("OK"))
	})

	handler := auth.Middleware(backend)
	req := httptest.NewRequest("POST", "/agent/request-secret", nil)
	req.Header.Set("Authorization", "Bearer my-secret")
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", rec.Code)
	}
}

func TestAuthSkipsHealthEndpoints(t *testing.T) {
	auth := NewAuth("secret")
	backend := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	})

	handler := auth.Middleware(backend)

	for _, path := range []string{"/healthz", "/readyz", "/metrics"} {
		req := httptest.NewRequest("GET", path, nil)
		rec := httptest.NewRecorder()
		handler.ServeHTTP(rec, req)

		if rec.Code != http.StatusOK {
			t.Fatalf("health endpoint %s should bypass auth, got %d", path, rec.Code)
		}
	}
}

func TestAuthDisabledWithEmptyToken(t *testing.T) {
	auth := NewAuth("")
	backend := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	})

	handler := auth.Middleware(backend)
	req := httptest.NewRequest("POST", "/agent/request-secret", nil)
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200 with no auth configured, got %d", rec.Code)
	}
}

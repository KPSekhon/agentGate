package middleware

import (
	"encoding/json"
	"log/slog"
	"net/http"
	"sync"
	"time"
)

type visitor struct {
	tokens    float64
	maxTokens float64
	refillRate float64 // tokens per second
	lastSeen  time.Time
}

type RateLimiter struct {
	mu       sync.Mutex
	visitors map[string]*visitor
	limit    int
	burst    int
}

func NewRateLimiter(perMinute, burst int) *RateLimiter {
	rl := &RateLimiter{
		visitors: make(map[string]*visitor),
		limit:    perMinute,
		burst:    burst,
	}

	go rl.cleanup()
	return rl
}

func (rl *RateLimiter) Allow(key string) bool {
	rl.mu.Lock()
	defer rl.mu.Unlock()

	now := time.Now()
	v, exists := rl.visitors[key]
	if !exists {
		v = &visitor{
			tokens:    float64(rl.burst),
			maxTokens: float64(rl.burst),
			refillRate: float64(rl.limit) / 60.0,
			lastSeen:  now,
		}
		rl.visitors[key] = v
	}

	elapsed := now.Sub(v.lastSeen).Seconds()
	v.tokens += elapsed * v.refillRate
	if v.tokens > v.maxTokens {
		v.tokens = v.maxTokens
	}
	v.lastSeen = now

	if v.tokens < 1 {
		return false
	}
	v.tokens--
	return true
}

func (rl *RateLimiter) cleanup() {
	ticker := time.NewTicker(5 * time.Minute)
	defer ticker.Stop()

	for range ticker.C {
		rl.mu.Lock()
		cutoff := time.Now().Add(-10 * time.Minute)
		for key, v := range rl.visitors {
			if v.lastSeen.Before(cutoff) {
				delete(rl.visitors, key)
			}
		}
		rl.mu.Unlock()
	}
}

func (rl *RateLimiter) Middleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		key := extractAgentKey(r)

		if !rl.Allow(key) {
			slog.Warn("rate limited", "agent", key, "path", r.URL.Path)
			w.Header().Set("Content-Type", "application/json")
			w.Header().Set("Retry-After", "10")
			w.WriteHeader(http.StatusTooManyRequests)
			json.NewEncoder(w).Encode(map[string]string{
				"error":  "rate_limited",
				"reason": "Too many requests. Slow down.",
			})
			return
		}

		next.ServeHTTP(w, r)
	})
}

func extractAgentKey(r *http.Request) string {
	if agent := r.Header.Get("X-Agent-Name"); agent != "" {
		return "agent:" + agent
	}
	return r.RemoteAddr
}

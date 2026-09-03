package config

import (
	"fmt"
	"os"
	"strconv"
	"time"
)

type Config struct {
	ListenAddr      string
	BackendURL      string
	RateLimitPerMin int
	RateLimitBurst  int
	TLSCertFile     string
	TLSKeyFile      string
	TLSClientCA     string
	AgentToken      string
	PublicKeyHex    string
	ReadTimeout     time.Duration
	WriteTimeout    time.Duration
	ShutdownTimeout time.Duration
}

func Load() (*Config, error) {
	cfg := &Config{
		ListenAddr:      envOr("AGENTGATE_PROXY_ADDR", ":8443"),
		BackendURL:      envOr("AGENTGATE_BACKEND_URL", "http://localhost:8000"),
		RateLimitPerMin: envInt("AGENTGATE_RATE_LIMIT", 60),
		RateLimitBurst:  envInt("AGENTGATE_RATE_BURST", 10),
		TLSCertFile:     os.Getenv("AGENTGATE_TLS_CERT"),
		TLSKeyFile:      os.Getenv("AGENTGATE_TLS_KEY"),
		TLSClientCA:     os.Getenv("AGENTGATE_TLS_CLIENT_CA"),
		AgentToken:      envOr("AGENTGATE_AGENT_TOKEN", ""),
		PublicKeyHex:    os.Getenv("AGENTGATE_PUBLIC_KEY"),
		ReadTimeout:     10 * time.Second,
		WriteTimeout:    10 * time.Second,
		ShutdownTimeout: 30 * time.Second,
	}

	if cfg.BackendURL == "" {
		return nil, fmt.Errorf("AGENTGATE_BACKEND_URL is required")
	}

	return cfg, nil
}

func envOr(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func envInt(key string, fallback int) int {
	v := os.Getenv(key)
	if v == "" {
		return fallback
	}
	n, err := strconv.Atoi(v)
	if err != nil {
		return fallback
	}
	return n
}

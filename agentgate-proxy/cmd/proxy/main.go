package main

import (
	"context"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/KPSekhon/agentgate/agentgate-proxy/internal/config"
	"github.com/KPSekhon/agentgate/agentgate-proxy/internal/handler"
	"github.com/KPSekhon/agentgate/agentgate-proxy/internal/health"
	"github.com/KPSekhon/agentgate/agentgate-proxy/internal/middleware"
	agTLS "github.com/KPSekhon/agentgate/agentgate-proxy/internal/tls"
	"github.com/KPSekhon/agentgate/agentgate-proxy/internal/tokens"
)

func main() {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelInfo}))
	slog.SetDefault(logger)

	cfg, err := config.Load()
	if err != nil {
		slog.Error("config load failed", "err", err)
		os.Exit(1)
	}

	proxy, err := handler.NewReverseProxy(cfg.BackendURL)
	if err != nil {
		slog.Error("proxy setup failed", "err", err)
		os.Exit(1)
	}

	checker := health.NewChecker(cfg.BackendURL)
	rateLimiter := middleware.NewRateLimiter(cfg.RateLimitPerMin, cfg.RateLimitBurst)
	auth := middleware.NewAuth(cfg.AgentToken)

	// The proxy verifies grant tokens using only the core's public key, which it
	// either has pinned by configuration or fetches from the backend. It never
	// holds the signing key, so compromising the edge does not let an attacker
	// mint grants.
	verifier := tokens.NewVerifier(cfg.BackendURL)
	if cfg.PublicKeyHex != "" {
		if err := verifier.SetKey(cfg.PublicKeyHex, "pinned"); err != nil {
			slog.Error("invalid AGENTGATE_PUBLIC_KEY", "err", err)
			os.Exit(1)
		}
		slog.Info("token verification key pinned from configuration")
	} else {
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		if err := verifier.Refresh(ctx); err != nil {
			slog.Warn("could not load token verification key, edge verification is idle until it appears", "err", err)
		} else {
			slog.Info("token verification key loaded", "key_id", verifier.KeyID())
		}
		cancel()

		// Re-fetch periodically so a key rotation is picked up without a restart.
		go func() {
			for range time.Tick(5 * time.Minute) {
				ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
				if err := verifier.Refresh(ctx); err != nil {
					slog.Warn("public key refresh failed", "err", err)
				}
				cancel()
			}
		}()
	}
	grantVerifier := middleware.NewGrantVerifier(verifier)

	mux := http.NewServeMux()
	mux.HandleFunc("/healthz", checker.LiveHandler)
	mux.HandleFunc("/readyz", checker.ReadyHandler)
	mux.HandleFunc("/metrics", checker.MetricsHandler)
	mux.Handle("/", proxy)

	var chain http.Handler = mux
	chain = grantVerifier.Middleware(chain)
	chain = auth.Middleware(chain)
	chain = rateLimiter.Middleware(chain)
	chain = middleware.Logging(chain)

	tlsCfg := &agTLS.Config{
		CertFile: cfg.TLSCertFile,
		KeyFile:  cfg.TLSKeyFile,
		ClientCA: cfg.TLSClientCA,
	}

	srv := &http.Server{
		Addr:         cfg.ListenAddr,
		Handler:      chain,
		ReadTimeout:  cfg.ReadTimeout,
		WriteTimeout: cfg.WriteTimeout,
	}

	if tlsCfg.Enabled() {
		tc, err := tlsCfg.Build()
		if err != nil {
			slog.Error("TLS setup failed", "err", err)
			os.Exit(1)
		}
		srv.TLSConfig = tc

		mode := "TLS"
		if tlsCfg.MutualTLSEnabled() {
			mode = "mTLS"
		}
		slog.Info("starting proxy", "addr", cfg.ListenAddr, "mode", mode, "backend", cfg.BackendURL)
	} else {
		slog.Info("starting proxy", "addr", cfg.ListenAddr, "mode", "plaintext", "backend", cfg.BackendURL)
	}

	errCh := make(chan error, 1)
	go func() {
		if tlsCfg.Enabled() {
			errCh <- srv.ListenAndServeTLS("", "")
		} else {
			errCh <- srv.ListenAndServe()
		}
	}()

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)

	select {
	case sig := <-quit:
		slog.Info("shutting down", "signal", sig.String())
	case err := <-errCh:
		if err != nil && err != http.ErrServerClosed {
			slog.Error("server failed", "err", err)
			os.Exit(1)
		}
	}

	ctx, cancel := context.WithTimeout(context.Background(), cfg.ShutdownTimeout)
	defer cancel()

	if err := srv.Shutdown(ctx); err != nil {
		slog.Error("graceful shutdown failed", "err", err)
		os.Exit(1)
	}
	slog.Info("proxy stopped")
}

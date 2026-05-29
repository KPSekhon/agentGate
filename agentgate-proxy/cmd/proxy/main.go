package main

import (
	"context"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"

	"github.com/KPSekhon/agentgate/agentgate-proxy/internal/config"
	"github.com/KPSekhon/agentgate/agentgate-proxy/internal/handler"
	"github.com/KPSekhon/agentgate/agentgate-proxy/internal/health"
	"github.com/KPSekhon/agentgate/agentgate-proxy/internal/middleware"
	agTLS "github.com/KPSekhon/agentgate/agentgate-proxy/internal/tls"
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

	mux := http.NewServeMux()
	mux.HandleFunc("/healthz", checker.LiveHandler)
	mux.HandleFunc("/readyz", checker.ReadyHandler)
	mux.HandleFunc("/metrics", checker.MetricsHandler)
	mux.Handle("/", proxy)

	var chain http.Handler = mux
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

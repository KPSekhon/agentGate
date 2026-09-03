package health

import (
	"encoding/json"
	"fmt"
	"net/http"
	"sync/atomic"
	"time"
)

type Checker struct {
	backendURL string
	ready      atomic.Bool
	lastCheck  atomic.Value // time.Time
	client     *http.Client
}

func NewChecker(backendURL string) *Checker {
	c := &Checker{
		backendURL: backendURL,
		client:     &http.Client{Timeout: 5 * time.Second},
	}
	c.ready.Store(false)
	c.lastCheck.Store(time.Time{})

	go c.loop()
	return c
}

func (c *Checker) loop() {
	ticker := time.NewTicker(10 * time.Second)
	defer ticker.Stop()

	c.check()
	for range ticker.C {
		c.check()
	}
}

func (c *Checker) check() {
	resp, err := c.client.Get(c.backendURL + "/docs")
	if err != nil {
		c.ready.Store(false)
		return
	}
	resp.Body.Close()
	c.ready.Store(resp.StatusCode < 500)
	c.lastCheck.Store(time.Now())
}

func (c *Checker) LiveHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{
		"status": "alive",
	})
}

func (c *Checker) ReadyHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")

	if !c.ready.Load() {
		w.WriteHeader(http.StatusServiceUnavailable)
		json.NewEncoder(w).Encode(map[string]string{
			"status": "not_ready",
			"reason": "backend health check failed",
		})
		return
	}

	last := c.lastCheck.Load().(time.Time)
	json.NewEncoder(w).Encode(map[string]string{
		"status":     "ready",
		"last_check": last.Format(time.RFC3339),
	})
}

func (c *Checker) MetricsHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "text/plain")
	ready := 0
	if c.ready.Load() {
		ready = 1
	}
	fmt.Fprintf(w, "# HELP agentgate_proxy_backend_up Whether the backend is reachable\n")
	fmt.Fprintf(w, "# TYPE agentgate_proxy_backend_up gauge\n")
	fmt.Fprintf(w, "agentgate_proxy_backend_up %d\n", ready)
}

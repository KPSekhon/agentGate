package handler

import (
	"io"
	"log/slog"
	"net/http"
	"net/url"
	"strings"
	"time"
)

type ReverseProxy struct {
	backendURL *url.URL
	client     *http.Client
}

func NewReverseProxy(backendURL string) (*ReverseProxy, error) {
	u, err := url.Parse(backendURL)
	if err != nil {
		return nil, err
	}
	return &ReverseProxy{
		backendURL: u,
		client: &http.Client{
			Timeout: 30 * time.Second,
			CheckRedirect: func(req *http.Request, via []*http.Request) error {
				return http.ErrUseLastResponse
			},
		},
	}, nil
}

func (rp *ReverseProxy) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	target := *rp.backendURL
	target.Path = singleJoiningSlash(target.Path, r.URL.Path)
	target.RawQuery = r.URL.RawQuery

	proxyReq, err := http.NewRequestWithContext(r.Context(), r.Method, target.String(), r.Body)
	if err != nil {
		slog.Error("proxy request creation failed", "err", err)
		http.Error(w, `{"error":"proxy_error","reason":"failed to create upstream request"}`, http.StatusBadGateway)
		return
	}

	for key, values := range r.Header {
		for _, value := range values {
			proxyReq.Header.Add(key, value)
		}
	}
	proxyReq.Header.Set("X-Forwarded-For", r.RemoteAddr)
	proxyReq.Header.Set("X-Forwarded-Proto", scheme(r))

	if r.TLS != nil && len(r.TLS.PeerCertificates) > 0 {
		cn := r.TLS.PeerCertificates[0].Subject.CommonName
		proxyReq.Header.Set("X-Client-CN", cn)
	}

	resp, err := rp.client.Do(proxyReq)
	if err != nil {
		slog.Error("upstream request failed", "err", err, "url", target.String())
		http.Error(w, `{"error":"upstream_error","reason":"backend unreachable"}`, http.StatusBadGateway)
		return
	}
	defer resp.Body.Close()

	for key, values := range resp.Header {
		for _, value := range values {
			w.Header().Add(key, value)
		}
	}
	w.WriteHeader(resp.StatusCode)
	io.Copy(w, resp.Body)
}

func singleJoiningSlash(a, b string) string {
	aslash := strings.HasSuffix(a, "/")
	bslash := strings.HasPrefix(b, "/")
	switch {
	case aslash && bslash:
		return a + b[1:]
	case !aslash && !bslash:
		return a + "/" + b
	}
	return a + b
}

func scheme(r *http.Request) string {
	if r.TLS != nil {
		return "https"
	}
	return "http"
}

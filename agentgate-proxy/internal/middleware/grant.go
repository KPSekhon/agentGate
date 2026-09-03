package middleware

import (
	"bytes"
	"encoding/json"
	"io"
	"log/slog"
	"net/http"
	"strings"

	"github.com/KPSekhon/agentgate/agentgate-proxy/internal/tokens"
)

// maxExchangeBody caps how much of an exchange request we buffer in order to
// read the grant token. An exchange body is a few hundred bytes, so anything
// larger is either a mistake or an attempt to make the proxy allocate.
const maxExchangeBody = 64 << 10

// grantHeader carries the verified requester identity to the backend. It is
// stripped from every inbound request first, so a client cannot forge it.
const grantHeader = "X-Grant-Requester"

// GrantVerifier rejects grant tokens that fail signature or expiry checks
// before they reach the backend.
//
// This is defense in depth, not the only gate. The backend still verifies every
// token and remains the sole authority on use count and revocation, which are
// mutable facts a signature cannot express. What the edge adds is that a forged
// or expired token never touches the application or its database at all.
type GrantVerifier struct {
	verifier *tokens.Verifier
}

func NewGrantVerifier(v *tokens.Verifier) *GrantVerifier {
	return &GrantVerifier{verifier: v}
}

func (g *GrantVerifier) Middleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Never let a caller supply their own identity header.
		r.Header.Del(grantHeader)

		if r.Method != http.MethodPost || !strings.HasSuffix(r.URL.Path, "/agent/exchange") {
			next.ServeHTTP(w, r)
			return
		}

		// Without a key we cannot check anything. Pass through rather than fail
		// closed: the backend verifies independently, so refusing here would
		// take the whole system down for a problem the edge cannot fix.
		if !g.verifier.HasKey() {
			next.ServeHTTP(w, r)
			return
		}

		body, err := io.ReadAll(io.LimitReader(r.Body, maxExchangeBody))
		r.Body.Close()
		if err != nil {
			unauthorized(w, "could not read request body")
			return
		}
		// The proxy consumed the body, so hand a fresh reader downstream.
		restore := func() {
			r.Body = io.NopCloser(bytes.NewReader(body))
			r.ContentLength = int64(len(body))
		}

		var payload struct {
			GrantID string `json:"grant_id"`
		}
		if err := json.Unmarshal(body, &payload); err != nil || payload.GrantID == "" {
			// Nothing we can inspect. Let the backend return its own error so
			// the proxy does not become a second source of truth on validation.
			restore()
			next.ServeHTTP(w, r)
			return
		}

		// Demo mode issues opaque database ids rather than signed tokens.
		if !strings.HasPrefix(payload.GrantID, "ag2.") {
			restore()
			next.ServeHTTP(w, r)
			return
		}

		claims, err := g.verifier.Verify(payload.GrantID)
		if err != nil {
			slog.Warn("grant token rejected at edge",
				"remote", r.RemoteAddr,
				"path", r.URL.Path,
				"err", err.Error(),
			)
			unauthorized(w, "grant token failed verification: "+err.Error())
			return
		}

		slog.Info("grant token verified at edge",
			"requester", claims.Requester,
			"policy", claims.PolicyName,
			"key_id", claims.KeyID,
		)
		r.Header.Set(grantHeader, claims.Requester)
		restore()
		next.ServeHTTP(w, r)
	})
}

# 0004. Verify grant tokens at the Go proxy

Status: Accepted

## Context

Before this change a forged grant token travelled the full depth of the system
before anything rejected it. It passed the proxy, reached the Python backend,
triggered a gRPC call to the core, and only then failed verification. An
attacker with a token generator could make every forged request consume work
across all three services.

Moving to Ed25519 (ADR 0001) made a better option available: the proxy can check
signatures using only the public key, without being trusted to mint anything.

## Decision

The Go proxy verifies grant tokens on the exchange path. It fetches the public
key of the core from the /publickey endpoint on the backend at startup,
refreshes it every five minutes so a key rotation is picked up without a
restart, and can alternatively have a key pinned by configuration.

On a request to /agent/exchange the proxy reads the grant token from the body,
verifies the signature and the signed expiry, and returns 401 immediately if
either fails. Verified requests continue to the backend with the requester
identity attached as X-Grant-Requester. That header is stripped from every
inbound request first, so a client cannot supply its own.

Deliberately out of scope at the edge: use count and revocation. Those are
mutable state owned by the backend (ADR 0002), and duplicating them in the proxy
would recreate the split brain that decision exists to avoid.

## Consequences

- Forged and expired tokens are dropped at the edge and never reach the
  application or its database.
- The proxy holds no secret capable of minting tokens, so compromising the most
  exposed component in the system does not yield the ability to forge grants.
- Verification is defense in depth, not the only gate. The backend still
  verifies every token independently, which is why the proxy fails open when no
  public key is available: refusing traffic there would take the system down for
  a problem the edge cannot fix, while the backend keeps rejecting bad tokens
  correctly.
- The proxy must buffer the exchange request body to read the token, capped at
  64 KB so a large body cannot force unbounded allocation.

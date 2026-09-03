# 0001. Sign grant tokens with Ed25519 instead of HMAC-SHA256

Status: Accepted

## Context

A grant token is a capability: whoever holds a valid one can exchange it for a
secret. It therefore has to be unforgeable, and every component that accepts a
token has to be able to check it.

The first implementation signed tokens with HMAC-SHA256. HMAC is symmetric, so
the same key both produces and checks a signature. That worked while the Rust
core was the only component touching tokens, but it does not survive contact
with a second verifier: to let the Go proxy check a token we would have to give
the proxy the signing key, and anything holding that key can mint grants for any
secret. The network edge is the most exposed component in the system, so it is
precisely where we least want a minting key.

## Decision

Sign tokens with Ed25519. The core holds the private key and is the only
component that can mint. Verifiers hold only the public key, which can check a
signature but cannot produce one.

The token format carries a version prefix (ag2) that pins exactly one algorithm.
The token never tells the verifier which algorithm to use, because
attacker-chosen algorithms are the root of the well known "alg: none" and
"RSA public key used as an HMAC secret" attacks against JWT.

Ed25519 specifically, rather than ECDSA or RSA:

- ECDSA needs a unique random nonce per signature. A repeated or biased nonce
  leaks the private key, which is how the PlayStation 3 signing key was
  recovered. Ed25519 derives its nonce deterministically, so that failure class
  does not exist.
- RSA at comparable strength means 3072-bit keys and 384-byte signatures against
  the 32-byte keys and 64-byte signatures of Ed25519, plus slower signing.
- Ed25519 verification is constant-time by construction, so there is no timing
  side channel to get wrong.

## Consequences

- Verifiers are decoupled from the signer. The proxy can reject forged tokens
  without being able to create them, which is what makes ADR 0004 possible.
- The public key can be published freely, so distribution is an ordinary
  unauthenticated endpoint rather than a secret-sharing problem.
- Signatures grew from 32 to 64 bytes. Tokens run about 700 characters, which is
  acceptable for a value carried in a request body.
- Ed25519 is not quantum resistant. The version prefix and the key_id claim
  exist so that migrating to a post-quantum scheme such as ML-DSA is a new token
  version verified alongside the old one, not a redesign.

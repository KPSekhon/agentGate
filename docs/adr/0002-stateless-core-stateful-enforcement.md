# 0002. Keep the crypto core stateless and enforcement stateful

Status: Accepted

## Context

Two components could plausibly own the lifecycle of a grant. The Rust core mints
and verifies tokens and already had an in-memory grant store. The Python backend
owns the REST surface, the database, and secret resolution.

Letting both track grant state produces a split brain: the core would believe a
token has one use left while the database says it was already spent, and the
answer depends on which service you ask. Restarting the core would also silently
reset use counts, because its store is in memory.

## Decision

Split along the line of what a signature can and cannot prove.

The Rust core is the policy decision point. It evaluates policy and performs
token minting and verification, and those operations are stateless: they touch
key material and nothing else. Given the same input it always returns the same
answer, and restarting it loses nothing as long as the signing key persists.

The Python backend is the policy enforcement point. It owns the facts a
signature cannot express because they change after the token is issued: how many
uses remain, whether the grant was revoked, and what the audit log records.

A signature proves a token is authentic. It cannot prove the token is still
allowed to be used. So authenticity is checked cryptographically in the core,
and liveness is checked against persistent state in the backend.

## Consequences

- There is exactly one writer for mutable grant state, so there is nothing to
  reconcile between services.
- The core can be restarted or run as several instances without coordination,
  because it holds no per-grant state.
- The SQLite store in the backend becomes the scaling bottleneck rather than the
  core. Moving to a shared database is a connection-string change, since no
  other component caches grant state.
- Verification happens in two places rather than one, so the exchange path makes
  an extra call. That cost buys the property that neither component can be
  compromised into approving a grant on its own.

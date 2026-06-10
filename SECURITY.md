# security model

agentgate brokers credentials for ai agents. this document is the threat model: what it protects, what it assumes, the trust boundaries between its components, and the cryptographic design of the grant token. it is written to be read by someone deciding whether to trust the system with real secrets.

## assets

what an attacker wants, in priority order:

1. **the secret value** — the actual api key, database password, or deploy token behind an `op://` reference.
2. **a usable grant** — a credential that can be exchanged for a secret value.
3. **the private signing key** — the Ed25519 private key in the Rust core that mints grant tokens. whoever holds it can forge any grant. (the corresponding *public* key is not sensitive — it can only verify, never mint, so it is safe to publish.)
4. **the audit trail** — tampering with it to hide activity.

## trust boundaries

a request crosses three boundaries. each component trusts less than the one behind it.

```
 untrusted          │  authenticated        │  trusted core
 (the agent)        │  (proxy + backend)    │  (decision point)
────────────────────┼───────────────────────┼─────────────────────
 holds a bearer     │  Go proxy terminates  │  Rust core holds the
 token and/or a     │  TLS, checks the      │  Ed25519 private key
 client cert; sends │  bearer token, rate-  │  and the policy set.
 grant tokens it    │  limits. Python       │  mints + verifies
 was given. assumed │  backend enforces     │  tokens. never exposed
 hostile.           │  policy + persists    │  to the network edge.
                    │  grant state.         │
```

- **agent → proxy** (`untrusted → authenticated`): the agent is assumed hostile. it authenticates with a bearer token, and optionally a client certificate (mTLS) whose CN the proxy forwards as `X-Client-CN`. everything past this point treats the agent's input as adversarial.
- **proxy → backend** (`authenticated → enforcement`): the Go proxy is the network edge — TLS termination, token-bucket rate limiting, structured logging. it does not make authorization decisions; it forwards authenticated traffic to the Python backend.
- **backend → core** (`enforcement → decision`): the Python backend is the **policy enforcement point (PEP)**. it owns the REST surface, grant state (SQLite), and secret resolution. it delegates the allow/deny decision and all cryptographic token operations to the Rust **policy decision point (PDP)** over gRPC. the core holds the private signing key and the policy set, and is never directly reachable from the agent.

the private key lives only in the core. a compromise of the proxy or backend does not yield the ability to forge grants — only the ability to *request* them, which still passes through policy evaluation.

## the grant capability token

a grant is a signed, self-describing capability token. format:

```
ag2.<hex(payload)>.<hex(ed25519_signature(payload))>
```

the payload is a json document of claims, minted by the core:

```json
{
  "grant_id":    "ce418748-7af4-4d66-aed6-6e8386334111",
  "requester":   "agent:github-actions",
  "secret_ref":  "op://ci-vault/deploy-key/credential",
  "environment": "ci",
  "task":        "deploy",
  "issued_at":   1780077757,
  "expires_at":  1780078057,
  "max_uses":    1,
  "policy_name": "ci-deploy-access",
  "key_id":      "2d8cf16480a15aae"
}
```

the signature is an **Ed25519** signature (via `ring`) over the exact payload bytes. minting and verification are **stateless** — they touch only the key material, never the grant store. this is deliberate: the core owns the cryptographic proof, the backend owns the mutable state.

the `ag2` version prefix replaces an earlier `ag1` HMAC-SHA256 scheme. the move to public-key signatures matters for trust: with HMAC, every verifier needs the *same secret* that mints tokens — so any verifier can forge. with Ed25519, the core holds the private key and verifiers hold only the **public key**, which can check a signature but never produce one. verifiers are cryptographically decoupled from the signer.

**public-key distribution (the PKI seam).** the core publishes its public key and a `key_id` over the `PublicKey` gRPC method. the `key_id` (first 8 bytes of `SHA-256(public_key)`) is stamped into every token, so a verifier holding several published keys can select the right one — the hook for **key rotation**: stand up a new key, publish it, let old tokens drain against the old key id, retire it. a fixed `AGENTGATE_ED25519_SEED` keeps the key (and thus previously issued tokens) stable across restarts.

**properties this gives us:**

- **tamper-evidence** — any change to the payload (a different `secret_ref`, a longer `expires_at`, more `max_uses`) invalidates the signature. verification fails before the backend touches the database. forged tokens are rejected the same way — without the private key, an attacker cannot produce a valid signature.
- **public verifiability** — anyone with the public key can verify a token; no one without the private key can mint one.
- **expiry bound into the signature** — `expires_at` is a signed claim. the core rejects an expired token at verification time; the attacker cannot extend the lifetime without breaking the signature.
- **self-describing** — the token carries its own scope. a leaked token is only ever good for one `secret_ref`, in one environment, for one task.
- **constant-time verification** — Ed25519 verification is constant-time by construction, so it leaks no timing signal.

these properties are not just asserted — the crypto is covered by **property-based tests** (`proptest`) that assert claims round-trip for arbitrary inputs and that flipping *any single bit* of the payload or signature is always rejected.

verification (signature + expiry) is cryptographic and stateless. **use-count and revocation are enforced separately** by the backend's persistent store, because they are mutable facts a signature cannot capture. a valid signature proves the token is authentic; the backend still checks that the grant has uses left and has not been revoked.

## guarantees

- **deny by default** — `policies/default.yaml` is a catch-all deny at priority 0. access requires an explicit higher-priority policy that matches the requester, environment, task, and secret reference. unknown agents get nothing.
- **two-phase exchange** — phase 1 (request) returns a token, never a secret. phase 2 (exchange) trades the token for the secret value. a token leaked before exchange is useless after it expires or is consumed; a token leaked after exchange is already spent.
- **single-use by default** — `max_uses` defaults to 1. the backend decrements on exchange and auto-revokes at zero. replaying a spent token gets a `410 gone`.
- **time-scoped** — every grant has a TTL, enforced both as a signed claim (core) and as a background expiry sweep (backend). the effective TTL is `min(requested, policy)`.
- **bulk revocation** — a single call (`/agent/revoke-agent`) revokes every active grant an agent holds, for incident response.
- **secrets never persist** — the audit log stores the `op://` reference and the decision, never the secret value. resolved secrets exist only in memory for the duration of the exchange.
- **graceful degradation, not fail-open** — if the core is unreachable, the backend falls back to an equivalent native policy engine that makes the *same* deny-by-default decisions. a core outage degrades token issuance to unsigned ids; it never grants access that policy would deny.

## what is out of scope

being honest about the boundaries:

- **demo mode uses mock secrets and an ephemeral signing key.** tokens do not survive a core restart, and the "secrets" are deterministic fakes. set `AGENTGATE_ED25519_SEED` (a 32-byte hex seed) for a stable key, and run in `live` mode with a 1Password service account for real use.
- **the bearer token is a shared secret.** on its own it authenticates the *caller*, not a specific agent identity. mTLS (`X-Client-CN`) is the stronger path for per-agent identity; the bearer token is the demo-friendly default.
- **grant state is single-node.** the backend's SQLite store is not designed for multi-region or high-availability deployment as written. the design (stateless crypto in the core, mutable state in the backend) is intended to make that swap — to a shared datastore — straightforward, but it is not implemented here.
- **no protection against a compromised core.** the core holds the private key and the policy set; it is the root of trust. its host must be secured accordingly.
- **classical (not yet post-quantum) signatures.** Ed25519 is not quantum-resistant. the token is versioned (`ag2`) and the `key_id` selects the verifying key, so migrating to a post-quantum signature (e.g. an NIST ML-DSA / Dilithium scheme) — or a hybrid — is an `ag3` engine plus a published key, not a redesign. not implemented here.
- **this is a portfolio project, not an audited product.** the cryptographic primitives (`ring`, Ed25519) are standard and used correctly, but the system has not undergone external security review.

## reporting

found something? open an issue describing the impact and reproduction. for anything you would not want public, contact the maintainer directly rather than filing publicly.

# Architecture decision records

Short records of the decisions that shaped AgentGate, written when the decision
was made rather than reconstructed afterwards. Each states the problem, the
options on the table, what was chosen, and what that choice costs.

| # | Decision | Status |
|---|---|---|
| [0001](0001-ed25519-over-hmac.md) | Sign grant tokens with Ed25519 instead of HMAC-SHA256 | Accepted |
| [0002](0002-stateless-core-stateful-enforcement.md) | Keep the crypto core stateless and enforcement stateful | Accepted |
| [0003](0003-pkcs8-key-storage.md) | Store signing keys as PKCS#8 | Accepted |
| [0004](0004-verify-tokens-at-the-edge.md) | Verify grant tokens at the Go proxy | Accepted |

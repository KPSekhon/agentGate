use std::sync::Arc;

use chrono::{Duration, Utc};
use tonic::{Request, Response, Status};

use crate::crypto::{GrantPayload, TokenEngine, generate_grant_id};
use crate::grants::{ActiveGrant, AuditEntry, GrantStore};
use crate::policy::PolicyEngine;
use crate::proto;

pub struct AgentGateService {
    token_engine: Arc<TokenEngine>,
    policy_engine: Arc<PolicyEngine>,
    grant_store: Arc<GrantStore>,
}

impl AgentGateService {
    pub fn new(
        token_engine: Arc<TokenEngine>,
        policy_engine: Arc<PolicyEngine>,
        grant_store: Arc<GrantStore>,
    ) -> Self {
        Self {
            token_engine,
            policy_engine,
            grant_store,
        }
    }
}

// Same reason as the proto module: the trait fixes the error type as
// tonic::Status, so we cannot shrink the Err variant.
#[allow(clippy::result_large_err)]
#[tonic::async_trait]
impl proto::agent_gate_server::AgentGate for AgentGateService {
    async fn request_grant(
        &self,
        request: Request<proto::GrantRequest>,
    ) -> Result<Response<proto::GrantResponse>, Status> {
        let req = request.into_inner();
        let requester = format!("agent:{}", req.agent_name);

        if let Err(e) = self.grant_store.check_rate_limit(&requester) {
            self.grant_store.log_audit(AuditEntry {
                timestamp: Utc::now(),
                requester: requester.clone(),
                environment: req.environment.clone(),
                task: req.task.clone(),
                secret_ref: req.secret_ref.clone(),
                action: "rate_limited".into(),
                policy_name: String::new(),
                source_ip: req.source_ip.clone(),
                anomaly_score: 0.0,
            });
            return Ok(Response::new(proto::GrantResponse {
                error: "rate_limited".into(),
                reason: e.to_string(),
                ..Default::default()
            }));
        }

        let result =
            self.policy_engine
                .evaluate(&requester, &req.environment, &req.task, &req.secret_ref);

        let anomaly = self
            .grant_store
            .compute_anomaly_score(&requester, &req.environment);

        match result.grant {
            None => {
                let policy_name = result
                    .policy
                    .as_ref()
                    .map(|p| p.name.clone())
                    .unwrap_or_else(|| "no-match".into());

                self.grant_store.log_audit(AuditEntry {
                    timestamp: Utc::now(),
                    requester,
                    environment: req.environment,
                    task: req.task,
                    secret_ref: req.secret_ref,
                    action: "denied".into(),
                    policy_name: policy_name.clone(),
                    source_ip: req.source_ip,
                    anomaly_score: anomaly,
                });

                let reason = if result.policy.as_ref().is_some_and(|p| p.deny) {
                    format!("Explicitly denied by policy '{policy_name}'")
                } else {
                    "No matching policy grants access".into()
                };

                Ok(Response::new(proto::GrantResponse {
                    error: "access_denied".into(),
                    reason,
                    ..Default::default()
                }))
            }
            Some(grant) => {
                let policy_name = result.policy.as_ref().unwrap().name.clone();
                let ttl = req.requested_ttl.min(grant.ttl_seconds);
                let now = Utc::now();
                let expires_at = now + Duration::seconds(ttl as i64);
                let grant_id = generate_grant_id().map_err(|e| Status::internal(e.to_string()))?;

                let payload = GrantPayload {
                    grant_id: grant_id.clone(),
                    requester: requester.clone(),
                    secret_ref: req.secret_ref.clone(),
                    environment: req.environment.clone(),
                    task: req.task.clone(),
                    issued_at: now.timestamp(),
                    expires_at: expires_at.timestamp(),
                    max_uses: grant.max_uses,
                    policy_name: policy_name.clone(),
                    key_id: String::new(), // stamped by the engine at mint time
                };

                let token = self
                    .token_engine
                    .mint(&payload)
                    .map_err(|e| Status::internal(e.to_string()))?;

                let active = ActiveGrant {
                    grant_id: grant_id.clone(),
                    token: token.clone(),
                    requester: requester.clone(),
                    secret_ref: req.secret_ref.clone(),
                    environment: req.environment.clone(),
                    task: req.task.clone(),
                    policy_name: policy_name.clone(),
                    issued_at: now,
                    expires_at,
                    uses_remaining: grant.max_uses,
                    revoked: false,
                };

                self.grant_store.store_grant(active);

                self.grant_store.log_audit(AuditEntry {
                    timestamp: now,
                    requester,
                    environment: req.environment,
                    task: req.task,
                    secret_ref: req.secret_ref,
                    action: "granted".into(),
                    policy_name: policy_name.clone(),
                    source_ip: req.source_ip,
                    anomaly_score: anomaly,
                });

                Ok(Response::new(proto::GrantResponse {
                    grant_id: token,
                    expires_at: expires_at.to_rfc3339(),
                    ttl_seconds: ttl,
                    uses_remaining: grant.max_uses as i32,
                    policy: policy_name,
                    ..Default::default()
                }))
            }
        }
    }

    async fn exchange_grant(
        &self,
        request: Request<proto::ExchangeRequest>,
    ) -> Result<Response<proto::ExchangeResponse>, Status> {
        let req = request.into_inner();

        let payload = self
            .token_engine
            .verify(&req.grant_id)
            .map_err(|e| Status::unauthenticated(e.to_string()))?;

        match self.grant_store.exchange(&payload.grant_id) {
            Ok(grant) => {
                self.grant_store.log_audit(AuditEntry {
                    timestamp: Utc::now(),
                    requester: grant.requester,
                    environment: grant.environment,
                    task: grant.task,
                    secret_ref: grant.secret_ref.clone(),
                    action: "exchanged".into(),
                    policy_name: grant.policy_name,
                    source_ip: req.source_ip,
                    anomaly_score: 0.0,
                });

                // In production this would call the secret provider (1Password SDK).
                // The grant token proves authorization — the proxy resolves the actual secret.
                Ok(Response::new(proto::ExchangeResponse {
                    grant_id: req.grant_id,
                    secret_value: format!("[resolved:{}]", grant.secret_ref),
                    uses_remaining: grant.uses_remaining as i32,
                    ..Default::default()
                }))
            }
            Err(e) => Ok(Response::new(proto::ExchangeResponse {
                error: "exchange_failed".into(),
                reason: e.to_string(),
                ..Default::default()
            })),
        }
    }

    async fn release_grant(
        &self,
        request: Request<proto::ReleaseRequest>,
    ) -> Result<Response<proto::ReleaseResponse>, Status> {
        let req = request.into_inner();

        let payload = self
            .token_engine
            .verify(&req.grant_id)
            .map_err(|e| Status::unauthenticated(e.to_string()))?;

        match self.grant_store.release(&payload.grant_id) {
            Ok(()) => {
                self.grant_store.log_audit(AuditEntry {
                    timestamp: Utc::now(),
                    requester: payload.requester,
                    environment: payload.environment,
                    task: payload.task,
                    secret_ref: payload.secret_ref,
                    action: "released".into(),
                    policy_name: payload.policy_name,
                    source_ip: String::new(),
                    anomaly_score: 0.0,
                });

                Ok(Response::new(proto::ReleaseResponse {
                    status: "released".into(),
                    grant_id: req.grant_id,
                    ..Default::default()
                }))
            }
            Err(e) => Ok(Response::new(proto::ReleaseResponse {
                error: "release_failed".into(),
                reason: e.to_string(),
                ..Default::default()
            })),
        }
    }

    async fn revoke_agent(
        &self,
        request: Request<proto::RevokeAgentRequest>,
    ) -> Result<Response<proto::RevokeAgentResponse>, Status> {
        let req = request.into_inner();
        let count = self.grant_store.revoke_agent(&req.agent_name);

        self.grant_store.log_audit(AuditEntry {
            timestamp: Utc::now(),
            requester: format!("agent:{}", req.agent_name),
            environment: String::new(),
            task: String::new(),
            secret_ref: String::new(),
            action: "bulk_revoked".into(),
            policy_name: String::new(),
            source_ip: String::new(),
            anomaly_score: 0.0,
        });

        Ok(Response::new(proto::RevokeAgentResponse {
            status: if count > 0 {
                "revoked"
            } else {
                "no_active_grants"
            }
            .into(),
            agent: req.agent_name,
            revoked_count: count as i32,
        }))
    }

    async fn evaluate_policy(
        &self,
        request: Request<proto::PolicyEvalRequest>,
    ) -> Result<Response<proto::PolicyEvalResponse>, Status> {
        let req = request.into_inner();
        let result = self.policy_engine.evaluate(
            &req.requester,
            &req.environment,
            &req.task,
            &req.secret_ref,
        );

        match result.grant {
            Some(grant) => Ok(Response::new(proto::PolicyEvalResponse {
                allowed: true,
                policy_name: result.policy.unwrap().name,
                reason: String::new(),
                ttl_seconds: grant.ttl_seconds,
                max_uses: grant.max_uses as i32,
            })),
            None => Ok(Response::new(proto::PolicyEvalResponse {
                allowed: false,
                policy_name: result
                    .policy
                    .map(|p| p.name)
                    .unwrap_or_else(|| "no-match".into()),
                reason: "denied".into(),
                ttl_seconds: 0,
                max_uses: 0,
            })),
        }
    }

    async fn health_check(
        &self,
        _request: Request<proto::HealthRequest>,
    ) -> Result<Response<proto::HealthResponse>, Status> {
        Ok(Response::new(proto::HealthResponse {
            status: "healthy".into(),
            active_grants: self.grant_store.active_grant_count() as i64,
            total_evaluations: self.grant_store.audit_entries().len() as i64,
        }))
    }

    /// Mint a signed capability token from a set of claims. Stateless — this is
    /// a pure HMAC-SHA256 signing operation and does not touch the grant store.
    /// The enforcement point (Python) persists grant state separately.
    async fn mint_token(
        &self,
        request: Request<proto::MintTokenRequest>,
    ) -> Result<Response<proto::MintTokenResponse>, Status> {
        let claims = request
            .into_inner()
            .claims
            .ok_or_else(|| Status::invalid_argument("claims are required"))?;

        let payload = GrantPayload {
            grant_id: claims.grant_id,
            requester: claims.requester,
            secret_ref: claims.secret_ref,
            environment: claims.environment,
            task: claims.task,
            issued_at: claims.issued_at,
            expires_at: claims.expires_at,
            max_uses: claims.max_uses,
            policy_name: claims.policy_name,
            key_id: String::new(), // stamped by the engine at mint time
        };

        match self.token_engine.mint(&payload) {
            Ok(token) => Ok(Response::new(proto::MintTokenResponse {
                token,
                error: String::new(),
            })),
            Err(e) => Ok(Response::new(proto::MintTokenResponse {
                token: String::new(),
                error: e.to_string(),
            })),
        }
    }

    /// Verify a capability token's signature and expiry. Stateless — proves the
    /// token was minted by this core and has not been tampered with or expired.
    /// Use-count and revocation are enforced by the persistent grant store at
    /// the enforcement point, not here.
    async fn verify_token(
        &self,
        request: Request<proto::VerifyTokenRequest>,
    ) -> Result<Response<proto::VerifyTokenResponse>, Status> {
        let token = request.into_inner().token;

        match self.token_engine.verify(&token) {
            Ok(payload) => {
                let now = Utc::now().timestamp();
                if payload.expires_at < now {
                    return Ok(Response::new(proto::VerifyTokenResponse {
                        valid: false,
                        claims: None,
                        reason: "token expired".into(),
                    }));
                }

                Ok(Response::new(proto::VerifyTokenResponse {
                    valid: true,
                    claims: Some(proto::GrantClaims {
                        grant_id: payload.grant_id,
                        requester: payload.requester,
                        secret_ref: payload.secret_ref,
                        environment: payload.environment,
                        task: payload.task,
                        issued_at: payload.issued_at,
                        expires_at: payload.expires_at,
                        max_uses: payload.max_uses,
                        policy_name: payload.policy_name,
                        key_id: payload.key_id,
                    }),
                    reason: String::new(),
                }))
            }
            Err(e) => Ok(Response::new(proto::VerifyTokenResponse {
                valid: false,
                claims: None,
                reason: e.to_string(),
            })),
        }
    }

    /// Publish the Ed25519 public key and its id. Verifiers use this to validate
    /// tokens without ever holding the signing key.
    async fn public_key(
        &self,
        _request: Request<proto::PublicKeyRequest>,
    ) -> Result<Response<proto::PublicKeyResponse>, Status> {
        Ok(Response::new(proto::PublicKeyResponse {
            algorithm: "Ed25519".into(),
            key_id: self.token_engine.key_id().to_string(),
            public_key: self.token_engine.public_key_hex(),
        }))
    }
}

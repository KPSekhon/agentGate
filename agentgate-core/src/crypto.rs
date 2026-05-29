use ring::hmac;
use ring::rand::{SecureRandom, SystemRandom};
use thiserror::Error;

#[derive(Error, Debug)]
pub enum CryptoError {
    #[error("HMAC verification failed — token is tampered or forged")]
    InvalidSignature,
    #[error("malformed token: expected 3 segments, got {0}")]
    MalformedToken(usize),
    #[error("token payload decode failed: {0}")]
    DecodeFailed(String),
    #[error("RNG failure: {0}")]
    RngFailed(String),
}

pub struct TokenEngine {
    key: hmac::Key,
}

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct GrantPayload {
    pub grant_id: String,
    pub requester: String,
    pub secret_ref: String,
    pub environment: String,
    pub task: String,
    pub issued_at: i64,
    pub expires_at: i64,
    pub max_uses: u32,
    pub policy_name: String,
}

impl TokenEngine {
    pub fn new(secret: &[u8]) -> Self {
        let key = hmac::Key::new(hmac::HMAC_SHA256, secret);
        Self { key }
    }

    pub fn from_random() -> Result<Self, CryptoError> {
        let rng = SystemRandom::new();
        let mut secret = [0u8; 32];
        rng.fill(&mut secret)
            .map_err(|e| CryptoError::RngFailed(e.to_string()))?;
        Ok(Self::new(&secret))
    }

    pub fn mint(&self, payload: &GrantPayload) -> Result<String, CryptoError> {
        let json = serde_json::to_vec(payload)
            .map_err(|e| CryptoError::DecodeFailed(e.to_string()))?;
        let encoded = hex::encode(&json);
        let tag = hmac::sign(&self.key, json.as_ref());
        let sig = hex::encode(tag.as_ref());
        Ok(format!("ag1.{encoded}.{sig}"))
    }

    pub fn verify(&self, token: &str) -> Result<GrantPayload, CryptoError> {
        let parts: Vec<&str> = token.splitn(3, '.').collect();
        if parts.len() != 3 {
            return Err(CryptoError::MalformedToken(parts.len()));
        }

        let payload_hex = parts[1];
        let sig_hex = parts[2];

        let payload_bytes =
            hex::decode(payload_hex).map_err(|e| CryptoError::DecodeFailed(e.to_string()))?;
        let sig_bytes =
            hex::decode(sig_hex).map_err(|e| CryptoError::DecodeFailed(e.to_string()))?;

        hmac::verify(&self.key, &payload_bytes, &sig_bytes)
            .map_err(|_| CryptoError::InvalidSignature)?;

        serde_json::from_slice(&payload_bytes)
            .map_err(|e| CryptoError::DecodeFailed(e.to_string()))
    }
}

pub fn generate_grant_id() -> Result<String, CryptoError> {
    let rng = SystemRandom::new();
    let mut bytes = [0u8; 16];
    rng.fill(&mut bytes)
        .map_err(|e| CryptoError::RngFailed(e.to_string()))?;
    Ok(hex::encode(bytes))
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::Utc;

    #[test]
    fn mint_and_verify_roundtrip() {
        let engine = TokenEngine::new(b"test-secret-key-for-agentgate-32");
        let now = Utc::now().timestamp();

        let payload = GrantPayload {
            grant_id: "grant-001".into(),
            requester: "agent:deploy-bot".into(),
            secret_ref: "op://vault/api-key/credential".into(),
            environment: "staging".into(),
            task: "deploy".into(),
            issued_at: now,
            expires_at: now + 300,
            max_uses: 1,
            policy_name: "deploy-access".into(),
        };

        let token = engine.mint(&payload).unwrap();
        assert!(token.starts_with("ag1."));

        let verified = engine.verify(&token).unwrap();
        assert_eq!(verified.grant_id, "grant-001");
        assert_eq!(verified.requester, "agent:deploy-bot");
        assert_eq!(verified.max_uses, 1);
    }

    #[test]
    fn tampered_token_rejected() {
        let engine = TokenEngine::new(b"test-secret-key-for-agentgate-32");
        let now = Utc::now().timestamp();

        let payload = GrantPayload {
            grant_id: "grant-002".into(),
            requester: "agent:ci".into(),
            secret_ref: "op://vault/key/cred".into(),
            environment: "ci".into(),
            task: "build".into(),
            issued_at: now,
            expires_at: now + 60,
            max_uses: 1,
            policy_name: "ci-access".into(),
        };

        let token = engine.mint(&payload).unwrap();
        let parts: Vec<&str> = token.splitn(3, '.').collect();
        let mut sig_bytes = hex::decode(parts[2]).unwrap();
        sig_bytes[0] ^= 0xff; // flip bits in the signature
        let tampered = format!("{}.{}.{}", parts[0], parts[1], hex::encode(&sig_bytes));
        assert!(engine.verify(&tampered).is_err());
    }

    #[test]
    fn wrong_key_rejected() {
        let engine1 = TokenEngine::new(b"key-one-for-agentgate-testing!!");
        let engine2 = TokenEngine::new(b"key-two-for-agentgate-testing!!");
        let now = Utc::now().timestamp();

        let payload = GrantPayload {
            grant_id: "grant-003".into(),
            requester: "agent:x".into(),
            secret_ref: "op://v/i/f".into(),
            environment: "dev".into(),
            task: "test".into(),
            issued_at: now,
            expires_at: now + 60,
            max_uses: 1,
            policy_name: "test".into(),
        };

        let token = engine1.mint(&payload).unwrap();
        assert!(engine2.verify(&token).is_err());
    }

    #[test]
    fn malformed_token_rejected() {
        let engine = TokenEngine::new(b"test-secret-key-for-agentgate-32");
        assert!(engine.verify("not-a-valid-token").is_err());
        assert!(engine.verify("ag1.only-two").is_err());
    }
}

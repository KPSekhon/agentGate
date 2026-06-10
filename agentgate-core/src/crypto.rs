use ring::rand::{SecureRandom, SystemRandom};
use ring::signature::{self, Ed25519KeyPair, KeyPair};
use ring::{digest, hmac};
use thiserror::Error;

#[derive(Error, Debug)]
pub enum CryptoError {
    #[error("signature verification failed — token is tampered or forged")]
    InvalidSignature,
    #[error("malformed token: expected 3 segments, got {0}")]
    MalformedToken(usize),
    #[error("unsupported token version: {0}")]
    UnsupportedVersion(String),
    #[error("token payload decode failed: {0}")]
    DecodeFailed(String),
    #[error("key rejected: {0}")]
    KeyRejected(String),
    #[error("RNG failure: {0}")]
    RngFailed(String),
}

/// Token version prefix. `ag2` denotes an Ed25519 (public-key) signature.
/// `ag1` (HMAC-SHA256, symmetric) is the legacy scheme — see SECURITY.md for
/// why we moved to public-key signatures (verifiers no longer need the secret).
const TOKEN_VERSION: &str = "ag2";

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
    /// Identifier of the key that signed this token (first 8 bytes of the
    /// SHA-256 of the public key, hex-encoded). Lets a verifier select the
    /// right key during rotation. Set by the engine at mint time.
    #[serde(default)]
    pub key_id: String,
}

/// Ed25519 capability-token engine.
///
/// The core holds the private key and is the only party that can mint tokens.
/// Verification needs only the public key, so any number of verifiers can be
/// decoupled from the signer — the basis of the PKI story in SECURITY.md.
pub struct TokenEngine {
    key_pair: Ed25519KeyPair,
    public_key: Vec<u8>,
    key_id: String,
}

impl TokenEngine {
    /// Build an engine from a 32-byte Ed25519 seed (e.g. from `AGENTGATE_ED25519_SEED`).
    /// A fixed seed yields a stable key id across restarts, so previously issued
    /// tokens remain verifiable.
    pub fn from_seed(seed: &[u8]) -> Result<Self, CryptoError> {
        let key_pair = Ed25519KeyPair::from_seed_unchecked(seed)
            .map_err(|e| CryptoError::KeyRejected(e.to_string()))?;
        let public_key = key_pair.public_key().as_ref().to_vec();
        let key_id = compute_key_id(&public_key);
        Ok(Self {
            key_pair,
            public_key,
            key_id,
        })
    }

    /// Build an engine with a fresh random key. Tokens will not survive a
    /// restart — fine for demo mode, not for production.
    pub fn from_random() -> Result<Self, CryptoError> {
        let rng = SystemRandom::new();
        let mut seed = [0u8; 32];
        rng.fill(&mut seed)
            .map_err(|e| CryptoError::RngFailed(e.to_string()))?;
        Self::from_seed(&seed)
    }

    /// Hex-encoded Ed25519 public key. Safe to publish — verifiers use it to
    /// check tokens but cannot mint with it.
    pub fn public_key_hex(&self) -> String {
        hex::encode(&self.public_key)
    }

    /// Short identifier of the signing key (see `GrantPayload::key_id`).
    pub fn key_id(&self) -> &str {
        &self.key_id
    }

    /// Mint a signed capability token: `ag2.<hex(payload)>.<hex(signature)>`.
    /// Stamps the engine's key id into the payload before signing.
    pub fn mint(&self, payload: &GrantPayload) -> Result<String, CryptoError> {
        let mut payload = payload.clone();
        payload.key_id = self.key_id.clone();

        let json =
            serde_json::to_vec(&payload).map_err(|e| CryptoError::DecodeFailed(e.to_string()))?;
        let sig = self.key_pair.sign(&json);
        Ok(format!(
            "{TOKEN_VERSION}.{}.{}",
            hex::encode(&json),
            hex::encode(sig.as_ref())
        ))
    }

    /// Verify a token's version, signature, and structure. Returns the signed
    /// claims on success. Stateless — does not check expiry, use-count, or
    /// revocation (those are the enforcement point's job).
    pub fn verify(&self, token: &str) -> Result<GrantPayload, CryptoError> {
        let parts: Vec<&str> = token.splitn(3, '.').collect();
        if parts.len() != 3 {
            return Err(CryptoError::MalformedToken(parts.len()));
        }
        if parts[0] != TOKEN_VERSION {
            return Err(CryptoError::UnsupportedVersion(parts[0].to_string()));
        }

        let payload_bytes =
            hex::decode(parts[1]).map_err(|e| CryptoError::DecodeFailed(e.to_string()))?;
        let sig_bytes =
            hex::decode(parts[2]).map_err(|e| CryptoError::DecodeFailed(e.to_string()))?;

        let public_key = signature::UnparsedPublicKey::new(&signature::ED25519, &self.public_key);
        public_key
            .verify(&payload_bytes, &sig_bytes)
            .map_err(|_| CryptoError::InvalidSignature)?;

        serde_json::from_slice(&payload_bytes).map_err(|e| CryptoError::DecodeFailed(e.to_string()))
    }
}

/// Key id = first 8 bytes of SHA-256(public_key), hex-encoded (16 chars).
fn compute_key_id(public_key: &[u8]) -> String {
    let hash = digest::digest(&digest::SHA256, public_key);
    hex::encode(&hash.as_ref()[..8])
}

pub fn generate_grant_id() -> Result<String, CryptoError> {
    let rng = SystemRandom::new();
    let mut bytes = [0u8; 16];
    rng.fill(&mut bytes)
        .map_err(|e| CryptoError::RngFailed(e.to_string()))?;
    Ok(hex::encode(bytes))
}

/// Constant-time tag used internally for non-token integrity needs.
/// Retained so the symmetric primitive stays available for future use
/// (e.g. signing internal audit checkpoints) without reintroducing it for tokens.
#[allow(dead_code)]
pub fn hmac_tag(key: &[u8], msg: &[u8]) -> String {
    let key = hmac::Key::new(hmac::HMAC_SHA256, key);
    hex::encode(hmac::sign(&key, msg).as_ref())
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::Utc;
    use proptest::prelude::*;

    fn sample_payload() -> GrantPayload {
        let now = Utc::now().timestamp();
        GrantPayload {
            grant_id: "grant-001".into(),
            requester: "agent:deploy-bot".into(),
            secret_ref: "op://vault/api-key/credential".into(),
            environment: "staging".into(),
            task: "deploy".into(),
            issued_at: now,
            expires_at: now + 300,
            max_uses: 1,
            policy_name: "deploy-access".into(),
            key_id: String::new(),
        }
    }

    #[test]
    fn mint_and_verify_roundtrip() {
        let engine = TokenEngine::from_random().unwrap();
        let token = engine.mint(&sample_payload()).unwrap();
        assert!(token.starts_with("ag2."));

        let verified = engine.verify(&token).unwrap();
        assert_eq!(verified.grant_id, "grant-001");
        assert_eq!(verified.requester, "agent:deploy-bot");
        assert_eq!(verified.max_uses, 1);
        // The engine stamps its key id into every token it mints.
        assert_eq!(verified.key_id, engine.key_id());
        assert!(!verified.key_id.is_empty());
    }

    #[test]
    fn stable_seed_gives_stable_key_id() {
        let seed = [7u8; 32];
        let a = TokenEngine::from_seed(&seed).unwrap();
        let b = TokenEngine::from_seed(&seed).unwrap();
        assert_eq!(a.key_id(), b.key_id());
        assert_eq!(a.public_key_hex(), b.public_key_hex());
        // A token minted by one is verifiable by the other (same key material).
        let token = a.mint(&sample_payload()).unwrap();
        assert!(b.verify(&token).is_ok());
    }

    #[test]
    fn tampered_token_rejected() {
        let engine = TokenEngine::from_random().unwrap();
        let token = engine.mint(&sample_payload()).unwrap();
        let parts: Vec<&str> = token.splitn(3, '.').collect();
        let mut sig_bytes = hex::decode(parts[2]).unwrap();
        sig_bytes[0] ^= 0xff; // flip bits in the signature
        let tampered = format!("{}.{}.{}", parts[0], parts[1], hex::encode(&sig_bytes));
        assert!(engine.verify(&tampered).is_err());
    }

    #[test]
    fn wrong_key_rejected() {
        let engine1 = TokenEngine::from_seed(&[1u8; 32]).unwrap();
        let engine2 = TokenEngine::from_seed(&[2u8; 32]).unwrap();
        let token = engine1.mint(&sample_payload()).unwrap();
        assert!(engine2.verify(&token).is_err());
    }

    #[test]
    fn wrong_version_rejected() {
        let engine = TokenEngine::from_random().unwrap();
        let token = engine.mint(&sample_payload()).unwrap();
        let parts: Vec<&str> = token.splitn(3, '.').collect();
        let legacy = format!("ag1.{}.{}", parts[1], parts[2]);
        assert!(matches!(
            engine.verify(&legacy),
            Err(CryptoError::UnsupportedVersion(_))
        ));
    }

    #[test]
    fn malformed_token_rejected() {
        let engine = TokenEngine::from_random().unwrap();
        assert!(engine.verify("not-a-valid-token").is_err());
        assert!(engine.verify("ag2.only-two").is_err());
    }

    proptest! {
        // Any well-formed set of claims round-trips through mint -> verify
        // unchanged (modulo the key_id the engine stamps in).
        #[test]
        fn prop_roundtrip_preserves_claims(
            grant_id in "[a-zA-Z0-9-]{1,40}",
            requester in "agent:[a-z0-9-]{1,30}",
            secret_ref in "op://[a-z0-9/-]{1,50}",
            max_uses in 1u32..1000,
            ttl in 0i64..1_000_000,
        ) {
            let engine = TokenEngine::from_random().unwrap();
            let now = Utc::now().timestamp();
            let payload = GrantPayload {
                grant_id: grant_id.clone(),
                requester: requester.clone(),
                secret_ref: secret_ref.clone(),
                environment: "ci".into(),
                task: "deploy".into(),
                issued_at: now,
                expires_at: now + ttl,
                max_uses,
                policy_name: "p".into(),
                key_id: String::new(),
            };
            let token = engine.mint(&payload).unwrap();
            let verified = engine.verify(&token).unwrap();
            prop_assert_eq!(verified.grant_id, grant_id);
            prop_assert_eq!(verified.requester, requester);
            prop_assert_eq!(verified.secret_ref, secret_ref);
            prop_assert_eq!(verified.max_uses, max_uses);
        }

        // Flipping any single byte of the signature always fails verification.
        #[test]
        fn prop_any_signature_mutation_rejected(byte_idx in 0usize..64, bit in 0u32..8) {
            let engine = TokenEngine::from_random().unwrap();
            let token = engine.mint(&sample_payload()).unwrap();
            let parts: Vec<&str> = token.splitn(3, '.').collect();
            let mut sig = hex::decode(parts[2]).unwrap();
            let idx = byte_idx % sig.len();
            sig[idx] ^= 1 << bit;
            let mutated = format!("{}.{}.{}", parts[0], parts[1], hex::encode(&sig));
            prop_assert!(engine.verify(&mutated).is_err());
        }

        // Flipping any single byte of the payload always fails verification.
        #[test]
        fn prop_any_payload_mutation_rejected(byte_idx in 0usize..4096, bit in 0u32..8) {
            let engine = TokenEngine::from_random().unwrap();
            let token = engine.mint(&sample_payload()).unwrap();
            let parts: Vec<&str> = token.splitn(3, '.').collect();
            let mut payload = hex::decode(parts[1]).unwrap();
            let idx = byte_idx % payload.len();
            payload[idx] ^= 1 << bit;
            let mutated = format!("{}.{}.{}", parts[0], hex::encode(&payload), parts[2]);
            prop_assert!(engine.verify(&mutated).is_err());
        }
    }
}

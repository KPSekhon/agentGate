use chrono::{DateTime, Utc};
use std::collections::HashMap;
use std::sync::Mutex;
use thiserror::Error;

#[derive(Error, Debug)]
pub enum GrantError {
    #[error("grant '{0}' not found")]
    NotFound(String),
    #[error("grant '{0}' has been revoked")]
    Revoked(String),
    #[error("grant '{0}' has expired")]
    Expired(String),
    #[error("grant '{0}' has no remaining uses")]
    Exhausted(String),
    #[error("rate limit exceeded: {0} requests/min for {1}")]
    RateLimited(u32, String),
}

#[derive(Debug, Clone)]
pub struct ActiveGrant {
    pub grant_id: String,
    pub token: String,
    pub requester: String,
    pub secret_ref: String,
    pub environment: String,
    pub task: String,
    pub policy_name: String,
    pub issued_at: DateTime<Utc>,
    pub expires_at: DateTime<Utc>,
    pub uses_remaining: u32,
    pub revoked: bool,
}

#[derive(Debug, Clone)]
pub struct AuditEntry {
    pub timestamp: DateTime<Utc>,
    pub requester: String,
    pub environment: String,
    pub task: String,
    pub secret_ref: String,
    pub action: String,
    pub policy_name: String,
    pub source_ip: String,
    pub anomaly_score: f64,
}

struct RateWindow {
    timestamps: Vec<DateTime<Utc>>,
}

pub struct GrantStore {
    grants: Mutex<HashMap<String, ActiveGrant>>,
    audit_log: Mutex<Vec<AuditEntry>>,
    rate_windows: Mutex<HashMap<String, RateWindow>>,
    rate_limit_per_minute: u32,
}

impl GrantStore {
    pub fn new(rate_limit_per_minute: u32) -> Self {
        Self {
            grants: Mutex::new(HashMap::new()),
            audit_log: Mutex::new(Vec::new()),
            rate_windows: Mutex::new(HashMap::new()),
            rate_limit_per_minute,
        }
    }

    pub fn check_rate_limit(&self, requester: &str) -> Result<(), GrantError> {
        let now = Utc::now();
        let window_start = now - chrono::Duration::seconds(60);

        let mut windows = self.rate_windows.lock().unwrap();
        let window = windows.entry(requester.to_string()).or_insert(RateWindow {
            timestamps: Vec::new(),
        });

        window.timestamps.retain(|t| *t > window_start);

        if window.timestamps.len() as u32 >= self.rate_limit_per_minute {
            return Err(GrantError::RateLimited(
                self.rate_limit_per_minute,
                requester.to_string(),
            ));
        }

        window.timestamps.push(now);
        Ok(())
    }

    pub fn store_grant(&self, grant: ActiveGrant) {
        let mut grants = self.grants.lock().unwrap();
        grants.insert(grant.grant_id.clone(), grant);
    }

    pub fn exchange(&self, grant_id: &str) -> Result<ActiveGrant, GrantError> {
        let mut grants = self.grants.lock().unwrap();
        let grant = grants
            .get_mut(grant_id)
            .ok_or_else(|| GrantError::NotFound(grant_id.to_string()))?;

        if grant.revoked {
            return Err(GrantError::Revoked(grant_id.to_string()));
        }
        if grant.expires_at < Utc::now() {
            grant.revoked = true;
            return Err(GrantError::Expired(grant_id.to_string()));
        }
        if grant.uses_remaining == 0 {
            return Err(GrantError::Exhausted(grant_id.to_string()));
        }

        grant.uses_remaining -= 1;
        if grant.uses_remaining == 0 {
            grant.revoked = true;
        }

        Ok(grant.clone())
    }

    pub fn release(&self, grant_id: &str) -> Result<(), GrantError> {
        let mut grants = self.grants.lock().unwrap();
        let grant = grants
            .get_mut(grant_id)
            .ok_or_else(|| GrantError::NotFound(grant_id.to_string()))?;

        if grant.revoked {
            return Err(GrantError::Revoked(grant_id.to_string()));
        }

        grant.revoked = true;
        Ok(())
    }

    pub fn revoke_agent(&self, agent_name: &str) -> u32 {
        let requester = format!("agent:{agent_name}");
        let mut grants = self.grants.lock().unwrap();
        let mut count = 0u32;

        for grant in grants.values_mut() {
            if grant.requester == requester && !grant.revoked {
                grant.revoked = true;
                count += 1;
            }
        }

        count
    }

    pub fn expire_stale(&self) -> u32 {
        let now = Utc::now();
        let mut grants = self.grants.lock().unwrap();
        let mut count = 0u32;

        for grant in grants.values_mut() {
            if !grant.revoked && grant.expires_at < now {
                grant.revoked = true;
                count += 1;
            }
        }

        count
    }

    pub fn log_audit(&self, entry: AuditEntry) {
        self.audit_log.lock().unwrap().push(entry);
    }

    pub fn active_grant_count(&self) -> usize {
        let grants = self.grants.lock().unwrap();
        grants.values().filter(|g| !g.revoked).count()
    }

    pub fn audit_entries(&self) -> Vec<AuditEntry> {
        self.audit_log.lock().unwrap().clone()
    }

    pub fn compute_anomaly_score(&self, requester: &str, environment: &str) -> f64 {
        let now = Utc::now();
        let five_min_ago = now - chrono::Duration::seconds(300);
        let log = self.audit_log.lock().unwrap();

        let mut score: f64 = 0.0;

        let recent = log
            .iter()
            .filter(|e| e.requester == requester && e.timestamp > five_min_ago)
            .count();
        if recent > 10 {
            score += 0.4;
        }

        let hour = now.hour();
        if environment == "production" && !(6..=22).contains(&hour) {
            score += 0.3;
        }

        let total = log.iter().filter(|e| e.requester == requester).count();
        if total == 0 {
            score += 0.3;
        }

        score.min(1.0)
    }
}

use chrono::Timelike;

#[cfg(test)]
mod tests {
    use super::*;

    fn make_grant(id: &str, requester: &str, ttl_secs: i64) -> ActiveGrant {
        let now = Utc::now();
        ActiveGrant {
            grant_id: id.to_string(),
            token: format!("ag1.fake.{id}"),
            requester: requester.to_string(),
            secret_ref: "op://vault/key/cred".to_string(),
            environment: "test".to_string(),
            task: "test".to_string(),
            policy_name: "test-policy".to_string(),
            issued_at: now,
            expires_at: now + chrono::Duration::seconds(ttl_secs),
            uses_remaining: 1,
            revoked: false,
        }
    }

    #[test]
    fn store_and_exchange() {
        let store = GrantStore::new(10);
        store.store_grant(make_grant("g1", "agent:bot", 300));

        let result = store.exchange("g1");
        assert!(result.is_ok());
        assert_eq!(result.unwrap().uses_remaining, 0);

        // Grant auto-revoked after uses hit 0
        let again = store.exchange("g1");
        assert!(matches!(again, Err(GrantError::Revoked(_))));
    }

    #[test]
    fn release_grant() {
        let store = GrantStore::new(10);
        store.store_grant(make_grant("g2", "agent:bot", 300));

        store.release("g2").unwrap();

        let result = store.exchange("g2");
        assert!(matches!(result, Err(GrantError::Revoked(_))));
    }

    #[test]
    fn revoke_agent_bulk() {
        let store = GrantStore::new(10);
        store.store_grant(make_grant("g3", "agent:bad", 300));
        store.store_grant(make_grant("g4", "agent:bad", 300));
        store.store_grant(make_grant("g5", "agent:good", 300));

        let count = store.revoke_agent("bad");
        assert_eq!(count, 2);

        assert!(store.exchange("g5").is_ok());
    }

    #[test]
    fn rate_limiting() {
        let store = GrantStore::new(3);
        for _ in 0..3 {
            store.check_rate_limit("agent:fast").unwrap();
        }
        let result = store.check_rate_limit("agent:fast");
        assert!(matches!(result, Err(GrantError::RateLimited(_, _))));
    }

    #[test]
    fn expire_stale_grants() {
        let store = GrantStore::new(10);
        store.store_grant(make_grant("g6", "agent:x", -10)); // already expired
        store.store_grant(make_grant("g7", "agent:x", 300));

        let expired = store.expire_stale();
        assert_eq!(expired, 1);
        assert_eq!(store.active_grant_count(), 1);
    }

    #[test]
    fn not_found() {
        let store = GrantStore::new(10);
        let result = store.exchange("nonexistent");
        assert!(matches!(result, Err(GrantError::NotFound(_))));
    }
}

use glob_match::glob_match;
use serde::{Deserialize, Serialize};
use std::path::Path;
use thiserror::Error;

#[derive(Error, Debug)]
pub enum PolicyError {
    #[error("failed to read policy file {path}: {source}")]
    IoError {
        path: String,
        source: std::io::Error,
    },
    #[error("failed to parse policy YAML in {path}: {source}")]
    ParseError {
        path: String,
        source: serde_yaml::Error,
    },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Policy {
    pub name: String,
    #[serde(default)]
    pub description: String,
    #[serde(default)]
    pub priority: i32,
    #[serde(default)]
    pub conditions: Vec<Condition>,
    #[serde(default)]
    pub grants: Vec<Grant>,
    #[serde(default)]
    pub deny: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Condition {
    #[serde(default = "default_glob")]
    pub requester: String,
    #[serde(default = "default_glob")]
    pub environment: String,
    #[serde(default = "default_glob")]
    pub task: String,
}

fn default_glob() -> String {
    "*".to_string()
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Grant {
    pub secret_ref: String,
    #[serde(default = "default_ttl")]
    pub ttl_seconds: i32,
    #[serde(default = "default_max_uses")]
    pub max_uses: u32,
}

fn default_ttl() -> i32 {
    300
}
fn default_max_uses() -> u32 {
    1
}

#[derive(Debug, Clone)]
pub struct EvalResult {
    pub grant: Option<Grant>,
    pub policy: Option<Policy>,
}

pub struct PolicyEngine {
    policies: Vec<Policy>,
}

impl Default for PolicyEngine {
    fn default() -> Self {
        Self::new()
    }
}

impl PolicyEngine {
    pub fn new() -> Self {
        Self {
            policies: Vec::new(),
        }
    }

    pub fn load_directory(&mut self, dir: &Path) -> Result<usize, PolicyError> {
        self.policies.clear();

        let entries = std::fs::read_dir(dir).map_err(|e| PolicyError::IoError {
            path: dir.display().to_string(),
            source: e,
        })?;

        for entry in entries.flatten() {
            let path = entry.path();
            let ext = path.extension().and_then(|e| e.to_str());
            if ext != Some("yaml") && ext != Some("yml") {
                continue;
            }

            let content = std::fs::read_to_string(&path).map_err(|e| PolicyError::IoError {
                path: path.display().to_string(),
                source: e,
            })?;

            for doc in content.split("\n---") {
                let trimmed = doc.trim();
                if trimmed.is_empty() {
                    continue;
                }
                let policy: Policy =
                    serde_yaml::from_str(trimmed).map_err(|e| PolicyError::ParseError {
                        path: path.display().to_string(),
                        source: e,
                    })?;
                self.policies.push(policy);
            }
        }

        self.policies.sort_by_key(|p| std::cmp::Reverse(p.priority));

        Ok(self.policies.len())
    }

    pub fn load_policies(&mut self, policies: Vec<Policy>) {
        self.policies = policies;
        self.policies.sort_by_key(|p| std::cmp::Reverse(p.priority));
    }

    pub fn evaluate(
        &self,
        requester: &str,
        environment: &str,
        task: &str,
        secret_ref: &str,
    ) -> EvalResult {
        for policy in &self.policies {
            if !conditions_match(policy, requester, environment, task) {
                continue;
            }

            if policy.deny {
                return EvalResult {
                    grant: None,
                    policy: Some(policy.clone()),
                };
            }

            for grant in &policy.grants {
                if glob_match(&grant.secret_ref, secret_ref) || grant.secret_ref == secret_ref {
                    return EvalResult {
                        grant: Some(grant.clone()),
                        policy: Some(policy.clone()),
                    };
                }
            }
        }

        EvalResult {
            grant: None,
            policy: None,
        }
    }

    pub fn policies(&self) -> &[Policy] {
        &self.policies
    }
}

fn conditions_match(policy: &Policy, requester: &str, environment: &str, task: &str) -> bool {
    policy.conditions.iter().any(|c| {
        glob_match(&c.requester, requester)
            && glob_match(&c.environment, environment)
            && glob_match(&c.task, task)
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_engine() -> PolicyEngine {
        let mut engine = PolicyEngine::new();
        engine.load_policies(vec![
            Policy {
                name: "ci-deny-prod".into(),
                description: "CI agents cannot access production".into(),
                priority: 100,
                conditions: vec![Condition {
                    requester: "agent:github-actions".into(),
                    environment: "production".into(),
                    task: "*".into(),
                }],
                grants: vec![],
                deny: true,
            },
            Policy {
                name: "ci-deploy".into(),
                description: "CI deploy access".into(),
                priority: 15,
                conditions: vec![Condition {
                    requester: "agent:github-actions".into(),
                    environment: "ci".into(),
                    task: "deploy".into(),
                }],
                grants: vec![Grant {
                    secret_ref: "op://ci-vault/deploy-key/*".into(),
                    ttl_seconds: 900,
                    max_uses: 1,
                }],
                deny: false,
            },
            Policy {
                name: "dev-team".into(),
                description: "Developer access".into(),
                priority: 10,
                conditions: vec![Condition {
                    requester: "agent:dev-*".into(),
                    environment: "development".into(),
                    task: "*".into(),
                }],
                grants: vec![Grant {
                    secret_ref: "op://dev-vault/*".into(),
                    ttl_seconds: 300,
                    max_uses: 3,
                }],
                deny: false,
            },
            Policy {
                name: "default-deny".into(),
                description: "Deny everything not explicitly allowed".into(),
                priority: 0,
                conditions: vec![Condition {
                    requester: "*".into(),
                    environment: "*".into(),
                    task: "*".into(),
                }],
                grants: vec![],
                deny: true,
            },
        ]);
        engine
    }

    #[test]
    fn ci_denied_from_production() {
        let engine = make_engine();
        let result = engine.evaluate(
            "agent:github-actions",
            "production",
            "deploy",
            "op://prod-vault/db-password/credential",
        );
        assert!(result.grant.is_none());
        assert_eq!(result.policy.unwrap().name, "ci-deny-prod");
    }

    #[test]
    fn ci_allowed_in_ci_environment() {
        let engine = make_engine();
        let result = engine.evaluate(
            "agent:github-actions",
            "ci",
            "deploy",
            "op://ci-vault/deploy-key/credential",
        );
        assert!(result.grant.is_some());
        let grant = result.grant.unwrap();
        assert_eq!(grant.ttl_seconds, 900);
        assert_eq!(grant.max_uses, 1);
        assert_eq!(result.policy.unwrap().name, "ci-deploy");
    }

    #[test]
    fn dev_team_glob_matching() {
        let engine = make_engine();
        let result = engine.evaluate(
            "agent:dev-alice",
            "development",
            "debug",
            "op://dev-vault/api-key",
        );
        assert!(result.grant.is_some());
        assert_eq!(result.grant.unwrap().max_uses, 3);
    }

    #[test]
    fn unknown_agent_denied_by_default() {
        let engine = make_engine();
        let result = engine.evaluate("agent:unknown", "staging", "test", "op://vault/secret/cred");
        assert!(result.grant.is_none());
        assert_eq!(result.policy.unwrap().name, "default-deny");
    }

    #[test]
    fn load_yaml_policies() {
        let dir = tempfile::tempdir().unwrap();
        std::fs::write(
            dir.path().join("test.yaml"),
            r#"
name: test-allow
description: "Test policy"
priority: 10
conditions:
  - requester: "agent:test"
    environment: "test"
    task: "*"
grants:
  - secret_ref: "op://test/*"
    ttl_seconds: 60
    max_uses: 2
deny: false
"#,
        )
        .unwrap();

        let mut engine = PolicyEngine::new();
        let count = engine.load_directory(dir.path()).unwrap();
        assert_eq!(count, 1);

        let result = engine.evaluate("agent:test", "test", "anything", "op://test/key");
        assert!(result.grant.is_some());
    }
}

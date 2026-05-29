use std::net::SocketAddr;
use std::path::PathBuf;
use std::sync::Arc;

use clap::{Parser, Subcommand};
use tonic::transport::Server;
use tracing_subscriber::EnvFilter;

use agentgate_core::crypto::TokenEngine;
use agentgate_core::grants::GrantStore;
use agentgate_core::policy::PolicyEngine;
use agentgate_core::proto::agent_gate_server::AgentGateServer;
use agentgate_core::service::AgentGateService;

#[derive(Parser)]
#[command(name = "agentgate", about = "AgentGate credential broker — Rust core")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Start the gRPC server
    Serve {
        /// Listen address
        #[arg(long, default_value = "0.0.0.0:50051")]
        addr: String,

        /// Policy directory
        #[arg(long, default_value = "policies")]
        policy_dir: PathBuf,

        /// Rate limit per agent per minute
        #[arg(long, default_value_t = 10)]
        rate_limit: u32,

        /// HMAC secret key (hex-encoded, 32+ bytes recommended)
        #[arg(long, env = "AGENTGATE_HMAC_SECRET")]
        hmac_secret: Option<String>,
    },

    /// Validate policy files
    PolicyCheck {
        /// Policy directory
        #[arg(long, default_value = "policies")]
        policy_dir: PathBuf,
    },

    /// Evaluate a single policy request (dry run)
    PolicyEval {
        /// Policy directory
        #[arg(long, default_value = "policies")]
        policy_dir: PathBuf,

        #[arg(long)]
        requester: String,

        #[arg(long)]
        environment: String,

        #[arg(long)]
        task: String,

        #[arg(long)]
        secret_ref: String,
    },
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    tracing_subscriber::fmt()
        .with_env_filter(EnvFilter::from_default_env().add_directive("agentgate=info".parse()?))
        .json()
        .init();

    let cli = Cli::parse();

    match cli.command {
        Commands::Serve {
            addr,
            policy_dir,
            rate_limit,
            hmac_secret,
        } => {
            let token_engine = match hmac_secret {
                Some(hex_key) => {
                    let bytes = hex::decode(&hex_key)?;
                    Arc::new(TokenEngine::new(&bytes))
                }
                None => {
                    tracing::warn!("no HMAC secret provided — generating random key (tokens won't survive restarts)");
                    Arc::new(TokenEngine::from_random()?)
                }
            };

            let mut policy_engine = PolicyEngine::new();
            let count = policy_engine.load_directory(&policy_dir)?;
            tracing::info!(count, dir = %policy_dir.display(), "loaded policies");
            let policy_engine = Arc::new(policy_engine);

            let grant_store = Arc::new(GrantStore::new(rate_limit));

            let expiry_store = grant_store.clone();
            tokio::spawn(async move {
                loop {
                    tokio::time::sleep(tokio::time::Duration::from_secs(30)).await;
                    let expired = expiry_store.expire_stale();
                    if expired > 0 {
                        tracing::info!(expired, "expired stale grants");
                    }
                }
            });

            let service = AgentGateService::new(token_engine, policy_engine, grant_store);
            let socket_addr: SocketAddr = addr.parse()?;

            tracing::info!(%socket_addr, "agentgate-core gRPC server starting");

            Server::builder()
                .add_service(AgentGateServer::new(service))
                .serve(socket_addr)
                .await?;
        }

        Commands::PolicyCheck { policy_dir } => {
            let mut engine = PolicyEngine::new();
            match engine.load_directory(&policy_dir) {
                Ok(count) => {
                    println!("OK: loaded {count} policies from {}", policy_dir.display());
                    for (i, p) in engine.policies().iter().enumerate() {
                        println!(
                            "  [{i}] {} (priority={}, deny={}, conditions={}, grants={})",
                            p.name,
                            p.priority,
                            p.deny,
                            p.conditions.len(),
                            p.grants.len()
                        );
                    }
                }
                Err(e) => {
                    eprintln!("ERROR: {e}");
                    std::process::exit(1);
                }
            }
        }

        Commands::PolicyEval {
            policy_dir,
            requester,
            environment,
            task,
            secret_ref,
        } => {
            let mut engine = PolicyEngine::new();
            engine.load_directory(&policy_dir)?;

            let result = engine.evaluate(&requester, &environment, &task, &secret_ref);

            match result.grant {
                Some(grant) => {
                    let policy = result.policy.unwrap();
                    println!("ALLOWED by policy '{}'", policy.name);
                    println!("  ttl_seconds: {}", grant.ttl_seconds);
                    println!("  max_uses: {}", grant.max_uses);
                    println!("  secret_ref: {}", grant.secret_ref);
                }
                None => {
                    let reason = match result.policy {
                        Some(p) if p.deny => format!("DENIED by policy '{}'", p.name),
                        _ => "DENIED (no matching policy)".to_string(),
                    };
                    println!("{reason}");
                    std::process::exit(1);
                }
            }
        }
    }

    Ok(())
}

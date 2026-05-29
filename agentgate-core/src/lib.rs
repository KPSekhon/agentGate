pub mod crypto;
pub mod grants;
pub mod policy;
pub mod service;

pub mod proto {
    tonic::include_proto!("agentgate");
}

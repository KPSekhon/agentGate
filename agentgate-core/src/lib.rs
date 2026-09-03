pub mod crypto;
pub mod grants;
pub mod policy;
pub mod service;

pub mod proto {
    // tonic generates every RPC as `Result<Response<T>, tonic::Status>`, and
    // Status is ~176 bytes, which trips clippy::result_large_err. The signature
    // is dictated by the generated trait, so the lint is unactionable here.
    #![allow(clippy::result_large_err)]

    tonic::include_proto!("agentgate");
}

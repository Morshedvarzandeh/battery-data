pub mod classify;
pub mod google;
pub mod io;
pub mod model;
pub mod plan;
pub mod taxonomy;

pub const AGENT_NAME: &str = "patent-miner";
pub const AGENT_VERSION: &str = env!("CARGO_PKG_VERSION");
pub const RECORD_SCHEMA_VERSION: &str = "1.0.0";

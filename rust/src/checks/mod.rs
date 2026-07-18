//! Built-in contract checks. Each check function returns a CheckResult.

pub mod auth;
pub mod envelope;
pub mod status;

use serde::Serialize;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "UPPERCASE")]
pub enum Outcome {
    Pass,
    Fail,
    Error,
}

impl Outcome {
    pub fn label(&self) -> &'static str {
        match self {
            Outcome::Pass => "PASSED",
            Outcome::Fail => "FAILED",
            Outcome::Error => "ERROR ",
        }
    }
}

#[derive(Debug, Clone, Serialize)]
pub struct CheckResult {
    pub endpoint: String,
    pub check: String,
    pub outcome: Outcome,
    pub detail: String,
}

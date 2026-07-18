//! Check: response status code matches the endpoint's declared contract.

use crate::checks::{CheckResult, Outcome};
use crate::config::Endpoint;

pub fn check_status(endpoint: &Endpoint, status_code: u16) -> CheckResult {
    let acceptable = endpoint.acceptable_statuses();
    let code = status_code as i64;

    if acceptable.contains(&code) {
        CheckResult {
            endpoint: endpoint.name.clone(),
            check: "status".to_string(),
            outcome: Outcome::Pass,
            detail: format!("got {code}, expected one of {acceptable:?}"),
        }
    } else {
        CheckResult {
            endpoint: endpoint.name.clone(),
            check: "status".to_string(),
            outcome: Outcome::Fail,
            detail: format!("expected status in {acceptable:?}, got {code}"),
        }
    }
}

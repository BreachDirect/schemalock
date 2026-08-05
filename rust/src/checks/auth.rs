//! Check: auth-required routes enforce the auth boundary.
//! Replays the request with no credentials and asserts 401/403 — never a
//! silent 2xx/3xx (bypass), never 404 (leaks resource existence), never 5xx.

use crate::checks::{CheckResult, Outcome};
use crate::config::Endpoint;
use std::time::Duration;

pub fn check_auth_required(
    endpoint: &Endpoint,
    agent: &ureq::Agent,
    base_url: &str,
    _timeout: Duration,
) -> CheckResult {
    let check_name = "auth_required".to_string();
    let url = format!(
        "{}{}",
        base_url.trim_end_matches('/'),
        endpoint.resolved_path()
    );

    let req = agent.request(&endpoint.method, &url);

    let send_result = match &endpoint.body {
        Some(body) => req.send_json(body.clone()),
        None => req.call(),
    };

    let response = match send_result {
        Ok(r) => r,
        Err(ureq::Error::Status(_code, r)) => r,
        Err(ureq::Error::Transport(t)) => {
            return CheckResult {
                endpoint: endpoint.name.clone(),
                check: check_name,
                outcome: Outcome::Error,
                detail: format!("request without credentials failed: {t}"),
            };
        }
    };

    let status = response.status();

    if status == 401 || status == 403 {
        return CheckResult {
            endpoint: endpoint.name.clone(),
            check: check_name,
            outcome: Outcome::Pass,
            detail: format!("unauthenticated request correctly rejected with {status}"),
        };
    }

    let detail = if status == 404 {
        "unauthenticated request returned 404 instead of 401/403 — this leaks resource existence to unauthenticated callers".to_string()
    } else if (200..400).contains(&status) {
        format!(
            "unauthenticated request returned {status} — auth boundary is not enforced (possible auth bypass)"
        )
    } else {
        format!("unauthenticated request returned {status} — expected 401 or 403")
    };

    CheckResult {
        endpoint: endpoint.name.clone(),
        check: check_name,
        outcome: Outcome::Fail,
        detail,
    }
}

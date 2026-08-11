//! Orchestrates HTTP requests against the target and runs applicable checks.

use crate::checks::auth::check_auth_required;
use crate::checks::envelope::check_error_envelope;
use crate::checks::status::check_status;
use crate::checks::{CheckResult, Outcome};
use crate::config::Config;
use std::time::Duration;

pub struct RunnerError(pub String);

fn parse_auth_header(raw: &str) -> Result<(String, String), RunnerError> {
    match raw.split_once(':') {
        Some((name, value)) => Ok((name.trim().to_string(), value.trim().to_string())),
        None => Err(RunnerError(format!(
            "auth_header must be 'Header-Name: value', got: {raw:?}"
        ))),
    }
}

pub struct Runner {
    config: Config,
    base_url: String,
    auth_header: Option<String>,
    timeout: Duration,
}

impl Runner {
    pub fn new(
        config: Config,
        base_url: Option<String>,
        auth_header: Option<String>,
        timeout: Duration,
    ) -> Result<Self, RunnerError> {
        let base_url = base_url
            .or_else(|| config.base_url.clone())
            .ok_or_else(|| {
                RunnerError("base_url must be provided via --base-url or config.base_url".into())
            })?;
        let auth_header = auth_header.or_else(|| config.auth_header.clone());
        Ok(Self {
            config,
            base_url,
            auth_header,
            timeout,
        })
    }

    pub fn run(&self) -> Result<Vec<CheckResult>, RunnerError> {
        // redirects(0): never follow 3xx responses, so an authenticated check
        // cannot forward credentials to a different origin.
        let agent = ureq::AgentBuilder::new()
            .redirects(0)
            .timeout(self.timeout)
            .build();
        let mut results = Vec::new();

        let header_pair = match &self.auth_header {
            Some(raw) => Some(parse_auth_header(raw)?),
            None => None,
        };

        for endpoint in &self.config.endpoints {
            let url = format!(
                "{}{}",
                self.base_url.trim_end_matches('/'),
                endpoint.resolved_path()
            );

            let mut req = agent.request(&endpoint.method, &url);
            if let Some((name, value)) = &header_pair {
                req = req.set(name, value);
            }

            let send_result = match &endpoint.body {
                Some(body) => req.send_json(body.clone()),
                None => req.call(),
            };

            let response = match send_result {
                Ok(r) => r,
                Err(ureq::Error::Status(_code, r)) => r, // non-2xx still gives us a response to check
                Err(ureq::Error::Transport(t)) => {
                    results.push(CheckResult {
                        endpoint: endpoint.name.clone(),
                        check: "request".to_string(),
                        outcome: Outcome::Error,
                        detail: format!("request failed: {t}"),
                    });
                    continue;
                }
            };

            let status_code = response.status();
            let body_text = response.into_string().unwrap_or_default();

            results.push(check_status(endpoint, status_code));

            if let Some(envelope_name) = &endpoint.expect_envelope {
                if status_code >= 400 {
                    let envelope = &self.config.error_envelopes[envelope_name];
                    results.push(check_error_envelope(endpoint, envelope, &body_text));
                }
            }

            if endpoint.auth_required {
                results.push(check_auth_required(endpoint, &agent, &self.base_url));
            }
        }

        Ok(results)
    }
}

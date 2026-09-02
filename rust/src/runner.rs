//! Orchestrates HTTP requests against the target and runs applicable checks.

use crate::checks::auth::check_auth_required;
use crate::checks::envelope::check_error_envelope;
use crate::checks::status::check_status;
use crate::checks::{CheckResult, Outcome};
use crate::config::Config;
use std::io::Read;
use std::time::Duration;

/// Default response body cap (10 MiB), matching Python's
/// `DEFAULT_MAX_RESPONSE_BYTES`.
pub const DEFAULT_MAX_RESPONSE_BYTES: usize = 10 * 1024 * 1024;

pub struct RunnerError(pub String);

/// Read at most `limit + 1` bytes of `response`'s body. Returns the bytes, or
/// `Err((url, limit))` when the body exceeds `limit` — the Rust mirror of
/// Python's `ResponseTooLarge`, including the exact detail format used by the
/// Python runner so cross-language reports stay identical.
fn read_bounded_body(
    response: ureq::Response,
    url: &str,
    limit: usize,
) -> Result<String, (String, usize)> {
    let mut buf: Vec<u8> = Vec::new();
    // Reading one byte past the cap is enough to prove the body is larger
    // than `limit` without buffering an unbounded response (Python reads in
    // 64 KiB chunks and raises once the running total exceeds the cap; the
    // accept/reject boundary is identical: bodies of exactly `limit` bytes
    // pass, larger bodies error).
    let mut reader = response.into_reader().take(limit as u64 + 1);
    match reader.read_to_end(&mut buf) {
        Ok(_) if buf.len() > limit => Err((url.to_string(), limit)),
        Ok(_) => Ok(String::from_utf8_lossy(&buf).into_owned()),
        Err(_) => Ok(String::new()),
    }
}

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
    max_response_bytes: usize,
}

impl Runner {
    pub fn new(
        config: Config,
        base_url: Option<String>,
        auth_header: Option<String>,
        timeout: Duration,
        max_response_bytes: Option<usize>,
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
            max_response_bytes: max_response_bytes.unwrap_or(DEFAULT_MAX_RESPONSE_BYTES),
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
            let body_text = match read_bounded_body(response, &url, self.max_response_bytes) {
                Ok(text) => text,
                Err((url, limit)) => {
                    // Mirrors Python: outcome ERROR, check "request", and the
                    // ResponseTooLarge tuple rendered the same way CPython
                    // str()s a two-arg exception.
                    results.push(CheckResult {
                        endpoint: endpoint.name.clone(),
                        check: "request".to_string(),
                        outcome: Outcome::Error,
                        detail: format!("response exceeded size limit: ('{url}', {limit})"),
                    });
                    continue;
                }
            };

            results.push(check_status(endpoint, status_code));

            if let Some(envelope_name) = &endpoint.expect_envelope {
                if status_code >= 400 {
                    let envelope = &self.config.error_envelopes[envelope_name];
                    results.push(check_error_envelope(endpoint, envelope, &body_text));
                }
            }

            if endpoint.auth_required {
                results.push(check_auth_required(
                    endpoint,
                    &agent,
                    &self.base_url,
                    self.max_response_bytes,
                ));
            }
        }

        Ok(results)
    }
}

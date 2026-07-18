//! Pytest-style console output and JSON report generation.

use crate::checks::{CheckResult, Outcome};
use serde::Serialize;
use std::fs::File;
use std::io::Write;

pub fn render_console(config_name: &str, results: &[CheckResult]) -> String {
    let mut lines = vec![format!("SchemaLock — {config_name}"), String::new()];

    for r in results {
        lines.push(format!("{}  {} :: {} — {}", r.outcome.label(), r.endpoint, r.check, r.detail));
    }

    let passed = results.iter().filter(|r| r.outcome == Outcome::Pass).count();
    let failed = results.iter().filter(|r| r.outcome == Outcome::Fail).count();
    let errored = results.iter().filter(|r| r.outcome == Outcome::Error).count();

    lines.push(String::new());
    lines.push(format!(
        "{} checks: {passed} passed, {failed} failed, {errored} errored",
        results.len()
    ));

    lines.join("\n")
}

#[derive(Serialize)]
struct Summary {
    total: usize,
    passed: usize,
    failed: usize,
    errored: usize,
}

#[derive(Serialize)]
struct JsonReport<'a> {
    config_name: &'a str,
    summary: Summary,
    results: &'a [CheckResult],
}

pub fn render_json(
    config_name: &str,
    results: &[CheckResult],
    path: &str,
) -> std::io::Result<()> {
    let summary = Summary {
        total: results.len(),
        passed: results.iter().filter(|r| r.outcome == Outcome::Pass).count(),
        failed: results.iter().filter(|r| r.outcome == Outcome::Fail).count(),
        errored: results.iter().filter(|r| r.outcome == Outcome::Error).count(),
    };
    let report = JsonReport { config_name, summary, results };
    let json = serde_json::to_string_pretty(&report).expect("serialize report");
    let mut file = File::create(path)?;
    file.write_all(json.as_bytes())
}

pub fn exit_code(results: &[CheckResult]) -> i32 {
    if results.iter().all(|r| r.outcome == Outcome::Pass) { 0 } else { 1 }
}

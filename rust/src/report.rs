//! Pytest-style console output and JSON report generation.

use crate::checks::{CheckResult, Outcome};
use serde::Serialize;
use std::fs::File;
use std::io::Write;

pub fn render_console(config_name: &str, results: &[CheckResult]) -> String {
    let mut lines = vec![format!("SchemaLock — {config_name}"), String::new()];

    for r in results {
        lines.push(format!(
            "{}  {} :: {} — {}",
            r.outcome.label(),
            r.endpoint,
            r.check,
            r.detail
        ));
    }

    let passed = results
        .iter()
        .filter(|r| r.outcome == Outcome::Pass)
        .count();
    let failed = results
        .iter()
        .filter(|r| r.outcome == Outcome::Fail)
        .count();
    let errored = results
        .iter()
        .filter(|r| r.outcome == Outcome::Error)
        .count();

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

pub fn render_json(config_name: &str, results: &[CheckResult], path: &str) -> std::io::Result<()> {
    let summary = Summary {
        total: results.len(),
        passed: results
            .iter()
            .filter(|r| r.outcome == Outcome::Pass)
            .count(),
        failed: results
            .iter()
            .filter(|r| r.outcome == Outcome::Fail)
            .count(),
        errored: results
            .iter()
            .filter(|r| r.outcome == Outcome::Error)
            .count(),
    };
    let report = JsonReport {
        config_name,
        summary,
        results,
    };
    let json = serde_json::to_string_pretty(&report).expect("serialize report");
    let mut file = File::create(path)?;
    file.write_all(json.as_bytes())
}

pub fn exit_code(results: &[CheckResult]) -> i32 {
    if results.iter().all(|r| r.outcome == Outcome::Pass) {
        0
    } else {
        1
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::checks::{CheckResult, Outcome};

    fn result(outcome: Outcome, detail: &str) -> CheckResult {
        CheckResult {
            endpoint: "/health".into(),
            check: "status".into(),
            outcome,
            detail: detail.into(),
        }
    }

    #[test]
    fn console_has_pytest_style_lines() {
        let results = vec![
            result(Outcome::Pass, "200 OK"),
            result(Outcome::Fail, "200 OK"),
            result(Outcome::Error, "200 OK"),
        ];
        let out = render_console("demo", &results);
        assert!(out.starts_with("SchemaLock — demo"));
        assert!(out.contains("PASSED  /health :: status — 200 OK"));
        assert!(out.contains("FAILED  /health :: status — 200 OK"));
        assert!(out.contains("ERROR   /health :: status — 200 OK"));
        assert!(out.contains("3 checks: 1 passed, 1 failed, 1 errored"));
    }

    #[test]
    fn console_summary_counts() {
        let results = vec![
            result(Outcome::Pass, "ok"),
            result(Outcome::Pass, "ok"),
            result(Outcome::Error, "nope"),
        ];
        assert!(
            render_console("demo", &results).contains("3 checks: 2 passed, 0 failed, 1 errored")
        );
    }

    #[test]
    fn json_report_summary_and_details() {
        let results = vec![
            result(Outcome::Pass, "ok"),
            result(Outcome::Error, "refused"),
        ];
        let path =
            std::env::temp_dir().join(format!("schemalock-report-{}.json", std::process::id()));
        render_json("demo", &results, path.to_str().unwrap()).unwrap();
        let text = std::fs::read_to_string(&path).unwrap();
        let _ = std::fs::remove_file(&path);

        let json: serde_json::Value = serde_json::from_str(&text).unwrap();
        assert_eq!(json["config_name"], "demo");
        assert_eq!(json["summary"]["total"], 2);
        assert_eq!(json["summary"]["passed"], 1);
        assert_eq!(json["summary"]["failed"], 0);
        assert_eq!(json["summary"]["errored"], 1);
        assert_eq!(json["results"][1]["outcome"], "ERROR");
        assert_eq!(json["results"][1]["detail"], "refused");
    }

    #[test]
    fn exit_code_zero_only_when_all_pass() {
        assert_eq!(exit_code(&[result(Outcome::Pass, "ok")]), 0);
        assert_eq!(
            exit_code(&[result(Outcome::Pass, "ok"), result(Outcome::Fail, "no")]),
            1
        );
        assert_eq!(
            exit_code(&[result(Outcome::Pass, "ok"), result(Outcome::Error, "oops")]),
            1
        );
        assert_eq!(exit_code(&[]), 0);
    }
}

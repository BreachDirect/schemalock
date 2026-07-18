use schemalock::checks::envelope::check_error_envelope;
use schemalock::checks::status::check_status;
use schemalock::checks::Outcome;
use schemalock::config::{parse_config, ConfigRaw, ErrorEnvelope};
use std::collections::HashMap;

fn make_endpoint(status_yaml: &str) -> schemalock::config::Endpoint {
    let yaml = format!(
        r#"
name: "Test"
base_url: "http://localhost:8000"
endpoints:
  - name: e
    method: GET
    path: /x
    expect:
      status: {status_yaml}
"#
    );
    let raw: ConfigRaw = serde_yaml::from_str(&yaml).unwrap();
    parse_config(raw).unwrap().endpoints.into_iter().next().unwrap()
}

#[test]
fn status_pass_on_exact_match() {
    let ep = make_endpoint("200");
    let result = check_status(&ep, 200);
    assert_eq!(result.outcome, Outcome::Pass);
}

#[test]
fn status_fail_on_mismatch() {
    let ep = make_endpoint("200");
    let result = check_status(&ep, 500);
    assert_eq!(result.outcome, Outcome::Fail);
    assert!(result.detail.contains("500"));
}

#[test]
fn status_pass_when_in_list() {
    let ep = make_endpoint("[204, 409]");
    let result = check_status(&ep, 409);
    assert_eq!(result.outcome, Outcome::Pass);
}

fn standard_envelope() -> ErrorEnvelope {
    let mut field_types = HashMap::new();
    field_types.insert("error".to_string(), "boolean".to_string());
    field_types.insert("message".to_string(), "string".to_string());
    field_types.insert("code".to_string(), "string".to_string());
    ErrorEnvelope {
        name: "standard".to_string(),
        required_fields: vec!["error".to_string(), "message".to_string(), "code".to_string()],
        field_types,
    }
}

#[test]
fn envelope_pass_when_shape_matches() {
    let ep = make_endpoint("404");
    let envelope = standard_envelope();
    let body = r#"{"error": true, "message": "not found", "code": "NOT_FOUND"}"#;
    let result = check_error_envelope(&ep, &envelope, body);
    assert_eq!(result.outcome, Outcome::Pass);
}

#[test]
fn envelope_fail_on_missing_field() {
    let ep = make_endpoint("404");
    let envelope = standard_envelope();
    let body = r#"{"error": true, "code": "NOT_FOUND"}"#; // missing "message"
    let result = check_error_envelope(&ep, &envelope, body);
    assert_eq!(result.outcome, Outcome::Fail);
    assert!(result.detail.contains("message"));
}

#[test]
fn envelope_fail_on_type_drift() {
    let ep = make_endpoint("404");
    let envelope = standard_envelope();
    let body = r#"{"error": "yes", "message": "not found", "code": "NOT_FOUND"}"#;
    let result = check_error_envelope(&ep, &envelope, body);
    assert_eq!(result.outcome, Outcome::Fail);
    assert!(result.detail.contains("error"));
}

#[test]
fn envelope_pass_allows_extra_fields() {
    let ep = make_endpoint("404");
    let envelope = standard_envelope();
    let body =
        r#"{"error": true, "message": "not found", "code": "NOT_FOUND", "trace_id": "abc123"}"#;
    let result = check_error_envelope(&ep, &envelope, body);
    assert_eq!(result.outcome, Outcome::Pass);
}

#[test]
fn envelope_fail_on_non_json_body() {
    let ep = make_endpoint("404");
    let envelope = standard_envelope();
    let result = check_error_envelope(&ep, &envelope, "not json");
    assert_eq!(result.outcome, Outcome::Fail);
}

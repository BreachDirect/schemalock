//! Check: error responses keep a stable envelope shape (required fields + types).
//! Forgiving on extra/additive fields; strict on missing fields or type drift.

use crate::checks::{CheckResult, Outcome};
use crate::config::{Endpoint, ErrorEnvelope};
use serde_json::Value;

/// Maps a serde_json::Value to the equivalent Python `type(...).__name__` so the
/// type-drift detail string matches the Python implementation exactly.
fn py_type_name(value: &Value) -> &'static str {
    match value {
        Value::Null => "NoneType",
        Value::Bool(_) => "bool",
        Value::Number(n) => {
            if n.is_i64() || n.is_u64() {
                "int"
            } else {
                "float"
            }
        }
        Value::String(_) => "str",
        Value::Array(_) => "list",
        Value::Object(_) => "dict",
    }
}

fn type_ok(value: &Value, type_name: &str) -> bool {
    match type_name {
        "string" => value.is_string(),
        "number" => value.is_number(),
        "boolean" => value.is_boolean(),
        "object" => value.is_object(),
        "array" => value.is_array(),
        "null" => value.is_null(),
        _ => true,
    }
}

pub fn check_error_envelope(
    endpoint: &Endpoint,
    envelope: &ErrorEnvelope,
    body_text: &str,
) -> CheckResult {
    let check_name = "error_envelope".to_string();

    let body: Value = match serde_json::from_str(body_text) {
        Ok(v) => v,
        Err(_) => {
            return CheckResult {
                endpoint: endpoint.name.clone(),
                check: check_name,
                outcome: Outcome::Fail,
                detail: "response body is not valid JSON; error envelope cannot be checked"
                    .to_string(),
            };
        }
    };

    let Some(obj) = body.as_object() else {
        let got = match &body {
            Value::Array(_) => "array",
            Value::String(_) => "string",
            Value::Number(_) => "number",
            Value::Bool(_) => "boolean",
            Value::Null => "null",
            Value::Object(_) => unreachable!(),
        };
        return CheckResult {
            endpoint: endpoint.name.clone(),
            check: check_name,
            outcome: Outcome::Fail,
            detail: format!(
                "expected a JSON object for envelope '{}', got {got}",
                envelope.name
            ),
        };
    };

    let missing: Vec<&String> = envelope
        .required_fields
        .iter()
        .filter(|f| !obj.contains_key(*f))
        .collect();
    if !missing.is_empty() {
        let missing_list = missing
            .iter()
            .map(|f| format!("'{f}'"))
            .collect::<Vec<_>>()
            .join(", ");
        return CheckResult {
            endpoint: endpoint.name.clone(),
            check: check_name,
            outcome: Outcome::Fail,
            detail: format!(
                "envelope '{}' missing required field(s): [{missing_list}]",
                envelope.name
            ),
        };
    }

    let mut type_errors = Vec::new();
    // Iterate in sorted key order so detail strings are deterministic across
    // runs and platforms (HashMap iteration order is not).
    let mut fields: Vec<(&String, &String)> = envelope.field_types.iter().collect();
    fields.sort_by(|a, b| a.0.cmp(b.0));
    for (fname, ftype) in fields {
        if let Some(value) = obj.get(fname) {
            if !type_ok(value, ftype) {
                type_errors.push(format!(
                    "{fname}: expected {ftype}, got {}",
                    py_type_name(value)
                ));
            }
        }
    }
    if !type_errors.is_empty() {
        return CheckResult {
            endpoint: endpoint.name.clone(),
            check: check_name,
            outcome: Outcome::Fail,
            detail: format!(
                "envelope '{}' field type drift: {}",
                envelope.name,
                type_errors.join("; ")
            ),
        };
    }

    CheckResult {
        endpoint: endpoint.name.clone(),
        check: check_name,
        outcome: Outcome::Pass,
        detail: format!("envelope '{}' shape stable", envelope.name),
    }
}

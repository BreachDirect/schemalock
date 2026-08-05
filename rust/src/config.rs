//! Load and validate schemalock.yaml into typed config structs.
//! Mirrors the Python `config.py` module: same validation rules, same
//! precise-path error messages, same data shape.

use serde::Deserialize;
use std::collections::HashMap;
use std::error::Error;
use std::fmt;

const VALID_METHODS: [&str; 5] = ["GET", "POST", "PUT", "PATCH", "DELETE"];
const VALID_TYPES: [&str; 6] = ["string", "number", "boolean", "object", "array", "null"];

#[derive(Debug)]
pub struct ConfigError(pub String);

impl fmt::Display for ConfigError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.0)
    }
}
impl Error for ConfigError {}

fn err(path: &str, msg: &str) -> ConfigError {
    ConfigError(format!("{path}: {msg}"))
}

// ---- Raw (as-parsed-from-YAML) shapes ----

#[derive(Debug, Deserialize, Clone)]
#[serde(untagged)]
pub enum StatusExpectation {
    Single(i64),
    Multiple(Vec<i64>),
}

impl StatusExpectation {
    pub fn acceptable(&self) -> Vec<i64> {
        match self {
            StatusExpectation::Single(s) => vec![*s],
            StatusExpectation::Multiple(v) => v.clone(),
        }
    }
}

#[derive(Debug, Deserialize, Clone)]
pub struct ExpectRaw {
    pub status: Option<serde_yaml::Value>,
    pub error_envelope: Option<String>,
}

#[derive(Debug, Deserialize, Clone)]
pub struct EndpointRaw {
    pub name: Option<String>,
    pub method: Option<String>,
    pub path: Option<String>,
    pub body: Option<serde_json::Value>,
    pub auth_required: Option<bool>,
    pub expect: Option<ExpectRaw>,
    pub path_params: Option<HashMap<String, String>>,
}

#[derive(Debug, Deserialize, Clone, Default)]
pub struct ErrorEnvelopeRaw {
    pub required_fields: Option<Vec<String>>,
    pub field_types: Option<HashMap<String, String>>,
}

#[derive(Debug, Deserialize)]
pub struct ConfigRaw {
    pub name: Option<String>,
    pub base_url: Option<String>,
    pub auth_header: Option<String>,
    pub error_envelopes: Option<HashMap<String, ErrorEnvelopeRaw>>,
    pub endpoints: Option<Vec<EndpointRaw>>,
}

// ---- Validated shapes used by the rest of the program ----

#[derive(Debug, Clone)]
pub struct ErrorEnvelope {
    pub name: String,
    pub required_fields: Vec<String>,
    pub field_types: HashMap<String, String>,
}

#[derive(Debug, Clone)]
pub struct Endpoint {
    pub name: String,
    pub method: String,
    pub path: String,
    pub body: Option<serde_json::Value>,
    pub auth_required: bool,
    pub expect_status: StatusExpectation,
    pub expect_envelope: Option<String>,
    pub path_params: HashMap<String, String>,
}

impl Endpoint {
    pub fn acceptable_statuses(&self) -> Vec<i64> {
        self.expect_status.acceptable()
    }

    pub fn resolved_path(&self) -> String {
        let mut p = self.path.clone();
        for (k, v) in &self.path_params {
            p = p.replace(&format!("{{{k}}}"), v);
        }
        p
    }
}

#[derive(Debug, Clone)]
pub struct Config {
    pub name: String,
    pub base_url: Option<String>,
    pub auth_header: Option<String>,
    pub error_envelopes: HashMap<String, ErrorEnvelope>,
    pub endpoints: Vec<Endpoint>,
}

fn parse_error_envelopes(
    raw: Option<HashMap<String, ErrorEnvelopeRaw>>,
) -> Result<HashMap<String, ErrorEnvelope>, ConfigError> {
    let mut out = HashMap::new();
    let Some(raw) = raw else { return Ok(out) };

    for (name, spec) in raw {
        let required_fields = spec.required_fields.unwrap_or_default();
        let field_types = spec.field_types.unwrap_or_default();
        for (fname, ftype) in &field_types {
            if !VALID_TYPES.contains(&ftype.as_str()) {
                return Err(err(
                    &format!("error_envelopes.{name}.field_types.{fname}"),
                    &format!("'{ftype}' is not one of {VALID_TYPES:?}"),
                ));
            }
        }
        out.insert(
            name.clone(),
            ErrorEnvelope {
                name,
                required_fields,
                field_types,
            },
        );
    }
    Ok(out)
}

fn yaml_status_to_expectation(
    value: &serde_yaml::Value,
    path: &str,
) -> Result<StatusExpectation, ConfigError> {
    match value {
        serde_yaml::Value::Number(n) if n.is_i64() => {
            Ok(StatusExpectation::Single(n.as_i64().unwrap()))
        }
        serde_yaml::Value::Sequence(seq) => {
            let mut statuses = Vec::new();
            for item in seq {
                match item.as_i64() {
                    Some(v) => statuses.push(v),
                    None => {
                        return Err(err(path, "all list items must be integers"));
                    }
                }
            }
            Ok(StatusExpectation::Multiple(statuses))
        }
        _ => Err(err(path, "expected int or list[int]")),
    }
}

fn parse_endpoint(
    raw: EndpointRaw,
    idx: usize,
    known_envelopes: &HashMap<String, ErrorEnvelope>,
) -> Result<Endpoint, ConfigError> {
    let path = format!("endpoints[{idx}]");

    let name = raw
        .name
        .ok_or_else(|| err(&path, "name: missing required field"))?;
    let method = raw
        .method
        .ok_or_else(|| err(&path, "method: missing required field"))?
        .to_uppercase();
    if !VALID_METHODS.contains(&method.as_str()) {
        return Err(err(
            &format!("{path}.method"),
            &format!("'{method}' must be one of {VALID_METHODS:?}"),
        ));
    }
    let ep_path = raw
        .path
        .ok_or_else(|| err(&path, "path: missing required field"))?;

    let expect = raw
        .expect
        .ok_or_else(|| err(&format!("{path}.expect.status"), "missing required field"))?;
    let status_value = expect
        .status
        .ok_or_else(|| err(&format!("{path}.expect.status"), "missing required field"))?;
    let expect_status =
        yaml_status_to_expectation(&status_value, &format!("{path}.expect.status"))?;

    let envelope_name = expect.error_envelope;
    if let Some(ref en) = envelope_name {
        if !known_envelopes.contains_key(en) {
            return Err(err(
                &format!("{path}.expect.error_envelope"),
                &format!("'{en}' is not defined in error_envelopes"),
            ));
        }
    }

    Ok(Endpoint {
        name,
        method,
        path: ep_path,
        body: raw.body,
        auth_required: raw.auth_required.unwrap_or(false),
        expect_status,
        expect_envelope: envelope_name,
        path_params: raw.path_params.unwrap_or_default(),
    })
}

pub fn parse_config(raw: ConfigRaw) -> Result<Config, ConfigError> {
    let name = raw
        .name
        .unwrap_or_else(|| "SchemaLock contract".to_string());
    let error_envelopes = parse_error_envelopes(raw.error_envelopes)?;

    let raw_endpoints = raw
        .endpoints
        .ok_or_else(|| err("endpoints", "expected a non-empty list"))?;
    if raw_endpoints.is_empty() {
        return Err(err("endpoints", "expected a non-empty list"));
    }

    let mut endpoints = Vec::with_capacity(raw_endpoints.len());
    for (i, ep) in raw_endpoints.into_iter().enumerate() {
        endpoints.push(parse_endpoint(ep, i, &error_envelopes)?);
    }

    Ok(Config {
        name,
        base_url: raw.base_url,
        auth_header: raw.auth_header,
        error_envelopes,
        endpoints,
    })
}

pub fn load_config(path: &str) -> Result<Config, ConfigError> {
    let contents = std::fs::read_to_string(path)
        .map_err(|_| ConfigError(format!("config file not found: {path}")))?;

    let raw: ConfigRaw = serde_yaml::from_str(&contents)
        .map_err(|e| ConfigError(format!("invalid YAML in {path}: {e}")))?;

    parse_config(raw)
}

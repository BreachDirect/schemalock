use schemalock::config::{parse_config, ConfigRaw};

fn minimal_valid_yaml() -> &'static str {
    r#"
name: "Test contract"
base_url: "http://localhost:8000"
endpoints:
  - name: health
    method: GET
    path: /health
    expect:
      status: 200
"#
}

fn parse(yaml: &str) -> Result<schemalock::config::Config, schemalock::config::ConfigError> {
    let raw: ConfigRaw = serde_yaml::from_str(yaml).expect("valid yaml syntax");
    parse_config(raw)
}

#[test]
fn parses_minimal_valid_config() {
    let cfg = parse(minimal_valid_yaml()).expect("should parse");
    assert_eq!(cfg.name, "Test contract");
    assert_eq!(cfg.base_url.as_deref(), Some("http://localhost:8000"));
    assert_eq!(cfg.endpoints.len(), 1);
    assert_eq!(cfg.endpoints[0].method, "GET");
}

#[test]
fn lowercases_method_is_uppercased() {
    let yaml = minimal_valid_yaml().replace("method: GET", "method: get");
    let cfg = parse(&yaml).expect("should parse");
    assert_eq!(cfg.endpoints[0].method, "GET");
}

#[test]
fn rejects_invalid_method() {
    let yaml = minimal_valid_yaml().replace("method: GET", "method: FETCH");
    let err = parse(&yaml).unwrap_err();
    assert!(err.0.contains("method"), "{}", err.0);
}

#[test]
fn rejects_empty_endpoints_list() {
    let yaml = r#"
name: "Test"
base_url: "http://localhost:8000"
endpoints: []
"#;
    let err = parse(yaml).unwrap_err();
    assert!(err.0.contains("endpoints"), "{}", err.0);
}

#[test]
fn rejects_missing_expect_status() {
    let yaml = r#"
name: "Test"
base_url: "http://localhost:8000"
endpoints:
  - name: health
    method: GET
    path: /health
    expect: {}
"#;
    let err = parse(yaml).unwrap_err();
    assert!(err.0.contains("status"), "{}", err.0);
}

#[test]
fn accepts_status_list() {
    let yaml = minimal_valid_yaml().replace("status: 200", "status: [200, 204]");
    let cfg = parse(&yaml).expect("should parse");
    assert_eq!(cfg.endpoints[0].acceptable_statuses(), vec![200, 204]);
}

#[test]
fn rejects_unknown_error_envelope_reference() {
    let yaml = minimal_valid_yaml().replace(
        "status: 200",
        "status: 200\n      error_envelope: does_not_exist",
    );
    let err = parse(&yaml).unwrap_err();
    assert!(err.0.contains("error_envelope"), "{}", err.0);
}

#[test]
fn accepts_known_error_envelope_reference() {
    let yaml = r#"
name: "Test"
base_url: "http://localhost:8000"
error_envelopes:
  standard:
    required_fields: ["error", "message"]
    field_types:
      error: "boolean"
endpoints:
  - name: health
    method: GET
    path: /health
    expect:
      status: 404
      error_envelope: standard
"#;
    let cfg = parse(yaml).expect("should parse");
    assert_eq!(
        cfg.endpoints[0].expect_envelope.as_deref(),
        Some("standard")
    );
    assert_eq!(
        cfg.error_envelopes["standard"].required_fields,
        vec!["error".to_string(), "message".to_string()]
    );
}

#[test]
fn rejects_invalid_field_type_name() {
    let yaml = r#"
name: "Test"
base_url: "http://localhost:8000"
error_envelopes:
  standard:
    field_types:
      error: "boolint"
endpoints:
  - name: health
    method: GET
    path: /health
    expect:
      status: 200
"#;
    let err = parse(yaml).unwrap_err();
    assert!(err.0.contains("field_types"), "{}", err.0);
}

#[test]
fn path_params_resolve() {
    let yaml = r#"
name: "Test"
base_url: "http://localhost:8000"
endpoints:
  - name: get_escrow
    method: GET
    path: /escrows/{id}
    path_params:
      id: esc_123
    expect:
      status: 200
"#;
    let cfg = parse(yaml).expect("should parse");
    assert_eq!(cfg.endpoints[0].resolved_path(), "/escrows/esc_123");
}

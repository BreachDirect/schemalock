import pytest
from schemalock.config import ConfigError, parse_config


def minimal_valid():
    return {
        "name": "Test contract",
        "base_url": "http://localhost:8000",
        "endpoints": [
            {"name": "health", "method": "GET", "path": "/health", "expect": {"status": 200}}
        ],
    }


def test_parses_minimal_valid_config():
    cfg = parse_config(minimal_valid())
    assert cfg.name == "Test contract"
    assert cfg.base_url == "http://localhost:8000"
    assert len(cfg.endpoints) == 1
    assert cfg.endpoints[0].method == "GET"


def test_lowercases_are_uppercased_for_method():
    raw = minimal_valid()
    raw["endpoints"][0]["method"] = "get"
    cfg = parse_config(raw)
    assert cfg.endpoints[0].method == "GET"


def test_rejects_invalid_method():
    raw = minimal_valid()
    raw["endpoints"][0]["method"] = "FETCH"
    with pytest.raises(ConfigError, match="method"):
        parse_config(raw)


def test_rejects_missing_endpoints():
    raw = minimal_valid()
    del raw["endpoints"]
    with pytest.raises(ConfigError, match="endpoints"):
        parse_config(raw)


def test_rejects_empty_endpoints_list():
    raw = minimal_valid()
    raw["endpoints"] = []
    with pytest.raises(ConfigError, match="endpoints"):
        parse_config(raw)


def test_rejects_missing_expect_status():
    raw = minimal_valid()
    del raw["endpoints"][0]["expect"]["status"]
    with pytest.raises(ConfigError, match="status"):
        parse_config(raw)


def test_accepts_status_list():
    raw = minimal_valid()
    raw["endpoints"][0]["expect"]["status"] = [200, 204]
    cfg = parse_config(raw)
    assert cfg.endpoints[0].acceptable_statuses() == [200, 204]


def test_rejects_unknown_error_envelope_reference():
    raw = minimal_valid()
    raw["endpoints"][0]["expect"]["error_envelope"] = "does_not_exist"
    with pytest.raises(ConfigError, match="error_envelope"):
        parse_config(raw)


def test_accepts_known_error_envelope_reference():
    raw = minimal_valid()
    raw["error_envelopes"] = {
        "standard": {"required_fields": ["error", "message"], "field_types": {"error": "boolean"}}
    }
    raw["endpoints"][0]["expect"]["error_envelope"] = "standard"
    cfg = parse_config(raw)
    assert cfg.endpoints[0].expect_envelope == "standard"
    assert cfg.error_envelopes["standard"].required_fields == ["error", "message"]


def test_rejects_invalid_field_type_name():
    raw = minimal_valid()
    raw["error_envelopes"] = {"standard": {"field_types": {"error": "boolint"}}}
    with pytest.raises(ConfigError, match="field_types"):
        parse_config(raw)


def test_path_params_resolve():
    raw = minimal_valid()
    raw["endpoints"][0]["path"] = "/escrows/{id}"
    raw["endpoints"][0]["path_params"] = {"id": "esc_123"}
    cfg = parse_config(raw)
    assert cfg.endpoints[0].resolved_path() == "/escrows/esc_123"


def test_root_must_be_mapping():
    with pytest.raises(ConfigError, match="mapping"):
        parse_config(["not", "a", "mapping"])

import json

import pytest
import yaml
from schemalock.config import parse_config
from schemalock.scaffold import (
    CaptureError,
    build_contract,
    parse_capture,
    render_yaml,
    scaffold,
)


def _capture(endpoints, version=1, **extra):
    return {"version": version, "endpoints": endpoints, **extra}


def _ep(method="GET", path="/escrows/{id}", origin="http://127.0.0.1:8000", **extra):
    base = {"method": method, "path": path, "origin": origin}
    base.update(extra)
    return base


def _obs(status, authed=False, body=None, count=1):
    return {"status": status, "authed": authed, "body": body, "count": count}


def _scaffold_dict(capture):
    return build_contract(parse_capture(capture))


def test_infers_envelope_and_statuses():
    capture = _capture(
        [
            _ep(
                path_params={"id": "esc_123"},
                observations=[
                    _obs(200, authed=True, body={"id": "esc_123", "status": "PENDING"}),
                    _obs(
                        404,
                        authed=True,
                        body={"error": True, "message": "not found", "code": "NOT_FOUND"},
                    ),
                ],
            )
        ]
    )
    contract = _scaffold_dict(capture)

    assert contract["base_url"] == "http://127.0.0.1:8000"
    assert contract["auth_header"] == "Authorization: Bearer <your-token>"

    env = contract["error_envelopes"]["standard"]
    assert sorted(env["required_fields"]) == ["code", "error", "message"]
    assert env["field_types"]["error"] == "boolean"
    assert env["field_types"]["message"] == "string"
    assert env["field_types"]["code"] == "string"

    ep = contract["endpoints"][0]
    assert ep["name"] == "get_escrows_id"
    assert ep["method"] == "GET"
    assert ep["path"] == "/escrows/{id}"
    assert ep["path_params"] == {"id": "esc_123"}
    assert ep["auth_required"] is False
    assert ep["expect"]["status"] == [200, 404]
    assert ep["expect"]["error_envelope"] == "standard"


def test_auth_required_from_observed_401():
    capture = _capture(
        [
            _ep(
                observations=[
                    _obs(201, authed=True, body={"id": "esc_new"}),
                    _obs(
                        401,
                        authed=False,
                        body={"error": True, "message": "nope", "code": "UNAUTHORIZED"},
                    ),
                ]
            )
        ]
    )
    contract = _scaffold_dict(capture)
    assert contract["endpoints"][0]["auth_required"] is True


def test_auth_required_from_probe():
    capture = _capture(
        [
            _ep(
                observations=[_obs(200, authed=True, body={"ok": True})],
                auth_probe={"status": 401},
            )
        ]
    )
    contract = _scaffold_dict(capture)
    assert contract["endpoints"][0]["auth_required"] is True


def test_probe_not_enforcing_auth_warns(tmp_path):
    capture = _capture(
        [
            _ep(
                observations=[_obs(200, authed=True, body={"ok": True})],
                auth_probe={"status": 200},
            )
        ]
    )
    cap_file = tmp_path / "capture.json"
    cap_file.write_text(json.dumps(capture))
    yaml_text, notes = scaffold(str(cap_file))
    assert "does not enforce an auth boundary" in notes[0]
    assert "auth_required: false" in yaml_text


def test_multiple_origins_omits_base_url(tmp_path):
    capture = _capture(
        [
            _ep(origin="http://api-a.local", observations=[_obs(200, body={})]),
            _ep(origin="http://api-b.local", observations=[_obs(201, body={})]),
        ]
    )
    cap_file = tmp_path / "capture.json"
    cap_file.write_text(json.dumps(capture))
    yaml_text, notes = scaffold(str(cap_file))
    assert "base_url:" not in yaml_text.split("endpoints:")[0]
    assert "multiple origins" in notes[0]


def test_non_dict_error_body_skipped():
    capture = _capture([_ep(observations=[_obs(500, authed=True, body="internal error text")])])
    contract = _scaffold_dict(capture)
    assert contract.get("error_envelopes") is None
    assert "error_envelope" not in contract["endpoints"][0]["expect"]


def test_unique_names_for_duplicate_paths():
    capture = _capture(
        [
            _ep(observations=[_obs(200, body={})]),
            _ep(observations=[_obs(404, body={"error": True, "message": "x", "code": "NF"})]),
        ]
    )
    contract = _scaffold_dict(capture)
    names = [ep["name"] for ep in contract["endpoints"]]
    assert names[0] == "get_escrows_id"
    assert names[1] == "get_escrows_id_2"
    assert len(set(names)) == 2


def test_multiple_envelope_shapes_numbered():
    capture = _capture(
        [
            _ep(
                path="/a",
                observations=[_obs(400, body={"error": True, "message": "x", "code": "X"})],
            ),
            _ep(path="/b", observations=[_obs(400, body={"detail": "y"})]),
        ]
    )
    contract = _scaffold_dict(capture)
    assert sorted(contract["error_envelopes"]) == ["error_v1", "error_v2"]


def test_scaffold_output_roundtrips_through_config_loader(tmp_path):
    capture = _capture(
        [
            _ep(
                path_params={"id": "esc_123"},
                observations=[
                    _obs(200, authed=True, body={"id": "esc_123"}),
                    _obs(
                        401,
                        authed=False,
                        body={"error": True, "message": "nope", "code": "UNAUTHORIZED"},
                    ),
                ],
            ),
            _ep(
                method="POST",
                path="/escrows",
                request_body={"amount": 500},
                observations=[
                    _obs(201, authed=True, body={"id": "esc_new"}),
                    _obs(
                        401,
                        authed=False,
                        body={"error": True, "message": "nope", "code": "UNAUTHORIZED"},
                    ),
                ],
            ),
        ]
    )
    cap_file = tmp_path / "capture.json"
    cap_file.write_text(json.dumps(capture))
    yaml_text, _ = scaffold(str(cap_file))

    config = parse_config(yaml.safe_load(yaml_text))
    assert config.name == "Recorded API contract"
    assert config.base_url == "http://127.0.0.1:8000"
    assert len(config.endpoints) == 2
    post = config.endpoints[1]
    assert post.method == "POST"
    assert post.body == {"amount": 500}
    assert post.auth_required is True
    assert "standard" in config.error_envelopes


def test_bad_version_rejected():
    with pytest.raises(CaptureError, match="unsupported capture version"):
        parse_capture(_capture([_ep(observations=[_obs(200, body={})])], version=99))


def test_missing_observations_rejected():
    with pytest.raises(CaptureError, match="at least one observation"):
        parse_capture(_capture([_ep()]))


def test_empty_endpoint_list_rejected():
    with pytest.raises(CaptureError, match="expected a list"):
        parse_capture(_capture("not-a-list"))


def test_load_capture_missing_file(tmp_path):
    with pytest.raises(CaptureError, match="not found"):
        scaffold(str(tmp_path / "nope.json"))


def test_redacts_sensitive_request_body_keys(tmp_path):
    capture = _capture(
        [
            _ep(
                method="POST",
                path="/auth/login",
                request_body={
                    "username": "alice",
                    "password": "hunter2",
                    "device": {"accessToken": "tok_123", "platform": "web"},
                    "amount": 500,
                },
                observations=[_obs(200, authed=False, body={"ok": True})],
            )
        ]
    )
    cap_file = tmp_path / "capture.json"
    cap_file.write_text(json.dumps(capture))
    yaml_text, notes = scaffold(str(cap_file))

    assert "hunter2" not in yaml_text
    assert "tok_123" not in yaml_text
    assert "<redacted>" in yaml_text
    assert "amount: 500" in yaml_text
    assert "alice" in yaml_text
    assert any("redacted sensitive request-body values" in n for n in notes)


def test_render_yaml_matches_example_style():
    contract = {
        "name": "Escrow API contract",
        "base_url": "http://127.0.0.1:8000",
        "auth_header": "Authorization: Bearer <your-token>",
        "error_envelopes": {
            "standard": {
                "required_fields": ["error", "message", "code"],
                "field_types": {"error": "boolean", "message": "string", "code": "string"},
            }
        },
        "endpoints": [
            {
                "name": "create_escrow",
                "method": "POST",
                "path": "/escrows",
                "auth_required": True,
                "body": {"amount": 500},
                "expect": {"status": 201},
            }
        ],
    }
    rendered = render_yaml(contract)
    assert 'name: "Escrow API contract"' in rendered
    assert "status: 201" in rendered
    assert "auth_required: true" in rendered
    assert 'required_fields: ["error", "message", "code"]' in rendered
    assert "    body:" in rendered
    assert "      amount: 500" in rendered

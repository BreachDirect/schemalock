"""Load and validate schemalock.yaml into typed config objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import yaml

VALID_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}
VALID_TYPES = {"string", "number", "boolean", "object", "array", "null"}


class ConfigError(Exception):
    """Raised when schemalock.yaml is malformed, with a precise field path."""


@dataclass
class ErrorEnvelope:
    name: str
    required_fields: list[str] = field(default_factory=list)
    field_types: dict[str, str] = field(default_factory=dict)


@dataclass
class Endpoint:
    name: str
    method: str
    path: str
    body: dict | None = None
    auth_required: bool = False
    expect_status: int | list[int] = 200
    expect_envelope: str | None = None
    path_params: dict[str, str] = field(default_factory=dict)

    def acceptable_statuses(self) -> list[int]:
        if isinstance(self.expect_status, int):
            return [self.expect_status]
        return list(self.expect_status)

    def resolved_path(self) -> str:
        path = self.path
        for k, v in self.path_params.items():
            path = path.replace("{" + k + "}", str(v))
        return path


@dataclass
class Config:
    name: str
    base_url: str | None
    auth_header: str | None
    error_envelopes: dict[str, ErrorEnvelope]
    endpoints: list[Endpoint]


def _require(d: Any, key: str, path: str, expected_type=None):
    if not isinstance(d, dict):
        raise ConfigError(f"{path}: expected a mapping, got {type(d).__name__}")
    if key not in d:
        raise ConfigError(f"{path}.{key}: missing required field")
    value = d[key]
    if expected_type is not None and not isinstance(value, expected_type):
        raise ConfigError(f"{path}.{key}: expected {expected_type}, got {type(value).__name__}")
    return value


def _parse_error_envelopes(raw: Any, path: str) -> dict[str, ErrorEnvelope]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ConfigError(f"{path}: expected a mapping of envelope_name -> spec")

    envelopes: dict[str, ErrorEnvelope] = {}
    for name, spec in raw.items():
        spec = spec or {}
        if not isinstance(spec, dict):
            raise ConfigError(f"{path}.{name}: expected a mapping")
        required_fields = spec.get("required_fields", []) or []
        if not isinstance(required_fields, list):
            raise ConfigError(f"{path}.{name}.required_fields: expected a list")
        field_types = spec.get("field_types", {}) or {}
        if not isinstance(field_types, dict):
            raise ConfigError(f"{path}.{name}.field_types: expected a mapping")
        for fname, ftype in field_types.items():
            if ftype not in VALID_TYPES:
                raise ConfigError(
                    f"{path}.{name}.field_types.{fname}: '{ftype}' is not one of "
                    f"{sorted(VALID_TYPES)}"
                )
        envelopes[name] = ErrorEnvelope(
            name=name, required_fields=list(required_fields), field_types=dict(field_types)
        )
    return envelopes


def _parse_endpoint(raw: Any, idx: int, known_envelopes: dict[str, ErrorEnvelope]) -> Endpoint:
    path = f"endpoints[{idx}]"
    if not isinstance(raw, dict):
        raise ConfigError(f"{path}: expected a mapping")

    name = _require(raw, "name", path, str)
    method = _require(raw, "method", path, str).upper()
    if method not in VALID_METHODS:
        raise ConfigError(f"{path}.method: '{method}' must be one of {sorted(VALID_METHODS)}")
    ep_path = _require(raw, "path", path, str)

    expect = raw.get("expect")
    if not isinstance(expect, dict) or "status" not in expect:
        raise ConfigError(f"{path}.expect.status: missing required field")
    status = expect["status"]
    if isinstance(status, list):
        if not all(isinstance(s, int) for s in status):
            raise ConfigError(f"{path}.expect.status: all list items must be integers")
    elif not isinstance(status, int):
        raise ConfigError(f"{path}.expect.status: expected int or list[int]")

    envelope_name = expect.get("error_envelope")
    if envelope_name is not None and envelope_name not in known_envelopes:
        raise ConfigError(
            f"{path}.expect.error_envelope: '{envelope_name}' is not defined in error_envelopes"
        )

    body = raw.get("body")
    if body is not None and not isinstance(body, dict):
        raise ConfigError(f"{path}.body: expected a mapping")

    auth_required = raw.get("auth_required", False)
    if not isinstance(auth_required, bool):
        raise ConfigError(f"{path}.auth_required: expected a boolean")

    path_params = raw.get("path_params", {}) or {}
    if not isinstance(path_params, dict):
        raise ConfigError(f"{path}.path_params: expected a mapping")

    return Endpoint(
        name=name,
        method=method,
        path=ep_path,
        body=body,
        auth_required=auth_required,
        expect_status=status,
        expect_envelope=envelope_name,
        path_params=path_params,
    )


def parse_config(raw: dict) -> Config:
    if not isinstance(raw, dict):
        raise ConfigError("root: expected a mapping (is this valid YAML?)")

    name = raw.get("name", "SchemaLock contract")
    base_url = raw.get("base_url")
    auth_header = raw.get("auth_header")

    envelopes = _parse_error_envelopes(raw.get("error_envelopes"), "error_envelopes")

    raw_endpoints = raw.get("endpoints")
    if not isinstance(raw_endpoints, list) or not raw_endpoints:
        raise ConfigError("endpoints: expected a non-empty list")

    endpoints = [_parse_endpoint(ep, i, envelopes) for i, ep in enumerate(raw_endpoints)]

    return Config(
        name=name,
        base_url=base_url,
        auth_header=auth_header,
        error_envelopes=envelopes,
        endpoints=endpoints,
    )


def load_config(path: str) -> Config:
    try:
        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)
    except FileNotFoundError as e:
        raise ConfigError(f"config file not found: {path}") from e
    except yaml.YAMLError as e:
        raise ConfigError(f"invalid YAML in {path}: {e}") from e

    if raw is None:
        raise ConfigError(f"{path}: file is empty")

    return parse_config(raw)

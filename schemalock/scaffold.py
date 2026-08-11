"""Turn a SchemaLock Recorder capture.json into a runnable schemalock.yaml.

The browser extension (`browser-extension/`) records live API traffic — status
codes, error-envelope bodies, and which requests were sent with credentials.
`schemalock scaffold` consumes that capture and infers a declarative contract:

- error envelopes clustered by observed top-level error-body shape
- expected statuses from the observed status distribution per endpoint
- `auth_required` from observed 401/403s and (when present) auth probes, where
  the extension replayed the request without credentials
- path placeholders with sample values, so the generated config runs immediately

The output is emitted as YAML that `schemalock test` accepts unchanged.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

CAPTURE_VERSION = 1

# Header the extension always sends on authenticated requests. We only detect
# auth presence, never the token value.
_AUTH_HEADER_NAMES = ("authorization", "x-api-key", "x-auth-token")

# Keys whose values are redacted before emitting YAML. Captured request bodies
# are recorded traffic — a real token/password that passed through the page
# must never end up committed to a contract repo.
_SENSITIVE_KEY_RE = re.compile(
    r"(?i)(password|passwd|pwd|secret|token|api[_-]?key|apikey|access[_-]?key|"
    r"authorization|credential|private[_-]?key|jwt|session|csrf)"
)


class CaptureError(Exception):
    """Raised when capture.json is malformed or unsupported."""


@dataclass
class Observation:
    status: int
    authed: bool
    body: Any = None
    count: int = 1


@dataclass
class CapturedEndpoint:
    method: str
    path: str
    origin: str
    observations: list[Observation] = field(default_factory=list)
    request_body: Any = None
    path_params: dict[str, str] = field(default_factory=dict)
    auth_probe: int | None = None


@dataclass
class Capture:
    endpoints: list[CapturedEndpoint]
    recorded_at: str | None = None
    recorder: str | None = None


def load_capture(path: str) -> Capture:
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except FileNotFoundError as e:
        raise CaptureError(f"capture file not found: {path}") from e
    except json.JSONDecodeError as e:
        raise CaptureError(f"invalid JSON in {path}: {e}") from e
    return parse_capture(raw)


def parse_capture(raw: Any) -> Capture:
    if not isinstance(raw, dict):
        raise CaptureError("capture: expected a JSON object")
    if raw.get("version") != CAPTURE_VERSION:
        raise CaptureError(
            f"unsupported capture version {raw.get('version')!r}; expected {CAPTURE_VERSION}"
        )
    raw_endpoints = raw.get("endpoints")
    if not isinstance(raw_endpoints, list):
        raise CaptureError("capture.endpoints: expected a list")

    endpoints: list[CapturedEndpoint] = []
    for idx, raw_ep in enumerate(raw_endpoints):
        path = f"capture.endpoints[{idx}]"
        if not isinstance(raw_ep, dict):
            raise CaptureError(f"{path}: expected an object")
        method = raw_ep.get("method", "").upper()
        if method not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
            raise CaptureError(f"{path}.method: '{raw_ep.get('method')}' is not supported")
        ep_path = raw_ep.get("path")
        origin = raw_ep.get("origin")
        if not isinstance(ep_path, str) or not ep_path:
            raise CaptureError(f"{path}.path: expected a non-empty string")
        if not isinstance(origin, str) or not origin:
            raise CaptureError(f"{path}.origin: expected a non-empty string")

        observations = []
        for obs_idx, raw_obs in enumerate(raw_ep.get("observations", [])):
            obs_path = f"{path}.observations[{obs_idx}]"
            if not isinstance(raw_obs, dict) or not isinstance(raw_obs.get("status"), int):
                raise CaptureError(f"{obs_path}: expected {{status: <int>}}")
            observations.append(
                Observation(
                    status=raw_obs["status"],
                    authed=bool(raw_obs.get("authed", False)),
                    body=raw_obs.get("body"),
                    count=int(raw_obs.get("count", 1)),
                )
            )
        if not observations:
            raise CaptureError(f"{path}: expected at least one observation")

        request_body = raw_ep.get("request_body")
        path_params = raw_ep.get("path_params") or {}
        if not isinstance(path_params, dict):
            raise CaptureError(f"{path}.path_params: expected a mapping")

        auth_probe = raw_ep.get("auth_probe")
        if auth_probe is not None and not isinstance(auth_probe, dict):
            raise CaptureError(f"{path}.auth_probe: expected an object or null")
        probe_status = None
        if auth_probe:
            probe_status = auth_probe.get("status")
            if not isinstance(probe_status, int):
                raise CaptureError(f"{path}.auth_probe.status: expected an integer")

        endpoints.append(
            CapturedEndpoint(
                method=method,
                path=ep_path,
                origin=origin,
                observations=observations,
                request_body=request_body,
                path_params=dict(path_params),
                auth_probe=probe_status,
            )
        )

    return Capture(
        endpoints=endpoints,
        recorded_at=raw.get("recorded_at"),
        recorder=raw.get("recorder"),
    )


def _json_type(value: Any) -> str:
    """Map a Python JSON value to the type names used in field_types."""
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if value is None:
        return "null"
    return "string"


def _infer_envelopes(capture: Capture) -> tuple[dict[str, dict], dict[int, str]]:
    """Cluster observed error bodies by top-level key signature.

    Returns (envelopes, endpoint_index -> envelope_name) where the envelope name
    is the best match for each endpoint's most frequent error body shape.
    """
    buckets: dict[tuple[str, ...], dict[int, Any]] = {}
    occurrences: dict[tuple[str, ...], int] = {}
    ep_error_buckets: list[dict[tuple[str, ...], int]] = []

    for idx, ep in enumerate(capture.endpoints):
        by_sig: dict[tuple[str, ...], int] = {}
        for obs in ep.observations:
            body = obs.body
            if obs.status < 400 or not isinstance(body, dict) or not body:
                continue
            sig = tuple(sorted(body.keys()))
            buckets.setdefault(sig, {})[idx] = body
            occurrences[sig] = occurrences.get(sig, 0) + obs.count
            by_sig[sig] = by_sig.get(sig, 0) + obs.count
        ep_error_buckets.append(by_sig)

    if not buckets:
        return {}, {}

    names: dict[tuple[str, ...], str] = {}
    if len(buckets) == 1:
        names[next(iter(buckets))] = "standard"
    else:
        for i, sig in enumerate(sorted(buckets, key=lambda s: (-occurrences[s], s)), start=1):
            names[sig] = f"error_v{i}"

    envelopes: dict[str, dict] = {}
    for sig, name in names.items():
        representative = next(iter(buckets[sig].values()))
        envelopes[name] = {
            "required_fields": list(sig),
            "field_types": {k: _json_type(representative[k]) for k in sig},
        }

    ep_envelope: dict[int, str] = {}
    for idx, by_sig in enumerate(ep_error_buckets):
        if not by_sig:
            continue
        best_sig = max(by_sig, key=by_sig.get)
        ep_envelope[idx] = names[best_sig]

    return envelopes, ep_envelope


def _auth_required(ep: CapturedEndpoint) -> bool:
    """An endpoint is auth_required if any 401/403 was observed or probed."""
    if ep.auth_probe in (401, 403):
        return True
    return any(obs.status in (401, 403) for obs in ep.observations)


def _auth_enforced_when_probed(ep: CapturedEndpoint) -> bool:
    """True when a probe (no credentials) was clearly rejected."""
    return ep.auth_probe in (401, 403)


def _name_for(method: str, path: str, taken: set[str]) -> str:
    parts = []
    for segment in path.strip("/").split("/"):
        if not segment:
            continue
        if segment.startswith("{") and segment.endswith("}"):
            parts.append(segment[1:-1])
        else:
            parts.append(re.sub(r"[^a-zA-Z0-9]+", "_", segment).strip("_"))
    base = "_".join([method.lower()] + parts).strip("_") or "root"
    candidate, i = base, 1
    while candidate in taken:
        i += 1
        candidate = f"{base}_{i}"
    taken.add(candidate)
    return candidate


def build_contract(capture: Capture, name: str | None = None, base_url: str | None = None) -> dict:
    """Build the config-shaped dict that render_yaml serializes."""
    origins = {ep.origin for ep in capture.endpoints}
    if base_url is None:
        base_url = next(iter(origins)) if len(origins) == 1 else None

    envelopes, ep_envelope = _infer_envelopes(capture)

    endpoints: list[dict] = []
    taken: set[str] = set()
    for idx, ep in enumerate(capture.endpoints):
        statuses = sorted({obs.status for obs in ep.observations})
        expect: dict[str, Any] = {}
        if len(statuses) == 1:
            expect["status"] = statuses[0]
        else:
            expect["status"] = statuses

        auth_required = _auth_required(ep)
        envelope_name = ep_envelope.get(idx)
        if envelope_name is not None:
            expect["error_envelope"] = envelope_name

        entry: dict[str, Any] = {
            "name": _name_for(ep.method, ep.path, taken),
            "method": ep.method,
            "path": ep.path,
        }
        if ep.path_params:
            entry["path_params"] = dict(ep.path_params)
        entry["auth_required"] = auth_required
        if ep.request_body is not None:
            entry["body"] = ep.request_body
        entry["expect"] = expect
        endpoints.append(entry)

    contract: dict[str, Any] = {"name": name or "Recorded API contract"}
    if base_url:
        contract["base_url"] = base_url
    if any(o.authed for ep in capture.endpoints for o in ep.observations):
        contract["auth_header"] = "Authorization: Bearer <your-token>"
    if envelopes:
        contract["error_envelopes"] = envelopes
    contract["endpoints"] = endpoints
    return contract


def _emit_dict(d: dict, indent: int, keys: list[str] | None = None) -> list[str]:
    lines: list[str] = []
    pad = " " * indent
    order = keys or list(d.keys())
    for key in order:
        if key not in d:
            continue
        value = d[key]
        if value is None:
            continue
        if isinstance(value, dict):
            lines.append(f"{pad}{key}:")
            lines.extend(_emit_dict(value, indent + 2))
        elif isinstance(value, list):
            if value and all(isinstance(v, dict) for v in value):
                lines.append(f"{pad}{key}:")
                for item in value:
                    lines.append(f"{pad}- name: {json.dumps(item['name'])}")
                    lines.extend(_emit_dict(item, indent + 4, ["name"]))
            elif value and all(isinstance(v, int) for v in value):
                lines.append(f"{pad}{key}: [{', '.join(str(v) for v in value)}]")
            elif not value:
                lines.append(f"{pad}{key}: []")
            else:
                lines.append(f"{pad}{key}: {json.dumps(value)}")
        else:
            lines.append(f"{pad}{key}: {json.dumps(value)}")
    return lines


def render_yaml(contract: dict, notes: list[str] | None = None) -> str:
    """Serialize a build_contract dict into schemalock.yaml (comments preserved)."""
    lines = [
        "# Generated by `schemalock scaffold`. Review before trusting it:",
        "#   - auth_header contains a placeholder token — replace it.",
        "#   - sensitive values (tokens, passwords, keys) are redacted as <redacted>.",
        "#   - expected statuses/error envelopes are inferred from recorded traffic.",
    ]
    if notes:
        lines.append("#")
        for note in notes:
            lines.append(f"# {note}")

    lines.append("")

    header = []
    if "name" in contract:
        header.append(("name", "str"))
    if "base_url" in contract:
        header.append(("base_url", "str"))
    if "auth_header" in contract:
        header.append(("auth_header", "str"))

    def emit_simple(key: str) -> None:
        lines.append(f"{key}: {json.dumps(contract[key])}")

    for key, _ in header:
        emit_simple(key)

    if "error_envelopes" in contract:
        lines.append("")
        lines.append("error_envelopes:")
        for env_name, env in contract["error_envelopes"].items():
            lines.append(f"  {env_name}:")
            lines.append(f"    required_fields: {json.dumps(env['required_fields'])}")
            lines.append("    field_types:")
            for fname, ftype in env["field_types"].items():
                lines.append(f'      {fname}: "{ftype}"')

    lines.append("")
    lines.append("endpoints:")
    for ep in contract["endpoints"]:
        lines.append(f"  - name: {json.dumps(ep['name'])}")
        lines.append(f"    method: {ep['method']}")
        lines.append(f"    path: {json.dumps(ep['path'])}")
        if "path_params" in ep:
            lines.append("    path_params:")
            for k, v in ep["path_params"].items():
                lines.append(f"      {k}: {json.dumps(v)}")
        lines.append(f"    auth_required: {str(ep['auth_required']).lower()}")
        if "body" in ep:
            lines.append("    body:")
            lines.extend(_emit_dict(ep["body"], 6))
        lines.append("    expect:")
        expect = ep["expect"]
        if isinstance(expect["status"], list):
            status_repr = ", ".join(str(s) for s in expect["status"])
            lines.append(f"      status: [{status_repr}]")
        else:
            lines.append(f"      status: {expect['status']}")
        if "error_envelope" in expect:
            lines.append(f"      error_envelope: {expect['error_envelope']}")

    return "\n".join(lines) + "\n"


def _redact(value: Any, redacted: list[str], path: str = "") -> Any:
    """Replace values under sensitive keys with '<redacted>'."""
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if _SENSITIVE_KEY_RE.search(str(key)):
                out[key] = "<redacted>"
                redacted.append(f"{path}.{key}".lstrip("."))
            else:
                out[key] = _redact(item, redacted, f"{path}.{key}")
        return out
    if isinstance(value, list):
        return [_redact(item, redacted, f"{path}[]") for item in value]
    return value


def scaffold(
    capture_path: str, name: str | None = None, base_url: str | None = None
) -> tuple[str, list[str]]:
    capture = load_capture(capture_path)
    notes: list[str] = []

    origins = {ep.origin for ep in capture.endpoints}
    if base_url is None and len(origins) > 1:
        notes.append("multiple origins recorded; base_url omitted — pass --base-url when testing")

    for ep in capture.endpoints:
        if ep.auth_probe is not None and ep.auth_probe not in (401, 403):
            notes.append(
                f"{ep.method} {ep.path}: replay without credentials returned "
                f"{ep.auth_probe} — the route does not enforce an auth boundary; "
                f"set auth_required accordingly"
            )

    redacted: list[str] = []
    for ep in capture.endpoints:
        if ep.request_body is not None:
            ep.request_body = _redact(ep.request_body, redacted)
    if redacted:
        keys = ", ".join(sorted(set(redacted))[:8])
        notes.append(f"redacted sensitive request-body values at: {keys}")

    contract = build_contract(capture, name=name, base_url=base_url)
    return render_yaml(contract, notes), notes

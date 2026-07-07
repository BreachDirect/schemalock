"""Check: error responses keep a stable envelope shape (required fields + types).

Deliberately forgiving on extra/additive fields; strict on missing fields or
type drift, since that's the class of change that actually breaks API clients.
"""

from __future__ import annotations

import httpx

from schemalock.checks import CheckResult, Outcome
from schemalock.config import Endpoint, ErrorEnvelope

_PY_TYPE_BY_NAME = {
    "string": str,
    "number": (int, float),
    "boolean": bool,
    "object": dict,
    "array": list,
    "null": type(None),
}


def _type_ok(value, type_name: str) -> bool:
    expected = _PY_TYPE_BY_NAME.get(type_name)
    if expected is None:
        return True
    if type_name == "boolean" and isinstance(value, int) and not isinstance(value, bool):
        # ints (0/1) should not silently pass as booleans
        return False
    return isinstance(value, expected)


def check_error_envelope(
    endpoint: Endpoint, envelope: ErrorEnvelope, response: httpx.Response
) -> CheckResult:
    check_name = "error_envelope"

    try:
        body = response.json()
    except ValueError:
        return CheckResult(
            endpoint=endpoint.name,
            check=check_name,
            outcome=Outcome.FAIL,
            detail="response body is not valid JSON; error envelope cannot be checked",
        )

    if not isinstance(body, dict):
        return CheckResult(
            endpoint=endpoint.name,
            check=check_name,
            outcome=Outcome.FAIL,
            detail=f"expected a JSON object for envelope '{envelope.name}', got {type(body).__name__}",
        )

    missing = [f for f in envelope.required_fields if f not in body]
    if missing:
        return CheckResult(
            endpoint=endpoint.name,
            check=check_name,
            outcome=Outcome.FAIL,
            detail=f"envelope '{envelope.name}' missing required field(s): {missing}",
        )

    type_errors = []
    for fname, ftype in envelope.field_types.items():
        if fname not in body:
            continue  # already caught by required_fields if it mattered
        if not _type_ok(body[fname], ftype):
            type_errors.append(
                f"{fname}: expected {ftype}, got {type(body[fname]).__name__}"
            )
    if type_errors:
        return CheckResult(
            endpoint=endpoint.name,
            check=check_name,
            outcome=Outcome.FAIL,
            detail=f"envelope '{envelope.name}' field type drift: {'; '.join(type_errors)}",
        )

    return CheckResult(
        endpoint=endpoint.name,
        check=check_name,
        outcome=Outcome.PASS,
        detail=f"envelope '{envelope.name}' shape stable",
    )

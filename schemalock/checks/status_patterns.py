"""Check: response status code matches the endpoint's declared contract."""

from __future__ import annotations

import httpx

from schemalock.checks import CheckResult, Outcome
from schemalock.config import Endpoint


def check_status(endpoint: Endpoint, response: httpx.Response) -> CheckResult:
    acceptable = endpoint.acceptable_statuses()
    if response.status_code in acceptable:
        return CheckResult(
            endpoint=endpoint.name,
            check="status",
            outcome=Outcome.PASS,
            detail=f"got {response.status_code}, expected one of {acceptable}",
        )
    return CheckResult(
        endpoint=endpoint.name,
        check="status",
        outcome=Outcome.FAIL,
        detail=f"expected status in {acceptable}, got {response.status_code}",
    )

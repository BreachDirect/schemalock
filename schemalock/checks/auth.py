"""Check: auth-required routes actually enforce the auth boundary.

Replays the request with credentials stripped and asserts the response is a
clean 401/403 — never a 2xx/3xx (auth bypass), never a 404 (which leaks
resource existence to unauthenticated callers), never a 5xx (auth check
crashing instead of rejecting).
"""

from __future__ import annotations

import httpx

from schemalock.checks import CheckResult, Outcome
from schemalock.config import Endpoint
from schemalock.http import ResponseTooLarge, send_bounded

ACCEPTABLE_UNAUTHENTICATED_STATUSES = {401, 403}


def check_auth_required(
    endpoint: Endpoint,
    client: httpx.Client,
    base_url: str,
    timeout: float,
    max_bytes: int = 10 * 1024 * 1024,
) -> CheckResult:
    check_name = "auth_required"
    url = base_url.rstrip("/") + endpoint.resolved_path()

    try:
        response = send_bounded(
            client,
            endpoint.method,
            url,
            json=endpoint.body,
            headers={},  # deliberately no auth header
            timeout=timeout,
            max_bytes=max_bytes,
        )
    except ResponseTooLarge as e:
        return CheckResult(
            endpoint=endpoint.name,
            check=check_name,
            outcome=Outcome.ERROR,
            detail=f"unauthenticated request failed: {e}",
        )
    except httpx.HTTPError as e:
        return CheckResult(
            endpoint=endpoint.name,
            check=check_name,
            outcome=Outcome.ERROR,
            detail=f"request without credentials failed: {e}",
        )

    if response.status_code in ACCEPTABLE_UNAUTHENTICATED_STATUSES:
        return CheckResult(
            endpoint=endpoint.name,
            check=check_name,
            outcome=Outcome.PASS,
            detail=f"unauthenticated request correctly rejected with {response.status_code}",
        )

    if response.status_code == 404:
        detail = (
            "unauthenticated request returned 404 instead of 401/403 — "
            "this leaks resource existence to unauthenticated callers"
        )
    elif 200 <= response.status_code < 400:
        detail = (
            f"unauthenticated request returned {response.status_code} — "
            "auth boundary is not enforced (possible auth bypass)"
        )
    else:
        detail = f"unauthenticated request returned {response.status_code} — expected 401 or 403"

    return CheckResult(
        endpoint=endpoint.name, check=check_name, outcome=Outcome.FAIL, detail=detail
    )

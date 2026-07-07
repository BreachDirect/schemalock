"""Orchestrates HTTP requests against the target and runs applicable checks."""

from __future__ import annotations

from typing import List, Optional

import httpx

from schemalock.checks import CheckResult, Outcome
from schemalock.checks.auth import check_auth_required
from schemalock.checks.error_envelope import check_error_envelope
from schemalock.checks.status_patterns import check_status
from schemalock.config import Config


def _parse_auth_header(raw: Optional[str]) -> dict:
    """Parses a "Header-Name: value" string into a headers dict. Empty if None."""
    if not raw:
        return {}
    if ":" not in raw:
        raise ValueError(f"auth_header must be 'Header-Name: value', got: {raw!r}")
    name, _, value = raw.partition(":")
    return {name.strip(): value.strip()}


class Runner:
    def __init__(
        self,
        config: Config,
        base_url: Optional[str] = None,
        auth_header: Optional[str] = None,
        timeout: float = 10.0,
    ):
        self.config = config
        self.base_url = base_url or config.base_url
        if not self.base_url:
            raise ValueError("base_url must be provided via --base-url or config.base_url")
        self.auth_header = auth_header or config.auth_header
        self.timeout = timeout

    def run(self) -> List[CheckResult]:
        results: List[CheckResult] = []
        headers = _parse_auth_header(self.auth_header)

        with httpx.Client() as client:
            for endpoint in self.config.endpoints:
                url = self.base_url.rstrip("/") + endpoint.resolved_path()

                try:
                    response = client.request(
                        endpoint.method,
                        url,
                        json=endpoint.body,
                        headers=headers,
                        timeout=self.timeout,
                    )
                except httpx.HTTPError as e:
                    results.append(
                        CheckResult(
                            endpoint=endpoint.name,
                            check="request",
                            outcome=Outcome.ERROR,
                            detail=f"request failed: {e}",
                        )
                    )
                    continue

                results.append(check_status(endpoint, response))

                if endpoint.expect_envelope and response.status_code >= 400:
                    envelope = self.config.error_envelopes[endpoint.expect_envelope]
                    results.append(check_error_envelope(endpoint, envelope, response))

                if endpoint.auth_required:
                    results.append(
                        check_auth_required(endpoint, client, self.base_url, self.timeout)
                    )

        return results

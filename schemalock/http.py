"""Redirect-safe, bounded HTTP requests for the runner and checks.

Two hardening properties are enforced here:

- **Redirects are never followed.** An authenticated contract check must not
  forward credentials to a different origin via a 3xx response. Contract tests
  also generally want to see the raw 3xx, not a transparently-followed body.
- **Response bodies are read incrementally and bounded.** The target of a
  contract check is attacker-influenced code; an unbounded response could
  exhaust CI memory. Reading is capped at ``max_bytes`` (default 10 MiB).
"""

from __future__ import annotations

import httpx

DEFAULT_MAX_RESPONSE_BYTES = 10 * 1024 * 1024
_READ_CHUNK = 64 * 1024


class ResponseTooLarge(Exception):
    """Raised when a target response exceeds ``max_bytes``."""


def send_bounded(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    json: dict | None = None,
    headers: dict | None = None,
    timeout: float,
    max_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
) -> httpx.Response:
    """Issue a request, reading at most ``max_bytes`` of response body.

    Returns an httpx.Response whose content is fully loaded (so ``.json()``
    works) or raises :class:`httpx.HTTPError` / :class:`ResponseTooLarge`.
    """
    with client.stream(
        method,
        url,
        json=json,
        headers=headers,
        timeout=timeout,
        follow_redirects=False,
    ) as response:
        size = 0
        chunks: list[bytes] = []
        for chunk in response.iter_bytes(_READ_CHUNK):
            size += len(chunk)
            if size > max_bytes:
                raise ResponseTooLarge(url, max_bytes)
            chunks.append(chunk)
        response._content = b"".join(chunks)
    return response

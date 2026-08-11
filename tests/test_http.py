import httpx
import pytest
from schemalock.http import DEFAULT_MAX_RESPONSE_BYTES, ResponseTooLarge, send_bounded


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_send_bounded_does_not_follow_redirects():
    seen = []

    def handler(request):
        seen.append(request.url)
        return httpx.Response(302, headers={"Location": "https://evil.example/steal"})

    with _client(handler) as client:
        response = send_bounded(
            client,
            "GET",
            "https://target.example/api",
            headers={"Authorization": "Bearer tok"},
            timeout=5.0,
        )
    assert response.status_code == 302
    assert len(seen) == 1  # no follow-up request, credentials never forwarded


def test_send_bounded_populates_content_for_json():
    def handler(request):
        return httpx.Response(200, json={"ok": True})

    with _client(handler) as client:
        response = send_bounded(client, "GET", "https://target.example/api", timeout=5.0)
    assert response.json() == {"ok": True}


def test_send_bounded_raises_when_response_exceeds_limit():
    def handler(request):
        return httpx.Response(200, content=b"x" * 1024)

    with _client(handler) as client, pytest.raises(ResponseTooLarge):
        send_bounded(client, "GET", "https://target.example/api", timeout=5.0, max_bytes=100)


def test_default_limit_is_sane():
    assert DEFAULT_MAX_RESPONSE_BYTES == 10 * 1024 * 1024

import httpx

from schemalock.checks import Outcome
from schemalock.checks.auth import check_auth_required
from schemalock.checks.error_envelope import check_error_envelope
from schemalock.checks.status_patterns import check_status
from schemalock.config import Endpoint, ErrorEnvelope


def make_response(status_code: int, json_body=None) -> httpx.Response:
    content = None if json_body is None else httpx.Response(200, json=json_body).content
    return httpx.Response(status_code, content=content)


# --- status_patterns ---

def test_status_pass_on_exact_match():
    ep = Endpoint(name="e", method="GET", path="/x", expect_status=200)
    result = check_status(ep, make_response(200))
    assert result.outcome == Outcome.PASS


def test_status_fail_on_mismatch():
    ep = Endpoint(name="e", method="GET", path="/x", expect_status=200)
    result = check_status(ep, make_response(500))
    assert result.outcome == Outcome.FAIL
    assert "500" in result.detail


def test_status_pass_when_in_list():
    ep = Endpoint(name="e", method="DELETE", path="/x", expect_status=[204, 409])
    result = check_status(ep, make_response(409))
    assert result.outcome == Outcome.PASS


# --- error_envelope ---

STANDARD = ErrorEnvelope(
    name="standard",
    required_fields=["error", "message", "code"],
    field_types={"error": "boolean", "message": "string", "code": "string"},
)


def test_envelope_pass_when_shape_matches():
    ep = Endpoint(name="e", method="GET", path="/x", expect_status=404)
    resp = make_response(404, {"error": True, "message": "not found", "code": "NOT_FOUND"})
    result = check_error_envelope(ep, STANDARD, resp)
    assert result.outcome == Outcome.PASS


def test_envelope_fail_on_missing_field():
    ep = Endpoint(name="e", method="GET", path="/x", expect_status=404)
    resp = make_response(404, {"error": True, "code": "NOT_FOUND"})  # missing "message"
    result = check_error_envelope(ep, STANDARD, resp)
    assert result.outcome == Outcome.FAIL
    assert "message" in result.detail


def test_envelope_fail_on_type_drift():
    ep = Endpoint(name="e", method="GET", path="/x", expect_status=404)
    resp = make_response(404, {"error": "yes", "message": "not found", "code": "NOT_FOUND"})
    result = check_error_envelope(ep, STANDARD, resp)
    assert result.outcome == Outcome.FAIL
    assert "error" in result.detail


def test_envelope_pass_allows_extra_fields():
    ep = Endpoint(name="e", method="GET", path="/x", expect_status=404)
    resp = make_response(
        404,
        {"error": True, "message": "not found", "code": "NOT_FOUND", "trace_id": "abc123"},
    )
    result = check_error_envelope(ep, STANDARD, resp)
    assert result.outcome == Outcome.PASS


def test_envelope_fail_on_non_json_body():
    ep = Endpoint(name="e", method="GET", path="/x", expect_status=404)
    resp = httpx.Response(404, content=b"not json")
    result = check_error_envelope(ep, STANDARD, resp)
    assert result.outcome == Outcome.FAIL


# --- auth ---

def _client_with_handler(handler):
    transport = httpx.MockTransport(handler)
    return httpx.Client(transport=transport)


def test_auth_pass_when_401_returned():
    def handler(request):
        assert "Authorization" not in request.headers
        return httpx.Response(401, json={"error": True})

    ep = Endpoint(name="e", method="GET", path="/secret", auth_required=True, expect_status=200)
    with _client_with_handler(handler) as client:
        result = check_auth_required(ep, client, "http://test", timeout=5.0)
    assert result.outcome == Outcome.PASS


def test_auth_fail_when_200_returned_bypass():
    def handler(request):
        return httpx.Response(200, json={"ok": True})

    ep = Endpoint(name="e", method="GET", path="/secret", auth_required=True, expect_status=200)
    with _client_with_handler(handler) as client:
        result = check_auth_required(ep, client, "http://test", timeout=5.0)
    assert result.outcome == Outcome.FAIL
    assert "bypass" in result.detail


def test_auth_fail_when_404_returned_leaks_existence():
    def handler(request):
        return httpx.Response(404, json={"error": True})

    ep = Endpoint(name="e", method="GET", path="/secret/1", auth_required=True, expect_status=200)
    with _client_with_handler(handler) as client:
        result = check_auth_required(ep, client, "http://test", timeout=5.0)
    assert result.outcome == Outcome.FAIL
    assert "leaks resource existence" in result.detail

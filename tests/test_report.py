import json

from schemalock.checks import CheckResult, Outcome
from schemalock.report import exit_code, render_console, render_json


def _result(outcome: Outcome, detail: str = "200 OK") -> CheckResult:
    return CheckResult(endpoint="/health", check="status", outcome=outcome, detail=detail)


def test_render_console_has_pytest_style_lines():
    results = [_result(Outcome.PASS), _result(Outcome.FAIL), _result(Outcome.ERROR)]
    out = render_console("demo", results)
    assert out.startswith("SchemaLock — demo")
    assert "PASSED  /health :: status — 200 OK" in out
    assert "FAILED  /health :: status — 200 OK" in out
    assert "ERROR   /health :: status — 200 OK" in out
    assert "3 checks: 1 passed, 1 failed, 1 errored" in out


def test_render_console_summary_counts():
    results = [_result(Outcome.PASS), _result(Outcome.PASS), _result(Outcome.ERROR)]
    assert "3 checks: 2 passed, 0 failed, 1 errored" in render_console("demo", results)


def test_render_json_summary_and_details(tmp_path):
    path = tmp_path / "report.json"
    results = [_result(Outcome.PASS), _result(Outcome.ERROR, detail="connection refused")]
    render_json("demo", results, str(path))
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["config_name"] == "demo"
    assert payload["summary"] == {"total": 2, "passed": 1, "failed": 0, "errored": 1}
    assert payload["results"][1] == {
        "endpoint": "/health",
        "check": "status",
        "outcome": "ERROR",
        "detail": "connection refused",
    }


def test_exit_code_is_zero_only_when_all_pass():
    assert exit_code([_result(Outcome.PASS)]) == 0
    assert exit_code([_result(Outcome.PASS), _result(Outcome.FAIL)]) == 1
    assert exit_code([_result(Outcome.PASS), _result(Outcome.ERROR)]) == 1
    assert exit_code([]) == 0

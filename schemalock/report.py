"""Pytest-style console output and JSON report generation."""

from __future__ import annotations

import json

from schemalock.checks import CheckResult, Outcome

_SYMBOL = {Outcome.PASS: "PASSED", Outcome.FAIL: "FAILED", Outcome.ERROR: "ERROR "}


def render_console(config_name: str, results: list[CheckResult]) -> str:
    lines = [f"SchemaLock — {config_name}", ""]
    for r in results:
        lines.append(f"{_SYMBOL[r.outcome]}  {r.endpoint} :: {r.check} — {r.detail}")

    passed = sum(1 for r in results if r.outcome == Outcome.PASS)
    failed = sum(1 for r in results if r.outcome == Outcome.FAIL)
    errored = sum(1 for r in results if r.outcome == Outcome.ERROR)

    lines.append("")
    lines.append(f"{len(results)} checks: {passed} passed, {failed} failed, {errored} errored")
    return "\n".join(lines)


def report_json_string(config_name: str, results: list[CheckResult]) -> str:
    """Serialize the report exactly once; shared by the file writer and the
    ``--json`` stdout path so both emit byte-identical payloads."""
    payload = {
        "config_name": config_name,
        "summary": {
            "total": len(results),
            "passed": sum(1 for r in results if r.outcome == Outcome.PASS),
            "failed": sum(1 for r in results if r.outcome == Outcome.FAIL),
            "errored": sum(1 for r in results if r.outcome == Outcome.ERROR),
        },
        "results": [r.to_dict() for r in results],
    }
    return json.dumps(payload, indent=2)


def render_json(config_name: str, results: list[CheckResult], path: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(report_json_string(config_name, results))


def exit_code(results: list[CheckResult]) -> int:
    return 0 if all(r.outcome == Outcome.PASS for r in results) else 1

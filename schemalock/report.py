"""Pytest-style console output and JSON report generation."""

from __future__ import annotations

import json
from typing import List

from schemalock.checks import CheckResult, Outcome

_SYMBOL = {Outcome.PASS: "PASSED", Outcome.FAIL: "FAILED", Outcome.ERROR: "ERROR "}


def render_console(config_name: str, results: List[CheckResult]) -> str:
    lines = [f"SchemaLock — {config_name}", ""]
    for r in results:
        lines.append(f"{_SYMBOL[r.outcome]}  {r.endpoint} :: {r.check} — {r.detail}")

    passed = sum(1 for r in results if r.outcome == Outcome.PASS)
    failed = sum(1 for r in results if r.outcome == Outcome.FAIL)
    errored = sum(1 for r in results if r.outcome == Outcome.ERROR)

    lines.append("")
    lines.append(
        f"{len(results)} checks: {passed} passed, {failed} failed, {errored} errored"
    )
    return "\n".join(lines)


def render_json(config_name: str, results: List[CheckResult], path: str) -> None:
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
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)


def exit_code(results: List[CheckResult]) -> int:
    return 0 if all(r.outcome == Outcome.PASS for r in results) else 1

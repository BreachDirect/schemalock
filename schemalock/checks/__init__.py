"""Built-in contract checks. Each check module returns CheckResult objects."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Outcome(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"  # network/transport failure, not a contract assertion failure


@dataclass
class CheckResult:
    endpoint: str
    check: str  # "status" | "error_envelope" | "auth_required"
    outcome: Outcome
    detail: str = ""

    def to_dict(self) -> dict:
        return {
            "endpoint": self.endpoint,
            "check": self.check,
            "outcome": self.outcome.value,
            "detail": self.detail,
        }

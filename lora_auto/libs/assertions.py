"""Assertion helpers for LoRa automation checks."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Pattern


@dataclass(frozen=True)
class AssertionResult:
    """Structured assertion result used by higher-level clients."""

    passed: bool
    message: str


def assert_contains(actual: str, expected: str) -> AssertionResult:
    """Check whether ``actual`` contains ``expected``."""

    if expected in actual:
        return AssertionResult(True, f"response contains {expected!r}")
    return AssertionResult(False, f"expected {expected!r} in response, got {actual!r}")


def assert_regex(actual: str, pattern: str | Pattern[str]) -> AssertionResult:
    """Check whether ``actual`` matches a regular expression."""

    compiled = re.compile(pattern) if isinstance(pattern, str) else pattern
    if compiled.search(actual):
        return AssertionResult(True, f"response matches regex {compiled.pattern!r}")
    return AssertionResult(False, f"expected regex {compiled.pattern!r} to match response, got {actual!r}")


def assert_payload_equal(sent: str, received: str) -> AssertionResult:
    """Check whether received payload contains the sent payload.

    LoRa transparent mode responses may include framing, line endings, or
    additional serial noise, so the MVP-level equality check is containment.
    """

    if sent in received:
        return AssertionResult(True, f"received payload contains sent payload {sent!r}")
    return AssertionResult(False, f"expected received payload to contain {sent!r}, got {received!r}")

"""AT command client for LoRa module automation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from lora_auto.libs.assertions import AssertionResult, assert_contains
from lora_auto.libs.serial_client import SerialClient, SerialClientError


class AtClientError(RuntimeError):
    """Raised when an AT command operation fails unexpectedly."""


@dataclass(frozen=True)
class AtCommandResult:
    """Structured result for a single AT command."""

    command: str
    response: str
    expected: str
    passed: bool
    message: str


class AtClient:
    """High-level helper for AT mode and AT command interactions."""

    def __init__(self, serial_client: SerialClient, at_entry_expected: str = "Entry AT") -> None:
        self.serial = serial_client
        self.at_entry_expected = at_entry_expected

    def enter_at(self, timeout: float = 2.0) -> AtCommandResult:
        """Enter AT mode using the LoRa module escape sequence."""

        return self.send_cmd(
            "+++",
            expected=self.at_entry_expected,
            timeout=timeout,
            append_newline=False,
        )

    def send_cmd(
        self,
        cmd: str,
        expected: str = "OK",
        timeout: float = 2.0,
        append_newline: bool = True,
    ) -> AtCommandResult:
        """Send one AT command and check whether the response contains expected text."""

        if not cmd:
            raise AtClientError("AT command must not be empty")
        if expected == "":
            raise AtClientError("expected response must not be empty")

        try:
            self.serial.write_text(cmd, append_newline=append_newline)
            response = self.serial.read_until(expected, timeout=timeout)
        except SerialClientError as exc:
            raise AtClientError(f"failed to execute AT command {cmd!r}: {exc}") from exc

        assertion: AssertionResult = assert_contains(response.data, expected)
        return AtCommandResult(
            command=cmd,
            response=response.data,
            expected=expected,
            passed=response.matched and assertion.passed,
            message=assertion.message,
        )

    def reset(self, timeout: float = 5.0, expected: str = "OK") -> AtCommandResult:
        """Reset the module through AT command."""

        return self.send_cmd("AT+RESET", expected=expected, timeout=timeout)

    def require_cmd(
        self,
        cmd: str,
        expected: str = "OK",
        timeout: float = 2.0,
        append_newline: bool = True,
    ) -> AtCommandResult:
        """Send a command and raise if it does not pass.

        This is useful for setup flows where later steps are invalid if a prior
        AT command failed.
        """

        result = self.send_cmd(
            cmd,
            expected=expected,
            timeout=timeout,
            append_newline=append_newline,
        )
        if not result.passed:
            raise AtClientError(
                f"AT command {cmd!r} failed: expected {expected!r}, response {result.response!r}"
            )
        return result

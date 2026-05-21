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

    def enter_at(self, timeout: float = 2.0, probe_timeout: float = 0.5) -> AtCommandResult:
        """Enter AT mode after probing the current mode.

        ``AT -> OK`` means the module is already in AT mode, so the method does
        not send ``+++`` again. If the probe does not match, the escape sequence
        is sent with CRLF to enter AT mode.
        """

        probe = self.send_cmd("AT", expected="OK", timeout=probe_timeout)
        if probe.passed:
            return probe

        return self.send_cmd(
            "+++",
            expected=self.at_entry_expected,
            timeout=timeout,
        )

    def exit_at(
        self,
        timeout: float = 2.0,
        reset_drain_timeout: float = 1.0,
        expected: str = "Exit AT",
    ) -> AtCommandResult:
        """Exit AT mode and drain reset banner residue.

        The module may output ``Power on`` after ``Exit AT``. ``read_until``
        returns as soon as ``Exit AT`` is seen, so this method drains the short
        reset banner window and then clears buffers to avoid leaking stale
        ``Power on`` into the next case.
        """

        result = self.send_cmd("+++", expected=expected, timeout=timeout)
        drained = self._drain_reset_banner(reset_drain_timeout, "AT exit")

        response = result.response + drained
        assertion: AssertionResult = assert_contains(result.response, expected)
        return AtCommandResult(
            command=result.command,
            response=response,
            expected=result.expected,
            passed=result.passed and assertion.passed,
            message=assertion.message,
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

    def reset(
        self,
        timeout: float = 5.0,
        expected: str = "OK",
        reset_drain_timeout: float = 1.0,
    ) -> AtCommandResult:
        """Reset the module through AT command and drain boot banner residue.

        ``AT+RESET`` may return ``OK`` before the module prints the subsequent
        boot banner, for example ``Power on``. Draining and clearing here keeps
        that banner from leaking into the next transparent-transfer receive
        window.
        """

        result = self.send_cmd("AT+RESET", expected=expected, timeout=timeout)
        drained = self._drain_reset_banner(reset_drain_timeout, "AT reset")

        response = result.response + drained
        assertion: AssertionResult = assert_contains(result.response, expected)
        return AtCommandResult(
            command=result.command,
            response=response,
            expected=result.expected,
            passed=result.passed and assertion.passed,
            message=assertion.message,
        )

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

    def _drain_reset_banner(self, timeout: float, operation: str) -> str:
        """Drain delayed reset/banner bytes and clear stale serial buffers."""

        try:
            drained = self.serial.read_all(timeout=timeout)
            self.serial.clear_buffer()
        except SerialClientError as exc:
            raise AtClientError(f"failed to drain {operation} response: {exc}") from exc
        return drained

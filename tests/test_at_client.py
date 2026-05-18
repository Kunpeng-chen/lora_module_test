from __future__ import annotations

import pytest

from lora_auto.libs.at_client import AtClient, AtClientError
from lora_auto.libs.serial_client import SerialClientError, SerialResponse


class FakeSerialClient:
    def __init__(self, response: SerialResponse | None = None, fail_write: bool = False) -> None:
        self.response = response or SerialResponse(data="OK\r\n", matched=True)
        self.fail_write = fail_write
        self.commands: list[tuple[str, bool]] = []
        self.reads: list[tuple[str, float]] = []

    def write_text(self, text: str, append_newline: bool = True) -> None:
        if self.fail_write:
            raise SerialClientError("write failed")
        self.commands.append((text, append_newline))

    def read_until(self, expected: str, timeout: float = 2.0) -> SerialResponse:
        self.reads.append((expected, timeout))
        return self.response


def test_send_cmd_returns_passed_result_for_expected_response() -> None:
    fake = FakeSerialClient(SerialResponse(data="OK\r\n", matched=True))
    client = AtClient(fake)  # type: ignore[arg-type]

    result = client.send_cmd("AT", expected="OK", timeout=1.5)

    assert result.passed is True
    assert result.command == "AT"
    assert result.expected == "OK"
    assert result.response == "OK\r\n"
    assert fake.commands == [("AT", True)]
    assert fake.reads == [("OK", 1.5)]


def test_send_cmd_returns_failed_result_when_expected_response_is_missing() -> None:
    fake = FakeSerialClient(SerialResponse(data="ERROR\r\n", matched=False))
    client = AtClient(fake)  # type: ignore[arg-type]

    result = client.send_cmd("AT", expected="OK", timeout=0.1)

    assert result.passed is False
    assert "ERROR" in result.response
    assert "expected" in result.message


def test_send_cmd_supports_version_expectation() -> None:
    fake = FakeSerialClient(SerialResponse(data="+VERSION=V1.2.4\r\nOK\r\n", matched=True))
    client = AtClient(fake)  # type: ignore[arg-type]

    result = client.send_cmd("AT+VERSION", expected="+VERSION")

    assert result.passed is True
    assert fake.commands == [("AT+VERSION", True)]


def test_enter_at_sends_escape_sequence_with_crlf() -> None:
    fake = FakeSerialClient(SerialResponse(data="Entry AT\r\n", matched=True))
    client = AtClient(fake)  # type: ignore[arg-type]

    result = client.enter_at(timeout=0.5)

    assert result.passed is True
    assert fake.commands == [("+++", True)]
    assert fake.reads == [("Entry AT", 0.5)]


def test_reset_sends_reset_command_with_longer_timeout() -> None:
    fake = FakeSerialClient(SerialResponse(data="OK\r\n", matched=True))
    client = AtClient(fake)  # type: ignore[arg-type]

    result = client.reset(timeout=3.0)

    assert result.passed is True
    assert fake.commands == [("AT+RESET", True)]
    assert fake.reads == [("OK", 3.0)]


def test_require_cmd_raises_when_command_fails() -> None:
    fake = FakeSerialClient(SerialResponse(data="ERROR\r\n", matched=False))
    client = AtClient(fake)  # type: ignore[arg-type]

    with pytest.raises(AtClientError, match="AT command 'AT' failed"):
        client.require_cmd("AT", expected="OK", timeout=0.1)


def test_send_cmd_raises_for_empty_command_or_expected_text() -> None:
    client = AtClient(FakeSerialClient())  # type: ignore[arg-type]

    with pytest.raises(AtClientError, match="must not be empty"):
        client.send_cmd("")

    with pytest.raises(AtClientError, match="must not be empty"):
        client.send_cmd("AT", expected="")


def test_send_cmd_wraps_serial_errors() -> None:
    fake = FakeSerialClient(fail_write=True)
    client = AtClient(fake)  # type: ignore[arg-type]

    with pytest.raises(AtClientError, match="failed to execute AT command"):
        client.send_cmd("AT")

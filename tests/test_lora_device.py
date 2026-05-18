from __future__ import annotations

import pytest

from lora_auto.libs.at_client import AtClientError, AtCommandResult
from lora_auto.libs.lora_device import LoraDevice, LoraDeviceError


class FakeSerialClient:
    def __init__(self) -> None:
        self.opened = False
        self.closed = False
        self.cleared = 0

    def open(self) -> None:
        self.opened = True

    def close(self) -> None:
        self.closed = True

    def clear_buffer(self) -> None:
        self.cleared += 1


class FakeAtClient:
    at_entry_expected = "Entry AT"

    def __init__(self, fail_command: str | None = None, raise_command: str | None = None) -> None:
        self.fail_command = fail_command
        self.raise_command = raise_command
        self.calls: list[tuple[str, str, float, bool]] = []

    def enter_at(self, timeout: float = 2.0) -> AtCommandResult:
        command = "+++"
        self.calls.append((command, self.at_entry_expected, timeout, True))
        return self._result(command, self.at_entry_expected)

    def send_cmd(
        self,
        cmd: str,
        expected: str = "OK",
        timeout: float = 2.0,
        append_newline: bool = True,
    ) -> AtCommandResult:
        self.calls.append((cmd, expected, timeout, append_newline))
        return self._result(cmd, expected)

    def reset(self, timeout: float = 5.0, expected: str = "OK") -> AtCommandResult:
        command = "AT+RESET"
        self.calls.append((command, expected, timeout, True))
        return self._result(command, expected)

    def _result(self, command: str, expected: str) -> AtCommandResult:
        if self.raise_command == command:
            raise AtClientError("transport error")
        passed = self.fail_command != command
        response = expected if passed else "ERROR"
        return AtCommandResult(
            command=command,
            response=response,
            expected=expected,
            passed=passed,
            message="ok" if passed else "failed",
        )


def make_device(at: FakeAtClient, name: str = "A", role: str | None = None, baudrate: int = 9600) -> tuple[LoraDevice, FakeSerialClient]:
    serial = FakeSerialClient()
    device = LoraDevice(name, "COM3", baudrate=baudrate, role=role, serial_client=serial, at_client=at)  # type: ignore[arg-type]
    return device, serial


def test_device_open_and_close_delegate_to_serial_client() -> None:
    serial = FakeSerialClient()
    at = FakeAtClient()
    device = LoraDevice("A", "COM3", serial_client=serial, at_client=at)  # type: ignore[arg-type]

    device.open()
    device.close()

    assert serial.opened is True
    assert serial.closed is True
    assert device.name == "A"
    assert device.port == "COM3"
    assert device.baudrate == 9600


def test_configure_transparent_mode_executes_expected_command_sequence() -> None:
    at = FakeAtClient()
    device, serial = make_device(at)

    steps = device.configure_transparent_mode()

    assert serial.cleared == 1
    assert [step.command for step in steps] == [
        "+++",
        "AT+SLEEP2",
        "AT+MODE0",
        "AT+LEVEL2",
        "AT+CHANNEL00",
        "AT+RESET",
    ]
    assert all(step.passed for step in steps)
    assert at.calls == [
        ("+++", "Entry AT", 2.0, True),
        ("AT+SLEEP2", "OK", 2.0, True),
        ("AT+MODE0", "OK", 2.0, True),
        ("AT+LEVEL2", "OK", 2.0, True),
        ("AT+CHANNEL00", "OK", 2.0, True),
        ("AT+RESET", "OK", 5.0, True),
    ]


def test_configure_transparent_mode_supports_custom_parameters() -> None:
    at = FakeAtClient()
    device, serial = make_device(at, name="B", role="receiver", baudrate=115200)

    steps = device.configure_transparent_mode(sleep="1", mode="0", level="3", channel="12")

    assert serial.cleared == 1
    assert device.role == "receiver"
    assert device.baudrate == 115200
    assert [step.command for step in steps] == [
        "+++",
        "AT+SLEEP1",
        "AT+MODE0",
        "AT+LEVEL3",
        "AT+CHANNEL12",
        "AT+RESET",
    ]


def test_configure_transparent_mode_stops_on_failed_command() -> None:
    at = FakeAtClient(fail_command="AT+LEVEL2")
    device, serial = make_device(at)

    with pytest.raises(LoraDeviceError, match=r"AT\+LEVEL2"):
        device.configure_transparent_mode()

    assert serial.cleared == 1
    assert [call[0] for call in at.calls] == ["+++", "AT+SLEEP2", "AT+MODE0", "AT+LEVEL2"]


def test_configure_transparent_mode_wraps_at_client_errors() -> None:
    at = FakeAtClient(raise_command="AT+MODE0")
    device, serial = make_device(at)

    with pytest.raises(LoraDeviceError, match=r"failed to execute 'AT\+MODE0'"):
        device.configure_transparent_mode()

    assert serial.cleared == 1

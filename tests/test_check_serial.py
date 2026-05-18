from __future__ import annotations

import sys
from pathlib import Path

import pytest

from lora_auto.libs.serial_client import SerialResponse

EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "lora_auto" / "examples"
if str(EXAMPLES_DIR) not in sys.path:
    sys.path.insert(0, str(EXAMPLES_DIR))

import check_serial  # noqa: E402


class FakeSerialClient:
    responses: list[SerialResponse] = []
    read_all_data = ""
    instances: list["FakeSerialClient"] = []

    def __init__(self, port: str, baudrate: int = 9600, timeout: float = 2.0) -> None:
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.is_open = False
        self.commands: list[tuple[str, bool]] = []
        self.read_alls: list[float] = []
        self.cleared = 0
        FakeSerialClient.instances.append(self)

    def open(self) -> None:
        self.is_open = True

    def close(self) -> None:
        self.is_open = False

    def clear_buffer(self) -> None:
        self.cleared += 1

    def write_text(self, text: str, append_newline: bool = True) -> None:
        self.commands.append((text, append_newline))

    def read_until(self, expected: str, timeout: float = 2.0) -> SerialResponse:
        if not FakeSerialClient.responses:
            return SerialResponse(data="", matched=False)
        return FakeSerialClient.responses.pop(0)

    def read_all(self, timeout: float = 2.0) -> str:
        self.read_alls.append(timeout)
        return FakeSerialClient.read_all_data


@pytest.fixture(autouse=True)
def patch_serial_client(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeSerialClient.responses = []
    FakeSerialClient.read_all_data = ""
    FakeSerialClient.instances = []
    monkeypatch.setattr(check_serial, "SerialClient", FakeSerialClient)


def test_check_serial_enters_at_sends_command_and_exits_at_on_success(capsys: pytest.CaptureFixture[str]) -> None:
    FakeSerialClient.responses = [
        SerialResponse(data="Entry AT\r\n", matched=True),
        SerialResponse(data="OK\r\n", matched=True),
        SerialResponse(data="Exit AT\r\n", matched=True),
    ]
    FakeSerialClient.read_all_data = "Power on\r\n"

    rc = check_serial.main(["--port", "COM3"])

    assert rc == 0
    serial = FakeSerialClient.instances[0]
    assert serial.commands == [("+++", True), ("AT", True), ("+++", True)]
    assert serial.read_alls == [1.0]
    assert serial.cleared >= 2
    output = capsys.readouterr().out
    assert "TX: +++" in output
    assert "RX: Entry AT" in output
    assert "TX: AT" in output
    assert "PASS" in output
    assert "RX: Exit AT" in output
    assert "Power on" in output


def test_check_serial_does_not_exit_at_when_command_fails() -> None:
    FakeSerialClient.responses = [
        SerialResponse(data="Entry AT\r\n", matched=True),
        SerialResponse(data="ERROR\r\n", matched=False),
    ]

    rc = check_serial.main(["--port", "COM3"])

    assert rc == 1
    serial = FakeSerialClient.instances[0]
    assert serial.commands == [("+++", True), ("AT", True)]
    assert serial.read_alls == []


def test_check_serial_skip_exit_at_keeps_module_in_at_mode() -> None:
    FakeSerialClient.responses = [
        SerialResponse(data="Entry AT\r\n", matched=True),
        SerialResponse(data="OK\r\n", matched=True),
    ]

    rc = check_serial.main(["--port", "COM3", "--skip-exit-at"])

    assert rc == 0
    serial = FakeSerialClient.instances[0]
    assert serial.commands == [("+++", True), ("AT", True)]
    assert serial.read_alls == []

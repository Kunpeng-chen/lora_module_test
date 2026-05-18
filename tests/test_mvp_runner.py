from __future__ import annotations

from pathlib import Path

import pytest

from lora_auto.libs.at_client import AtCommandResult
from lora_auto.test_mvp import MvpRunner, MvpRunnerError, load_cases, load_devices, select_cases


class FakeAt:
    def __init__(self, fail_command: str | None = None) -> None:
        self.fail_command = fail_command
        self.commands: list[tuple[str, str]] = []

    def send_cmd(self, command: str, expected: str = "OK") -> AtCommandResult:
        self.commands.append((command, expected))
        passed = self.fail_command != command
        return AtCommandResult(
            command=command,
            response=expected if passed else "ERROR",
            expected=expected,
            passed=passed,
            message="ok" if passed else "failed",
        )


class FakeSerial:
    def __init__(self, read_data: str = "") -> None:
        self.read_data = read_data
        self.cleared = 0
        self.written: list[tuple[str, bool]] = []

    def clear_buffer(self) -> None:
        self.cleared += 1

    def write_text(self, text: str, append_newline: bool = True) -> None:
        self.written.append((text, append_newline))

    def read_all(self, timeout: float = 2.0) -> str:
        return self.read_data


class FakeDevice:
    def __init__(self, name: str, port: str = "COMX", baudrate: int = 9600, role: str | None = None) -> None:
        self.name = name
        self.port = port
        self.baudrate = baudrate
        self.role = role
        self.at = FakeAt()
        self.serial = FakeSerial()
        self.opened = False
        self.closed = False
        self.config_calls: list[dict[str, str]] = []

    def open(self) -> None:
        self.opened = True

    def close(self) -> None:
        self.closed = True

    def configure_transparent_mode(self, sleep: str = "2", mode: str = "0", level: str = "2", channel: str = "00") -> None:
        self.config_calls.append({"sleep": sleep, "mode": mode, "level": level, "channel": channel})


def test_load_devices_creates_devices_from_yaml(tmp_path: Path) -> None:
    path = tmp_path / "devices.yaml"
    path.write_text(
        """
devices:
  A:
    port: COM3
    baudrate: 9600
    role: sender
""",
        encoding="utf-8",
    )

    devices = load_devices(path, device_factory=FakeDevice)

    assert list(devices) == ["A"]
    assert devices["A"].port == "COM3"
    assert devices["A"].role == "sender"


def test_load_cases_and_select_single_case(tmp_path: Path) -> None:
    path = tmp_path / "cases.yaml"
    path.write_text(
        """
cases:
  - id: MVP-001
    name: AT 基础指令测试
    type: at
  - id: MVP-003
    name: 透明传输收发一致性测试
    type: transparent_transfer
""",
        encoding="utf-8",
    )

    cases = load_cases(path)
    selected = select_cases(cases, "MVP-003")

    assert len(cases) == 2
    assert selected[0]["id"] == "MVP-003"


def test_select_cases_raises_for_unknown_case() -> None:
    with pytest.raises(MvpRunnerError, match="not found"):
        select_cases([{"id": "MVP-001", "name": "x", "type": "at"}], "MVP-999")


def test_runner_executes_at_case_successfully() -> None:
    device = FakeDevice("A")
    runner = MvpRunner({"A": device})

    result = runner.run_case(
        {
            "id": "MVP-001",
            "name": "AT 基础指令测试",
            "type": "at",
            "device": "A",
            "steps": [
                {"command": "AT", "expected": "OK"},
                {"command": "AT+VERSION", "expected": "+VERSION"},
            ],
        }
    )

    assert result.status == "PASS"
    assert device.at.commands == [("AT", "OK"), ("AT+VERSION", "+VERSION")]


def test_runner_returns_fail_for_at_case_mismatch() -> None:
    device = FakeDevice("A")
    device.at = FakeAt(fail_command="AT")
    runner = MvpRunner({"A": device})

    result = runner.run_case(
        {
            "id": "MVP-001",
            "name": "AT 基础指令测试",
            "type": "at",
            "device": "A",
            "steps": [{"command": "AT", "expected": "OK"}],
        }
    )

    assert result.status == "FAIL"
    assert "AT command" in result.failure_reason


def test_runner_executes_config_case_for_multiple_devices() -> None:
    dev_a = FakeDevice("A")
    dev_b = FakeDevice("B")
    runner = MvpRunner({"A": dev_a, "B": dev_b})

    result = runner.run_case(
        {
            "id": "MVP-002",
            "name": "A/B 模块配置为透明传输",
            "type": "config",
            "devices": ["A", "B"],
            "config": {"sleep": "2", "mode": "0", "level": "2", "channel": "00"},
        }
    )

    assert result.status == "PASS"
    assert dev_a.config_calls == [{"sleep": "2", "mode": "0", "level": "2", "channel": "00"}]
    assert dev_b.config_calls == [{"sleep": "2", "mode": "0", "level": "2", "channel": "00"}]


def test_runner_executes_transparent_transfer_case_successfully() -> None:
    sender = FakeDevice("A")
    receiver = FakeDevice("B")
    receiver.serial = FakeSerial(read_data="noise123456789\r\n")
    runner = MvpRunner({"A": sender, "B": receiver})

    result = runner.run_case(
        {
            "id": "MVP-003",
            "name": "透明传输收发一致性测试",
            "type": "transparent_transfer",
            "sender": "A",
            "receiver": "B",
            "payload": "123456789",
            "expected": "123456789",
            "timeout": 5,
        }
    )

    assert result.status == "PASS"
    assert sender.serial.cleared == 1
    assert receiver.serial.cleared == 1
    assert sender.serial.written == [("123456789", False)]


def test_runner_returns_fail_for_transparent_transfer_timeout() -> None:
    sender = FakeDevice("A")
    receiver = FakeDevice("B")
    receiver.serial = FakeSerial(read_data="")
    runner = MvpRunner({"A": sender, "B": receiver})

    result = runner.run_case(
        {
            "id": "MVP-003",
            "name": "透明传输收发一致性测试",
            "type": "transparent_transfer",
            "sender": "A",
            "receiver": "B",
            "payload": "123456789",
            "expected": "123456789",
            "timeout": 5,
        }
    )

    assert result.status == "FAIL"
    assert "receiver did not receive expected payload" in result.failure_reason


def test_runner_opens_and_closes_all_devices() -> None:
    dev_a = FakeDevice("A")
    dev_b = FakeDevice("B")
    runner = MvpRunner({"A": dev_a, "B": dev_b})

    runner.open_devices()
    runner.close_devices()

    assert dev_a.opened is True
    assert dev_a.closed is True
    assert dev_b.opened is True
    assert dev_b.closed is True

from __future__ import annotations

from pathlib import Path

import pytest

from lora_auto.libs.at_client import AtCommandResult
from lora_auto.libs.lora_device import DeviceCommandStep, LoraDeviceError
from lora_auto.libs.serial_client import SerialResponse
from lora_auto.test_mvp import (
    MvpRunner,
    MvpRunnerError,
    load_cases,
    load_devices,
    run_cases_with_dependencies,
    select_cases,
    to_report_case,
)


class FakeAt:
    def __init__(self, fail_command: str | None = None) -> None:
        self.fail_command = fail_command
        self.commands: list[tuple[str, str]] = []

    def enter_at(self) -> AtCommandResult:
        self.commands.append(("+++", "Entry AT"))
        passed = self.fail_command != "+++"
        return AtCommandResult(
            command="+++",
            response="Entry AT" if passed else "ERROR",
            expected="Entry AT",
            passed=passed,
            message="ok" if passed else "failed",
        )

    def exit_at(self) -> AtCommandResult:
        self.commands.append(("+++", "Exit AT"))
        passed = self.fail_command != "exit+++"
        return AtCommandResult(
            command="+++",
            response="Exit AT\r\nPower on\r\n" if passed else "Entry AT",
            expected="Exit AT",
            passed=passed,
            message="ok" if passed else "failed",
        )

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
        self.read_until_calls: list[tuple[str, float]] = []

    def clear_buffer(self) -> None:
        self.cleared += 1

    def write_text(self, text: str, append_newline: bool = True) -> None:
        self.written.append((text, append_newline))

    def read_all(self, timeout: float = 2.0) -> str:
        return self.read_data

    def read_until(self, expected: str, timeout: float = 2.0) -> SerialResponse:
        self.read_until_calls.append((expected, timeout))
        return SerialResponse(data=self.read_data, matched=expected in self.read_data)


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
        self.fail_config = False

    def open(self) -> None:
        self.opened = True

    def close(self) -> None:
        self.closed = True

    def configure_transparent_mode(
        self,
        sleep: str = "2",
        mode: str = "0",
        level: str = "2",
        channel: str = "00",
    ) -> list[DeviceCommandStep]:
        self.serial.clear_buffer()
        self.config_calls.append({"sleep": sleep, "mode": mode, "level": level, "channel": channel})
        if self.fail_config:
            raise LoraDeviceError(f"{self.name}: config failed")
        return [
            DeviceCommandStep(command="+++", expected="Entry AT", response="Entry AT", passed=True),
            DeviceCommandStep(command=f"AT+SLEEP{sleep}", expected="OK", response="OK", passed=True),
            DeviceCommandStep(command=f"AT+MODE{mode}", expected="OK", response="OK", passed=True),
            DeviceCommandStep(command=f"AT+LEVEL{level}", expected="OK", response="OK", passed=True),
            DeviceCommandStep(command=f"AT+CHANNEL{channel}", expected="OK", response="OK", passed=True),
            DeviceCommandStep(command="AT+RESET", expected="OK", response="OK\r\nPower on\r\n", passed=True),
        ]


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


def test_runner_executes_at_case_successfully_and_exits_at(tmp_path: Path) -> None:
    device = FakeDevice("A")
    runner = MvpRunner({"A": device}, report_dir=tmp_path)

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
    assert result.log_file is not None
    assert Path(result.log_file).exists()
    assert device.at.commands == [
        ("+++", "Entry AT"),
        ("AT", "OK"),
        ("AT+VERSION", "+VERSION"),
        ("+++", "Exit AT"),
    ]
    assert "A: +++ -> 'Exit AT\\r\\nPower on\\r\\n'" in "\n".join(result.steps)


def test_runner_stops_at_case_when_enter_at_fails(tmp_path: Path) -> None:
    device = FakeDevice("A")
    device.at = FakeAt(fail_command="+++")
    runner = MvpRunner({"A": device}, report_dir=tmp_path)

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
    assert "failed to enter AT mode" in result.failure_reason
    assert device.at.commands == [("+++", "Entry AT")]


def test_runner_returns_fail_for_at_case_mismatch(tmp_path: Path) -> None:
    device = FakeDevice("A")
    device.at = FakeAt(fail_command="AT")
    runner = MvpRunner({"A": device}, report_dir=tmp_path)

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
    assert result.log_file is not None
    assert Path(result.log_file).exists()
    assert "AT command" in result.failure_reason
    assert device.at.commands == [("+++", "Entry AT"), ("AT", "OK")]


def test_runner_returns_fail_when_at_exit_fails(tmp_path: Path) -> None:
    device = FakeDevice("A")
    device.at = FakeAt(fail_command="exit+++")
    runner = MvpRunner({"A": device}, report_dir=tmp_path)

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
    assert "failed to exit AT mode" in result.failure_reason


def test_runner_executes_config_case_for_multiple_devices(tmp_path: Path) -> None:
    dev_a = FakeDevice("A")
    dev_b = FakeDevice("B")
    runner = MvpRunner({"A": dev_a, "B": dev_b}, report_dir=tmp_path)

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
    assert dev_a.serial.cleared >= 1
    assert dev_b.serial.cleared >= 1
    assert "AT+RESET" in "\n".join(result.steps)
    assert "Power on" in "\n".join(result.steps)


def test_runner_executes_transparent_transfer_case_successfully(tmp_path: Path) -> None:
    sender = FakeDevice("A")
    receiver = FakeDevice("B")
    receiver.serial = FakeSerial(read_data="noise123456789\r\n")
    runner = MvpRunner({"A": sender, "B": receiver}, report_dir=tmp_path)

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
    assert receiver.serial.read_until_calls == [("123456789", 5.0)]
    assert "sent='123456789'" in "\n".join(result.steps)


def test_runner_returns_fail_for_transparent_transfer_timeout(tmp_path: Path) -> None:
    sender = FakeDevice("A")
    receiver = FakeDevice("B")
    receiver.serial = FakeSerial(read_data="Power on\r\n")
    runner = MvpRunner({"A": sender, "B": receiver}, report_dir=tmp_path)

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
    assert "sent='123456789'" in result.failure_reason
    assert "received='Power on\\r\\n'" in result.failure_reason
    assert "received_hex='50 6F 77 65 72 20 6F 6E 0D 0A'" in result.failure_reason
    assert "rx_bytes=10" in result.failure_reason
    assert receiver.serial.read_until_calls == [("123456789", 5.0)]


def test_run_cases_blocks_transparent_transfer_when_config_fails(tmp_path: Path) -> None:
    dev_a = FakeDevice("A")
    dev_b = FakeDevice("B")
    dev_a.fail_config = True
    runner = MvpRunner({"A": dev_a, "B": dev_b}, report_dir=tmp_path)
    cases = [
        {
            "id": "MVP-002",
            "name": "A/B 模块配置为透明传输",
            "type": "config",
            "devices": ["A", "B"],
            "config": {"sleep": "2", "mode": "0", "level": "2", "channel": "00"},
        },
        {
            "id": "MVP-003",
            "name": "透明传输收发一致性测试",
            "type": "transparent_transfer",
            "sender": "A",
            "receiver": "B",
            "payload": "123456789",
            "expected": "123456789",
            "timeout": 5,
        },
    ]

    results = run_cases_with_dependencies(runner, cases)

    assert results[0].status == "FAIL"
    assert results[1].status == "BLOCKED"
    assert "MVP-002" in results[1].failure_reason
    assert sender_not_used(dev_a, dev_b)


def sender_not_used(dev_a: FakeDevice, dev_b: FakeDevice) -> bool:
    return dev_a.serial.written == [] and dev_b.serial.written == []


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


def test_to_report_case_preserves_failure_reason_and_steps(tmp_path: Path) -> None:
    device = FakeDevice("A")
    device.at = FakeAt(fail_command="AT")
    runner = MvpRunner({"A": device}, report_dir=tmp_path)

    result = runner.run_case(
        {
            "id": "MVP-001",
            "name": "AT 基础指令测试",
            "type": "at",
            "device": "A",
            "steps": [{"command": "AT", "expected": "OK"}],
        }
    )
    report_case = to_report_case(result)

    assert report_case.case_id == "MVP-001"
    assert report_case.status == "FAIL"
    assert report_case.failure_reason == result.failure_reason
    assert report_case.log_file == result.log_file

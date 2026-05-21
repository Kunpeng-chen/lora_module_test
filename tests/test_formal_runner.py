from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from lora_auto.test_formal import (
    FormalAtRunner,
    FormalRunnerError,
    build_broadcast_hex_frame,
    build_fixed_hex_frame,
    describe_case_selection,
    expected_read_until,
    load_formal_cases,
    match_expected,
    run_cases,
    select_cases,
    to_report_case,
)
from lora_auto.libs.report import write_reports


FORMAL_CASE_DIR = Path(__file__).resolve().parents[1] / "lora_auto" / "config" / "formal"
TRANSFER_PAYLOAD = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
TRANSFER_PAYLOAD_HEX = TRANSFER_PAYLOAD.encode("utf-8").hex().upper()


class LinkedFakeSerial:
    def __init__(self, name: str) -> None:
        self.name = name
        self.is_open = True
        self.buffer = ""
        self.written_text: list[str] = []
        self.written_hex: list[str] = []
        self.peers: dict[str, "LinkedFakeSerial"] = {}

    @property
    def in_waiting(self) -> int:
        return len(self.buffer.encode("utf-8"))

    def connect(self, peers: dict[str, "LinkedFakeSerial"]) -> None:
        self.peers = peers

    def clear_buffer(self) -> None:
        self.buffer = ""

    def write_text(self, text: str, append_newline: bool = True) -> None:
        payload = text if not append_newline else f"{text}\r\n"
        self.written_text.append(payload)
        for name, peer in self.peers.items():
            if name != self.name:
                peer.buffer += text

    def write_hex(self, hex_str: str) -> None:
        normalized = hex_str.replace(" ", "").upper()
        self.written_hex.append(normalized)
        if normalized.startswith("000201"):
            payload_hex = normalized[6:]
            self.peers["B"].buffer += bytes.fromhex(payload_hex).decode("utf-8")
            return
        if normalized.startswith("01"):
            payload_hex = normalized[2:]
            payload = bytes.fromhex(payload_hex).decode("utf-8")
            for name in ("B", "C"):
                if name in self.peers:
                    self.peers[name].buffer += payload
            return

    def read_until(self, expected: str, timeout: float = 5.0):
        return FakeSerialResponse(data=self.buffer, matched=expected in self.buffer)

    def read(self, size: int) -> bytes:
        data = self.buffer[:size]
        self.buffer = self.buffer[size:]
        return data.encode("utf-8")

    def reset_input_buffer(self) -> None:
        self.buffer = ""

    def reset_output_buffer(self) -> None:
        pass

    def open(self) -> None:
        self.is_open = True

    def close(self) -> None:
        self.is_open = False


class FakeSerialResponse:
    def __init__(self, data: str, matched: bool) -> None:
        self.data = data
        self.matched = matched


class FakeAtClient:
    def __init__(self, responses: dict[str, str | list[str]] | None = None) -> None:
        self.responses = responses or {}
        self.calls: list[str] = []

    def send_cmd(self, cmd: str, expected: str = "OK", timeout: float = 2.0, append_newline: bool = True):
        self.calls.append(cmd)
        raw_response = self.responses.get(cmd, expected)
        if isinstance(raw_response, list):
            response = raw_response.pop(0) if raw_response else ""
        else:
            response = raw_response
        return FakeAtResult(command=cmd, response=response, expected=expected, passed=expected in response)

    def enter_at(self, timeout: float = 2.0):
        self.calls.append("+++:enter")
        response = str(self.responses.get("+++", "Entry AT"))
        return FakeAtResult(command="+++", response=response, expected="Entry AT", passed="Entry AT" in response)

    def exit_at(self):
        self.calls.append("+++:exit")
        return FakeAtResult(command="+++", response="Exit AT\nPower On", expected="Exit AT", passed=True)

    def reset(self, expected: str = "OK"):
        self.calls.append("AT+RESET")
        return FakeAtResult(command="AT+RESET", response="OK\nPower On", expected=expected, passed=expected in "OK\nPower On")


class FakeAtResult:
    def __init__(self, command: str, response: str, expected: str, passed: bool) -> None:
        self.command = command
        self.response = response
        self.expected = expected
        self.passed = passed
        self.message = "matched" if passed else "not matched"


class FakeDevice:
    def __init__(
        self,
        name: str = "A",
        responses: dict[str, str | list[str]] | None = None,
        serial: LinkedFakeSerial | None = None,
    ) -> None:
        self.name = name
        self.at = FakeAtClient(responses)
        self.serial = serial or LinkedFakeSerial(name)
        self.opened = False
        self.closed = False

    def open(self) -> None:
        self.opened = True
        self.serial.open()

    def close(self) -> None:
        self.closed = True
        self.serial.close()


def make_transfer_devices(names: tuple[str, ...] = ("A", "B", "C")) -> dict[str, FakeDevice]:
    serials = {name: LinkedFakeSerial(name) for name in names}
    for serial in serials.values():
        serial.connect(serials)
    return {name: FakeDevice(name=name, serial=serials[name]) for name in names}


def cases_by_id() -> dict[str, dict[str, Any]]:
    return {case["id"]: case for case in load_formal_cases(FORMAL_CASE_DIR)}


def test_select_at_suite_skips_manual_confirm_and_state_changing_cases_by_default() -> None:
    cases = load_formal_cases(FORMAL_CASE_DIR)

    selected = select_cases(cases, suite="at")

    assert [case["id"] for case in selected] == [
        "AT-001",
        *(f"AT-{index:03d}" for index in range(4, 13)),
        *(f"AT-{index:03d}" for index in range(14, 19)),
    ]
    assert "AT-002" not in {case["id"] for case in selected}
    assert "AT-003" not in {case["id"] for case in selected}
    assert "AT-013" not in {case["id"] for case in selected}
    assert "AT-019" not in {case["id"] for case in selected}
    assert "AT-020" not in {case["id"] for case in selected}


def test_select_main_suite_includes_all_transfer_cases_by_default() -> None:
    cases = load_formal_cases(FORMAL_CASE_DIR)

    selected = select_cases(cases, suite="main")

    assert [case["id"] for case in selected] == [f"MAIN-{index:03d}" for index in range(1, 7)]


def test_select_error_at_suite_includes_all_negative_cases_by_default() -> None:
    cases = load_formal_cases(FORMAL_CASE_DIR)

    selected = select_cases(cases, suite="error_at")

    assert len(selected) == 57
    assert selected[0]["id"] == "ERRAT-001"
    assert selected[-1]["id"] == "ERRAT-057"


def test_select_manual_case_by_id_requires_explicit_include_manual() -> None:
    cases = load_formal_cases(FORMAL_CASE_DIR)

    with pytest.raises(FormalRunnerError, match="requires manual confirmation"):
        select_cases(cases, case_id="AT-020")

    selected = select_cases(cases, case_id="AT-020", include_manual=True)
    assert [case["id"] for case in selected] == ["AT-020"]


def test_dry_run_describes_run_and_skip_without_opening_devices() -> None:
    cases = [cases_by_id()["AT-001"], cases_by_id()["AT-020"]]

    lines = describe_case_selection(cases)

    assert lines[0].startswith("[RUN] AT-001")
    assert any(line.startswith("[SKIP] AT-020") and "manual_confirm" in line for line in lines)


def test_expected_read_until_for_regex_uses_response_prefix() -> None:
    assert expected_read_until({"mode": "regex", "value": r"\+BAUD=\d+"}) == "+BAUD="
    assert expected_read_until({"mode": "contains", "value": "OK"}) == "OK"
    assert expected_read_until({"mode": "contains_all", "values": ["+KEY=12345", "OK"]}) == "+KEY=12345"
    assert expected_read_until({"mode": "contains_all_receivers", "value": TRANSFER_PAYLOAD}) == TRANSFER_PAYLOAD


def test_match_expected_modes() -> None:
    assert match_expected("OK", {"mode": "contains", "value": "OK"})[0]
    assert match_expected("+KEY=12345\nOK", {"mode": "contains_all", "values": ["+KEY=12345", "OK"]})[0]
    assert match_expected("+BAUD=3", {"mode": "regex", "value": r"\+BAUD=\d+"})[0]
    assert match_expected("OK\n", {"mode": "exact", "value": "OK"})[0]
    assert match_expected(TRANSFER_PAYLOAD, {"mode": "contains_all_receivers", "value": TRANSFER_PAYLOAD})[0]


def test_build_fixed_and_broadcast_hex_frames() -> None:
    assert build_fixed_hex_frame(
        {
            "target_mac": "00,02",
            "channel": "01",
            "payload": TRANSFER_PAYLOAD,
            "encoding": "fixed_hex_frame",
        }
    ) == f"000201{TRANSFER_PAYLOAD_HEX}"
    assert build_broadcast_hex_frame(
        {"channel": "01", "payload": TRANSFER_PAYLOAD, "encoding": "broadcast_hex_frame"}
    ) == f"01{TRANSFER_PAYLOAD_HEX}"


def test_run_at_001_with_mock_device_writes_reports(tmp_path: Path) -> None:
    case = cases_by_id()["AT-001"]
    device = FakeDevice(responses={"AT": "OK"})
    runner = FormalAtRunner({"A": device}, report_dir=tmp_path)

    results = run_cases(runner, [case])
    json_path, markdown_path = write_reports(tmp_path, [to_report_case(result) for result in results])

    assert results[0].status == "PASS"
    assert device.at.calls == ["AT", "AT"]
    assert Path(json_path).exists()
    assert Path(markdown_path).exists()
    payload = json.loads(Path(json_path).read_text(encoding="utf-8"))
    assert payload["summary"]["passed"] == 1
    assert payload["cases"][0]["case_id"] == "AT-001"
    assert (tmp_path / "logs" / "AT-001_runner.log").exists()


def test_ensure_at_mode_enters_when_initial_probe_fails() -> None:
    case = cases_by_id()["AT-001"]
    device = FakeDevice(responses={"AT": ["", "OK", "OK"], "+++": "Entry AT"})
    runner = FormalAtRunner({"A": device})

    result = runner.run_case(case)

    assert result.status == "PASS"
    assert device.at.calls == ["AT", "+++:enter", "AT", "AT"]
    assert any("enter_at" in step for step in result.steps)


def test_ensure_at_mode_fails_if_entry_verification_fails() -> None:
    case = cases_by_id()["AT-001"]
    device = FakeDevice(responses={"AT": ["", ""], "+++": "Entry AT"})
    runner = FormalAtRunner({"A": device})

    result = runner.run_case(case)

    assert result.status == "FAIL"
    assert "AT mode verification failed" in (result.failure_reason or "")
    assert device.at.calls == ["AT", "+++:enter", "AT"]


def test_run_regex_at_case_with_mock_device() -> None:
    case = cases_by_id()["AT-004"]
    device = FakeDevice(responses={"AT": "OK", "AT+BAUD": "+BAUD=3"})
    runner = FormalAtRunner({"A": device})

    result = runner.run_case(case)

    assert result.status == "PASS"
    assert device.at.calls == ["AT", "AT+BAUD"]


def test_run_error_at_104_case_with_post_check() -> None:
    case = cases_by_id()["ERRAT-001"]
    device = FakeDevice(responses={"AT": "OK", "AT+": "ERROR=101"})
    runner = FormalAtRunner({"A": device})

    result = runner.run_case(case)

    assert result.status == "PASS"
    assert device.at.calls == ["AT", "AT+", "AT"]


def test_run_error_at_105_case_with_post_check() -> None:
    case = cases_by_id()["ERRAT-014"]
    device = FakeDevice(responses={"AT": "OK", "AT+BAUD9": "ERROR=101"})
    runner = FormalAtRunner({"A": device})

    result = runner.run_case(case)

    assert result.status == "PASS"
    assert device.at.calls == ["AT", "AT+BAUD9", "AT"]


def test_error_at_case_fails_when_health_check_fails() -> None:
    case = cases_by_id()["ERRAT-001"]
    device = FakeDevice(responses={"AT": ["OK", ""], "AT+": "ERROR=101"})
    runner = FormalAtRunner({"A": device})

    result = runner.run_case(case)

    assert result.status == "FAIL"
    assert "post_check" not in (result.failure_reason or "") or "OK" in (result.failure_reason or "")
    assert device.at.calls == ["AT", "AT+", "AT"]


def test_manual_confirm_case_is_blocked_if_runner_receives_it() -> None:
    case = cases_by_id()["AT-020"]
    device = FakeDevice(responses={"AT+DEFAULT": "OK\nPower On"})
    runner = FormalAtRunner({"A": device})

    result = runner.run_case(case)

    assert result.status == "BLOCKED"
    assert "manual confirmation" in (result.failure_reason or "")
    assert device.at.calls == []


def test_run_main_001_transparent_transfer_with_mock_devices() -> None:
    case = cases_by_id()["MAIN-001"]
    devices = make_transfer_devices(("A", "B"))
    runner = FormalAtRunner(devices)

    result = runner.run_case(case)

    assert result.status == "PASS"
    assert devices["A"].serial.written_text == [TRANSFER_PAYLOAD, TRANSFER_PAYLOAD]
    assert "AT+SLEEP2" in devices["A"].at.calls
    assert "AT+MODE0" in devices["A"].at.calls
    assert "AT+KEY123456" in devices["B"].at.calls


def test_run_main_002_wake_on_air_transparent_transfer_with_mock_devices() -> None:
    case = cases_by_id()["MAIN-002"]
    devices = make_transfer_devices(("A", "B"))
    runner = FormalAtRunner(devices)

    result = runner.run_case(case)

    assert result.status == "PASS"
    assert "AT+SLEEP1" in devices["A"].at.calls
    assert devices["A"].serial.written_text == [TRANSFER_PAYLOAD, TRANSFER_PAYLOAD]


def test_run_main_003_fixed_transfer_writes_structured_hex_frame() -> None:
    case = cases_by_id()["MAIN-003"]
    devices = make_transfer_devices(("A", "B"))
    runner = FormalAtRunner(devices)

    result = runner.run_case(case)

    assert result.status == "PASS"
    assert devices["A"].serial.written_hex == [
        f"000201{TRANSFER_PAYLOAD_HEX}",
        f"000201{TRANSFER_PAYLOAD_HEX}",
    ]
    assert "AT+MODE1" in devices["A"].at.calls


def test_run_main_005_broadcast_transfer_asserts_b_and_c() -> None:
    case = cases_by_id()["MAIN-005"]
    devices = make_transfer_devices(("A", "B", "C"))
    runner = FormalAtRunner(devices)

    result = runner.run_case(case)

    assert result.status == "PASS"
    assert devices["A"].serial.written_hex == [
        f"01{TRANSFER_PAYLOAD_HEX}",
        f"01{TRANSFER_PAYLOAD_HEX}",
    ]
    assert "AT+KEY123456" in devices["A"].at.calls
    assert "AT+KEY123456" in devices["B"].at.calls
    assert "AT+KEY123456" in devices["C"].at.calls
    assert any("B: received" in step for step in result.steps)
    assert any("C: received" in step for step in result.steps)

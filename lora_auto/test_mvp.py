"""MVP case runner for LoRa module automation."""

from __future__ import annotations

import argparse
import logging
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import yaml

# Allow running this file directly from a source checkout.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from lora_auto.libs.assertions import assert_payload_equal
from lora_auto.libs.lora_device import LoraDevice, LoraDeviceError
from lora_auto.libs.report import ReportCase, ReportStep, utc_now_iso, write_device_log, write_reports

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class CaseResult:
    """Console-level case result for MVP execution."""

    case_id: str
    case_name: str
    status: str
    failure_reason: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    duration: float = 0.0
    steps: tuple[str, ...] = ()
    log_file: str | None = None


class MvpRunnerError(RuntimeError):
    """Raised when MVP runner setup or execution fails."""


def load_yaml(path: str | Path) -> dict[str, Any]:
    """Load a YAML file as a dictionary."""

    try:
        with Path(path).open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    except OSError as exc:
        raise MvpRunnerError(f"failed to read YAML file {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise MvpRunnerError(f"YAML file {path} must contain a mapping")
    return data


def load_devices(
    path: str | Path,
    device_factory: Callable[..., LoraDevice] = LoraDevice,
) -> dict[str, LoraDevice]:
    """Create devices from a devices.yaml file."""

    data = load_yaml(path)
    raw_devices = data.get("devices")
    if not isinstance(raw_devices, dict) or not raw_devices:
        raise MvpRunnerError("devices.yaml must contain a non-empty 'devices' mapping")

    devices: dict[str, LoraDevice] = {}
    for name, config in raw_devices.items():
        if not isinstance(config, dict):
            raise MvpRunnerError(f"device {name!r} config must be a mapping")
        try:
            port = config["port"]
        except KeyError as exc:
            raise MvpRunnerError(f"device {name!r} is missing required field 'port'") from exc

        baudrate = int(config.get("baudrate", 9600))
        role = config.get("role")
        devices[name] = device_factory(name=name, port=port, baudrate=baudrate, role=role)

    return devices


def load_cases(path: str | Path) -> list[dict[str, Any]]:
    """Load MVP case definitions."""

    data = load_yaml(path)
    cases = data.get("cases")
    if not isinstance(cases, list) or not cases:
        raise MvpRunnerError("mvp_cases.yaml must contain a non-empty 'cases' list")
    for case in cases:
        if not isinstance(case, dict):
            raise MvpRunnerError("each case must be a mapping")
        if "id" not in case or "name" not in case or "type" not in case:
            raise MvpRunnerError("each case must include id, name, and type")
    return cases


def select_cases(cases: list[dict[str, Any]], case_id: str | None = None) -> list[dict[str, Any]]:
    """Return all cases or one requested case."""

    if case_id is None:
        return cases
    selected = [case for case in cases if case.get("id") == case_id]
    if not selected:
        raise MvpRunnerError(f"case {case_id!r} not found")
    return selected


class MvpRunner:
    """Executes the MVP case types."""

    def __init__(self, devices: dict[str, LoraDevice], report_dir: str | Path = "reports") -> None:
        self.devices = devices
        self.report_dir = Path(report_dir)

    def run_case(self, case: dict[str, Any]) -> CaseResult:
        case_type = case["type"]
        case_id = case["id"]
        case_name = case["name"]
        start_time = utc_now_iso()
        start_monotonic = time.monotonic()
        steps: list[str] = []

        try:
            if case_type == "at":
                steps = self._run_at_case(case)
            elif case_type == "config":
                steps = self._run_config_case(case)
            elif case_type == "transparent_transfer":
                steps = self._run_transparent_transfer_case(case)
            else:
                raise MvpRunnerError(f"unsupported case type {case_type!r}")
        except Exception as exc:
            end_time = utc_now_iso()
            duration = time.monotonic() - start_monotonic
            return self._build_result(
                case_id=case_id,
                case_name=case_name,
                status="FAIL",
                start_time=start_time,
                end_time=end_time,
                duration=duration,
                steps=steps,
                failure_reason=str(exc),
            )

        end_time = utc_now_iso()
        duration = time.monotonic() - start_monotonic
        return self._build_result(
            case_id=case_id,
            case_name=case_name,
            status="PASS",
            start_time=start_time,
            end_time=end_time,
            duration=duration,
            steps=steps,
        )

    def build_blocked_result(self, case: dict[str, Any], reason: str) -> CaseResult:
        """Create a blocked result for a case that should not be executed."""

        timestamp = utc_now_iso()
        return self._build_result(
            case_id=case["id"],
            case_name=case["name"],
            status="BLOCKED",
            start_time=timestamp,
            end_time=timestamp,
            duration=0.0,
            steps=[],
            failure_reason=reason,
        )

    def _build_result(
        self,
        case_id: str,
        case_name: str,
        status: str,
        start_time: str,
        end_time: str,
        duration: float,
        steps: list[str],
        failure_reason: str | None = None,
    ) -> CaseResult:
        log_lines = [
            f"case_id={case_id}",
            f"case_name={case_name}",
            f"status={status}",
        ]
        if failure_reason:
            log_lines.append(f"failure_reason={failure_reason}")
        log_lines.extend(steps)
        log_file = write_device_log(self.report_dir, case_id, "runner", log_lines)
        return CaseResult(
            case_id=case_id,
            case_name=case_name,
            status=status,
            failure_reason=failure_reason,
            start_time=start_time,
            end_time=end_time,
            duration=duration,
            steps=tuple(steps),
            log_file=log_file,
        )

    def open_devices(self) -> None:
        for device in self.devices.values():
            device.open()

    def close_devices(self) -> None:
        for device in self.devices.values():
            device.close()

    def _get_device(self, name: str) -> LoraDevice:
        try:
            return self.devices[name]
        except KeyError as exc:
            raise MvpRunnerError(f"device {name!r} not found") from exc

    def _run_at_case(self, case: dict[str, Any]) -> list[str]:
        device = self._get_device(case["device"])
        steps = case.get("steps", [])
        if not isinstance(steps, list) or not steps:
            raise MvpRunnerError(f"case {case['id']} must define at least one AT step")

        executed_steps: list[str] = []
        entry = device.at.enter_at()
        executed_steps.append(f"{device.name}: +++ -> {entry.response!r}")
        if not entry.passed:
            raise MvpRunnerError(
                f"failed to enter AT mode: expected {entry.expected!r}, response {entry.response!r}"
            )

        for step in steps:
            command = step["command"]
            expected = step.get("expected", "OK")
            result = device.at.send_cmd(command, expected=expected)
            executed_steps.append(f"{device.name}: {command} -> {result.response!r}")
            if not result.passed:
                raise MvpRunnerError(
                    f"AT command {command!r} failed: expected {expected!r}, response {result.response!r}"
                )

        exit_result = device.at.exit_at()
        executed_steps.append(f"{device.name}: +++ -> {exit_result.response!r}")
        if not exit_result.passed:
            raise MvpRunnerError(
                f"failed to exit AT mode: expected {exit_result.expected!r}, response {exit_result.response!r}"
            )
        return executed_steps

    def _run_config_case(self, case: dict[str, Any]) -> list[str]:
        device_names = case.get("devices", [])
        config = case.get("config", {})
        if not isinstance(device_names, list) or not device_names:
            raise MvpRunnerError(f"case {case['id']} must define target devices")
        if not isinstance(config, dict):
            raise MvpRunnerError(f"case {case['id']} config must be a mapping")

        executed_steps: list[str] = []
        for device_name in device_names:
            device = self._get_device(device_name)
            device.serial.clear_buffer()
            try:
                command_steps = device.configure_transparent_mode(
                    sleep=str(config.get("sleep", "2")),
                    mode=str(config.get("mode", "0")),
                    level=str(config.get("level", "2")),
                    channel=str(config.get("channel", "00")),
                )
            except LoraDeviceError as exc:
                raise MvpRunnerError(str(exc)) from exc
            for command_step in command_steps:
                executed_steps.append(f"{device.name}: {command_step.command} -> {command_step.response!r}")
        return executed_steps

    def _run_transparent_transfer_case(self, case: dict[str, Any]) -> list[str]:
        sender = self._get_device(case["sender"])
        receiver = self._get_device(case["receiver"])
        payload = str(case["payload"])
        expected = str(case.get("expected", payload))
        timeout = float(case.get("timeout", 5))

        sender.serial.clear_buffer()
        receiver.serial.clear_buffer()
        sender.serial.write_text(payload, append_newline=False)
        received = receiver.serial.read_all(timeout=timeout)

        assertion = assert_payload_equal(expected, received)
        if not assertion.passed:
            raise MvpRunnerError(
                "receiver did not receive expected payload within "
                f"{timeout}s; sent={payload!r}, received={received!r}"
            )
        return [
            f"{sender.name}: sent={payload!r}",
            f"{receiver.name}: received={received!r}",
        ]


def should_block_case(case: dict[str, Any], results: list[CaseResult]) -> str | None:
    """Return a blocking reason for cases whose prerequisites failed."""

    if case.get("type") != "transparent_transfer":
        return None
    failed_config = next(
        (result for result in results if result.case_id == "MVP-002" and result.status != "PASS"),
        None,
    )
    if failed_config is None:
        return None
    return f"前置配置用例 MVP-002 未通过，跳过透明传输测试：{failed_config.failure_reason}"


def run_cases_with_dependencies(runner: MvpRunner, cases: list[dict[str, Any]]) -> list[CaseResult]:
    """Run cases in order and block dependent cases when prerequisites fail."""

    results: list[CaseResult] = []
    for case in cases:
        block_reason = should_block_case(case, results)
        if block_reason is not None:
            results.append(runner.build_blocked_result(case, block_reason))
            continue
        results.append(runner.run_case(case))
    return results


def to_report_case(result: CaseResult) -> ReportCase:
    """Convert runner result to serializable report entry."""

    return ReportCase(
        case_id=result.case_id,
        case_name=result.case_name,
        status=result.status,
        start_time=result.start_time or "",
        end_time=result.end_time or "",
        duration=result.duration,
        steps=[ReportStep(name=step, status=result.status, detail=step) for step in result.steps],
        failure_reason=result.failure_reason,
        log_file=result.log_file,
    )


def print_result(result: CaseResult) -> None:
    """Print the console result format."""

    print(f"[{result.case_id}] {result.case_name} {result.status}")
    if result.failure_reason:
        print(f"失败原因：{result.failure_reason}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run LoRa automation MVP cases.")
    parser.add_argument("--config", default="lora_auto/config/devices.yaml", help="Device config YAML path.")
    parser.add_argument("--cases", default="lora_auto/config/mvp_cases.yaml", help="MVP cases YAML path.")
    parser.add_argument("--case", dest="case_id", default=None, help="Run only one case ID.")
    parser.add_argument("--log-level", default="INFO", help="Python logging level. Default: INFO.")
    parser.add_argument("--report-dir", default="reports", help="Report output directory.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))

    devices = load_devices(args.config)
    cases = select_cases(load_cases(args.cases), args.case_id)
    runner = MvpRunner(devices, report_dir=args.report_dir)

    try:
        runner.open_devices()
        results = run_cases_with_dependencies(runner, cases)
    finally:
        runner.close_devices()

    for result in results:
        print_result(result)

    json_path, markdown_path = write_reports(args.report_dir, [to_report_case(result) for result in results])
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {markdown_path}")

    return 1 if any(result.status != "PASS" for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())

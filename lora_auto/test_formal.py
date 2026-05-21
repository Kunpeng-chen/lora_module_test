"""Formal case runner for LoRa module automation."""

from __future__ import annotations

import argparse
import logging
import re
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

from lora_auto.libs.formal_cases import load_formal_case_directory
from lora_auto.libs.lora_device import LoraDevice
from lora_auto.libs.report import ReportCase, ReportStep, utc_now_iso, write_device_log, write_reports

LOGGER = logging.getLogger(__name__)
SUPPORTED_SUITES = frozenset({"at", "error_at", "main"})
TRANSFER_ACTIONS = frozenset(
    {
        "configure_transfer_round",
        "send_plain_payload",
        "send_fixed_payload",
        "send_broadcast_payload",
        "receive_payload",
        "multi_receiver_assert",
    }
)


@dataclass(frozen=True)
class FormalCaseResult:
    """Console-level case result for formal execution."""

    case_id: str
    case_name: str
    status: str
    failure_reason: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    duration: float = 0.0
    steps: tuple[str, ...] = ()
    log_file: str | None = None


class FormalRunnerError(RuntimeError):
    """Raised when formal runner setup or execution fails."""


def load_yaml(path: str | Path) -> dict[str, Any]:
    """Load a YAML file as a dictionary."""

    try:
        with Path(path).open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    except OSError as exc:
        raise FormalRunnerError(f"failed to read YAML file {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise FormalRunnerError(f"YAML file {path} must contain a mapping")
    return data


def load_devices(
    path: str | Path,
    device_factory: Callable[..., LoraDevice] = LoraDevice,
) -> dict[str, LoraDevice]:
    """Create devices from a devices.yaml file."""

    data = load_yaml(path)
    raw_devices = data.get("devices")
    if not isinstance(raw_devices, dict) or not raw_devices:
        raise FormalRunnerError("devices.yaml must contain a non-empty 'devices' mapping")

    devices: dict[str, LoraDevice] = {}
    for name, config in raw_devices.items():
        if not isinstance(config, dict):
            raise FormalRunnerError(f"device {name!r} config must be a mapping")
        try:
            port = config["port"]
        except KeyError as exc:
            raise FormalRunnerError(f"device {name!r} is missing required field 'port'") from exc

        baudrate = int(config.get("baudrate", 9600))
        role = config.get("role")
        devices[name] = device_factory(name=name, port=port, baudrate=baudrate, role=role)

    return devices


def load_formal_cases(cases_dir: str | Path) -> list[dict[str, Any]]:
    """Load formal cases from the standard formal case directory."""

    return load_formal_case_directory(cases_dir)


def is_query_only_case(case: dict[str, Any]) -> bool:
    """Return whether a normal AT case contains only non-mutating AT query/send steps."""

    return case.get("suite") == "at" and all(
        step.get("action") == "send_at" for step in case.get("steps", [])
    )


def is_error_at_case(case: dict[str, Any]) -> bool:
    """Return whether a case is an executable negative AT flow with a health check."""

    steps = case.get("steps", [])
    return (
        case.get("suite") == "error_at"
        and len(steps) >= 2
        and steps[-1].get("action") == "post_check"
        and all(step.get("action") in {"send_at", "post_check"} for step in steps)
    )


def is_transfer_case(case: dict[str, Any]) -> bool:
    """Return whether a main-suite formal case can be executed by the transfer runner."""

    steps = case.get("steps", [])
    return (
        case.get("suite") == "main"
        and bool(steps)
        and all(step.get("action") in TRANSFER_ACTIONS for step in steps)
    )


def is_auto_runnable(case: dict[str, Any]) -> bool:
    """Return whether a case is safe for default automatic execution."""

    metadata = case.get("metadata", {})
    if (
        is_transfer_case(case)
        and case.get("automation_level") == "auto"
        and metadata.get("run_policy") == "auto"
        and metadata.get("destructive") is not True
    ):
        return True

    return (
        case.get("automation_level") == "auto"
        and metadata.get("run_policy") == "auto"
        and metadata.get("destructive") is not True
        and metadata.get("state_changing") is not True
        and (is_query_only_case(case) or is_error_at_case(case))
    )


def select_cases(
    cases: list[dict[str, Any]],
    suite: str | None = None,
    case_id: str | None = None,
    include_manual: bool = False,
) -> list[dict[str, Any]]:
    """Select formal cases by suite or case ID.

    By default this only returns cases that are safe for automatic execution.
    Manual-confirm and destructive cases can be listed by dry-run, but they are
    not selected for execution unless include_manual is explicitly enabled.
    """

    if case_id is not None:
        selected = [case for case in cases if case.get("id") == case_id]
        if not selected:
            raise FormalRunnerError(f"case {case_id!r} not found")
    else:
        selected = [case for case in cases if suite is None or case.get("suite") == suite]
        if not selected:
            raise FormalRunnerError(f"suite {suite!r} did not match any cases")

    if include_manual:
        return selected

    auto_cases = [case for case in selected if is_auto_runnable(case)]
    if case_id is not None and not auto_cases:
        raise FormalRunnerError(
            f"case {case_id!r} requires manual confirmation or is not selected by default"
        )
    return auto_cases


def describe_case_selection(cases: list[dict[str, Any]]) -> list[str]:
    """Return human-readable dry-run plan lines."""

    lines: list[str] = []
    for case in cases:
        marker = "RUN" if is_auto_runnable(case) else "SKIP"
        reason = ""
        if marker == "SKIP":
            metadata = case.get("metadata", {})
            reason = f" ({case.get('automation_level')}, {metadata.get('run_policy')})"
        lines.append(f"[{marker}] {case['id']} {case['scenario']}{reason}")
        for step in case.get("steps", []):
            lines.append(f"  - {step['action']} {step.get('device') or '-'} {step.get('command') or '-'}")
    return lines


class FormalAtRunner:
    """Executes formal AT and formal transfer cases."""

    def __init__(self, devices: dict[str, LoraDevice], report_dir: str | Path = "reports") -> None:
        self.devices = devices
        self.report_dir = Path(report_dir)

    def open_devices(self) -> None:
        for device in self.devices.values():
            device.open()

    def close_devices(self) -> None:
        for device in self.devices.values():
            device.close()

    def run_case(self, case: dict[str, Any]) -> FormalCaseResult:
        if case.get("suite") not in SUPPORTED_SUITES:
            return self._build_result(
                case=case,
                status="BLOCKED",
                start_time=utc_now_iso(),
                end_time=utc_now_iso(),
                duration=0.0,
                steps=[],
                failure_reason=(
                    f"formal runner currently supports only {sorted(SUPPORTED_SUITES)}, "
                    f"got {case.get('suite')!r}"
                ),
            )
        if not is_auto_runnable(case):
            return self._build_result(
                case=case,
                status="BLOCKED",
                start_time=utc_now_iso(),
                end_time=utc_now_iso(),
                duration=0.0,
                steps=[],
                failure_reason="case requires manual confirmation or is not run automatically",
            )

        if is_transfer_case(case):
            return self._run_transfer_case(case)
        return self._run_at_case(case)

    def _run_at_case(self, case: dict[str, Any]) -> FormalCaseResult:
        start_time = utc_now_iso()
        start_monotonic = time.monotonic()
        executed_steps: list[str] = []

        try:
            device_names = [step.get("device") for step in case.get("steps", []) if step.get("device")]
            for device_name in dict.fromkeys(device_names):
                executed_steps.extend(self.ensure_at_mode(self._get_device(device_name)))
            for step in case.get("steps", []):
                executed_steps.append(self._run_at_step(case, step))
        except Exception as exc:
            end_time = utc_now_iso()
            duration = time.monotonic() - start_monotonic
            return self._build_result(
                case=case,
                status="FAIL",
                start_time=start_time,
                end_time=end_time,
                duration=duration,
                steps=executed_steps,
                failure_reason=str(exc),
            )

        end_time = utc_now_iso()
        duration = time.monotonic() - start_monotonic
        return self._build_result(
            case=case,
            status="PASS",
            start_time=start_time,
            end_time=end_time,
            duration=duration,
            steps=executed_steps,
        )

    def _run_transfer_case(self, case: dict[str, Any]) -> FormalCaseResult:
        start_time = utc_now_iso()
        start_monotonic = time.monotonic()
        executed_steps: list[str] = []
        current_roles: dict[str, Any] = {}

        try:
            for step in case.get("steps", []):
                action = step["action"]
                if action == "configure_transfer_round":
                    current_roles = step.get("roles") or {}
                    executed_steps.extend(self._configure_transfer_round(case, step))
                elif action == "send_plain_payload":
                    executed_steps.append(self._send_plain_payload(case, step, current_roles))
                elif action == "send_fixed_payload":
                    executed_steps.append(self._send_fixed_payload(case, step, current_roles))
                elif action == "send_broadcast_payload":
                    executed_steps.append(self._send_broadcast_payload(case, step, current_roles))
                elif action == "receive_payload":
                    executed_steps.append(self._receive_payload(case, step))
                elif action == "multi_receiver_assert":
                    executed_steps.extend(self._multi_receiver_assert(case, step))
                else:
                    raise FormalRunnerError(f"case {case['id']} has unsupported transfer action {action!r}")
        except Exception as exc:
            end_time = utc_now_iso()
            duration = time.monotonic() - start_monotonic
            return self._build_result(
                case=case,
                status="FAIL",
                start_time=start_time,
                end_time=end_time,
                duration=duration,
                steps=executed_steps,
                failure_reason=str(exc),
            )

        end_time = utc_now_iso()
        duration = time.monotonic() - start_monotonic
        return self._build_result(
            case=case,
            status="PASS",
            start_time=start_time,
            end_time=end_time,
            duration=duration,
            steps=executed_steps,
        )

    def ensure_at_mode(self, device: LoraDevice) -> list[str]:
        """Ensure a device is in AT mode before running query-style AT cases."""

        probe = device.at.send_cmd("AT", expected="OK", timeout=0.5)
        if probe.passed:
            return [f"{device.name}: ensure_at_mode already in AT mode -> {probe.response!r}"]

        enter = device.at.enter_at(timeout=2.0)
        if not enter.passed:
            raise FormalRunnerError(
                f"{device.name}: failed to enter AT mode, response {enter.response!r}"
            )

        verify = device.at.send_cmd("AT", expected="OK", timeout=2.0)
        if not verify.passed:
            raise FormalRunnerError(
                f"{device.name}: AT mode verification failed after entry, response {verify.response!r}"
            )

        return [
            f"{device.name}: ensure_at_mode probe failed -> {probe.response!r}",
            f"{device.name}: enter_at -> {enter.response!r}",
            f"{device.name}: ensure_at_mode verified -> {verify.response!r}",
        ]

    def ensure_work_mode(self, device: LoraDevice) -> list[str]:
        """Ensure a device is in work mode before payload transfer IO."""

        if not hasattr(device, "ensure_work_mode"):
            return []
        steps = device.ensure_work_mode()
        return [f"{device.name}: {step.command} -> {step.response!r}" for step in steps]

    def _run_at_step(self, case: dict[str, Any], step: dict[str, Any]) -> str:
        action = step["action"]
        device = self._get_device(step.get("device"))
        command = step.get("command")
        expected = step.get("expected")
        read_until = expected_read_until(expected)

        if action == "enter_at":
            result = device.at.enter_at()
        elif action == "exit_at":
            result = device.at.exit_at()
        elif action == "reset":
            result = device.at.reset(expected=read_until)
        elif action in {"send_at", "post_check"}:
            result = device.at.send_cmd(command, expected=read_until)
        else:
            raise FormalRunnerError(f"case {case['id']} has unsupported AT action {action!r}")

        passed, message = match_expected(result.response, expected)
        detail = f"{device.name}: {command or result.command} -> {result.response!r}"
        if not result.passed or not passed:
            raise FormalRunnerError(
                f"{detail}; expected {expected!r}; result={result.message}; assertion={message}"
            )
        return detail

    def _configure_transfer_round(self, case: dict[str, Any], step: dict[str, Any]) -> list[str]:
        config = step.get("config")
        if not isinstance(config, dict) or not config:
            raise FormalRunnerError(f"case {case['id']} configure_transfer_round must define config")

        transfer_type = str(step.get("transfer_type") or case.get("feature"))
        details: list[str] = []
        for device_name, device_config in config.items():
            if not isinstance(device_config, dict):
                raise FormalRunnerError(f"case {case['id']} device config for {device_name!r} must be a mapping")
            device = self._get_device(str(device_name))
            device.serial.clear_buffer()
            details.append(self._enter_at_for_config(device))
            commands = self._build_transfer_config_commands(transfer_type, device_config)
            for command in commands:
                details.append(self._send_config_command(device, command))
            details.append(self._reset_after_config(device))
        return details

    def _build_transfer_config_commands(
        self,
        transfer_type: str,
        device_config: dict[str, Any],
    ) -> list[str]:
        sleep = normalize_at_value(device_config.get("sleep", "SLEEP2"), "SLEEP")
        mode = normalize_at_value(device_config.get("mode", default_mode_for_transfer(transfer_type)), "MODE")
        level = normalize_at_value(device_config.get("level", "2"), "LEVEL")
        channel = normalize_hex_value(device_config.get("channel", "01"))
        mac = normalize_mac_value(device_config.get("mac"))
        key = device_config.get("key")

        commands = [
            f"AT+SLEEP{sleep}",
            f"AT+MODE{mode}",
            f"AT+LEVEL{level}",
            f"AT+CHANNEL{channel}",
        ]
        if mac:
            commands.append(f"AT+MAC{mac}")
        if key is not None:
            commands.append(f"AT+KEY{key}")
        return commands

    def _enter_at_for_config(self, device: LoraDevice) -> str:
        result = device.at.enter_at(timeout=2.0)
        detail = f"{device.name}: +++ -> {result.response!r}"
        if not result.passed:
            raise FormalRunnerError(f"{detail}; failed to enter AT mode for transfer config")
        return detail

    def _send_config_command(self, device: LoraDevice, command: str) -> str:
        result = device.at.send_cmd(command, expected="OK")
        detail = f"{device.name}: {command} -> {result.response!r}"
        if not result.passed:
            raise FormalRunnerError(f"{detail}; expected OK")
        return detail

    def _reset_after_config(self, device: LoraDevice) -> str:
        result = device.at.reset(expected="OK")
        detail = f"{device.name}: AT+RESET -> {result.response!r}"
        if not result.passed:
            raise FormalRunnerError(f"{detail}; expected OK")
        return detail

    def _send_plain_payload(
        self,
        case: dict[str, Any],
        step: dict[str, Any],
        current_roles: dict[str, Any],
    ) -> str:
        device = self._get_device(step.get("device"))
        payload = str((step.get("payload") or {}).get("payload") or step.get("command") or "")
        if not payload:
            raise FormalRunnerError(f"case {case['id']} send_plain_payload must define payload")
        self._clear_transfer_buffers(device, current_roles)
        device.serial.write_text(payload, append_newline=False)
        return f"{device.name}: sent plain payload {payload!r}"

    def _send_fixed_payload(
        self,
        case: dict[str, Any],
        step: dict[str, Any],
        current_roles: dict[str, Any],
    ) -> str:
        device = self._get_device(step.get("device"))
        payload = build_fixed_hex_frame(step.get("payload"))
        self._clear_transfer_buffers(device, current_roles)
        device.serial.write_hex(payload)
        return f"{device.name}: sent fixed hex {payload}"

    def _send_broadcast_payload(
        self,
        case: dict[str, Any],
        step: dict[str, Any],
        current_roles: dict[str, Any],
    ) -> str:
        device = self._get_device(step.get("device"))
        payload = build_broadcast_hex_frame(step.get("payload"))
        self._clear_transfer_buffers(device, current_roles)
        device.serial.write_hex(payload)
        return f"{device.name}: sent broadcast hex {payload}"

    def _clear_transfer_buffers(self, sender: LoraDevice, current_roles: dict[str, Any]) -> None:
        self.ensure_work_mode(sender)
        sender.serial.clear_buffer()
        for receiver_name in current_roles.get("receivers", []) or []:
            receiver = self._get_device(str(receiver_name))
            self.ensure_work_mode(receiver)
            receiver.serial.clear_buffer()

    def _receive_payload(self, case: dict[str, Any], step: dict[str, Any]) -> str:
        device = self._get_device(step.get("device"))
        self.ensure_work_mode(device)
        expected = step.get("expected")
        read_until = expected_read_until(expected)
        response = device.serial.read_until(read_until, timeout=float(step.get("timeout", 5.0)))
        passed, message = match_expected(response.data, expected)
        detail = f"{device.name}: received {response.data!r}"
        if not response.matched or not passed:
            raise FormalRunnerError(f"{detail}; expected {expected!r}; assertion={message}")
        return detail

    def _multi_receiver_assert(self, case: dict[str, Any], step: dict[str, Any]) -> list[str]:
        expected = step.get("expected")
        if not isinstance(expected, dict):
            raise FormalRunnerError(f"case {case['id']} multi_receiver_assert must define expected")
        receivers = expected.get("receivers")
        value = expected.get("value")
        if not isinstance(receivers, list) or not receivers:
            raise FormalRunnerError(f"case {case['id']} multi_receiver_assert must define receivers")
        details: list[str] = []
        for receiver_name in receivers:
            device = self._get_device(str(receiver_name))
            self.ensure_work_mode(device)
            response = device.serial.read_until(str(value), timeout=float(step.get("timeout", 5.0)))
            detail = f"{device.name}: received {response.data!r}"
            if not response.matched or str(value) not in response.data:
                raise FormalRunnerError(f"{detail}; expected receiver payload {value!r}")
            details.append(detail)
        return details

    def _get_device(self, name: str | None) -> LoraDevice:
        if not name:
            raise FormalRunnerError("formal step must define a device")
        try:
            return self.devices[name]
        except KeyError as exc:
            raise FormalRunnerError(f"device {name!r} not found") from exc

    def _build_result(
        self,
        case: dict[str, Any],
        status: str,
        start_time: str,
        end_time: str,
        duration: float,
        steps: list[str],
        failure_reason: str | None = None,
    ) -> FormalCaseResult:
        case_id = case["id"]
        case_name = case["scenario"]
        log_lines = [
            f"case_id={case_id}",
            f"case_name={case_name}",
            f"status={status}",
        ]
        if failure_reason:
            log_lines.append(f"failure_reason={failure_reason}")
        log_lines.extend(steps)
        log_file = write_device_log(self.report_dir, case_id, "runner", log_lines)
        return FormalCaseResult(
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


def normalize_at_value(value: Any, prefix: str) -> str:
    """Normalize YAML values such as SLEEP2 or MODE0 to the AT suffix value."""

    text = str(value)
    if text.upper().startswith(prefix):
        return text[len(prefix) :]
    return text


def normalize_hex_value(value: Any) -> str:
    """Normalize one hex field by removing common separators."""

    return str(value).replace(",", "").replace(" ", "").upper()


def normalize_mac_value(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if "," in text else f"{text[:2]},{text[2:]}"


def default_mode_for_transfer(transfer_type: str) -> str:
    """Return the default AT+MODE suffix for a transfer type."""

    if transfer_type == "transparent_transfer":
        return "0"
    return "1"


def ascii_to_hex(payload: str) -> str:
    """Encode a text payload as uppercase hexadecimal bytes."""

    return payload.encode("utf-8").hex().upper()


def build_fixed_hex_frame(payload_config: Any) -> str:
    """Build target_mac + channel + data for a fixed-transfer HEX frame."""

    if not isinstance(payload_config, dict):
        raise FormalRunnerError("fixed payload must be a mapping")
    target_mac = normalize_hex_value(payload_config.get("target_mac"))
    channel = normalize_hex_value(payload_config.get("channel"))
    payload = str(payload_config.get("payload", ""))
    if not target_mac or not channel or not payload:
        raise FormalRunnerError("fixed payload requires target_mac, channel, and payload")
    return f"{target_mac}{channel}{ascii_to_hex(payload)}"


def build_broadcast_hex_frame(payload_config: Any) -> str:
    """Build channel + data for a broadcast-transfer HEX frame."""

    if not isinstance(payload_config, dict):
        raise FormalRunnerError("broadcast payload must be a mapping")
    channel = normalize_hex_value(payload_config.get("channel"))
    payload = str(payload_config.get("payload", ""))
    if not channel or not payload:
        raise FormalRunnerError("broadcast payload requires channel and payload")
    return f"{channel}{ascii_to_hex(payload)}"


def expected_read_until(expected: dict[str, Any]) -> str:
    """Choose a concrete substring for serial read_until from a structured expectation."""

    mode = expected.get("mode")
    if mode in {"contains", "exact"}:
        return str(expected.get("value"))
    if mode == "contains_all":
        values = expected.get("values")
        if not isinstance(values, list) or not values:
            raise FormalRunnerError("contains_all expectation must include a non-empty values list")
        return str(values[0])
    if mode == "contains_all_receivers":
        return str(expected.get("value"))
    if mode == "regex":
        value = str(expected.get("value", ""))
        prefix_match = re.match(r"\\\+([A-Z]+)=", value)
        if prefix_match:
            return f"+{prefix_match.group(1)}="
        return "OK"
    raise FormalRunnerError(f"unsupported expected mode {mode!r}")


def match_expected(response: str, expected: dict[str, Any]) -> tuple[bool, str]:
    """Evaluate a structured formal expectation against a response string."""

    mode = expected.get("mode")
    if mode == "contains":
        value = str(expected.get("value"))
        return (value in response, f"expected response to contain {value!r}")
    if mode == "contains_all":
        values = expected.get("values")
        if not isinstance(values, list) or not values:
            raise FormalRunnerError("contains_all expectation must include a non-empty values list")
        missing = [str(value) for value in values if str(value) not in response]
        return (not missing, f"expected response to contain all values; missing={missing!r}")
    if mode == "contains_all_receivers":
        value = str(expected.get("value"))
        return (value in response, f"expected all receivers to contain {value!r}")
    if mode == "regex":
        pattern = str(expected.get("value"))
        return (re.search(pattern, response) is not None, f"expected response to match regex {pattern!r}")
    if mode == "exact":
        value = str(expected.get("value"))
        return (response.strip() == value, f"expected stripped response to equal {value!r}")
    raise FormalRunnerError(f"unsupported expected mode {mode!r}")


def run_cases(runner: FormalAtRunner, cases: list[dict[str, Any]]) -> list[FormalCaseResult]:
    """Run selected formal cases in order."""

    return [runner.run_case(case) for case in cases]


def to_report_case(result: FormalCaseResult) -> ReportCase:
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


def print_result(result: FormalCaseResult) -> None:
    """Print the console result format."""

    print(f"[{result.case_id}] {result.case_name} {result.status}")
    if result.failure_reason:
        print(f"失败原因：{result.failure_reason}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run LoRa formal cases.")
    parser.add_argument("--config", default="lora_auto/config/devices.yaml", help="Device config YAML path.")
    parser.add_argument("--cases-dir", default="lora_auto/config/formal", help="Formal case directory.")
    parser.add_argument("--suite", default="at", help="Run a formal suite. Supports 'at', 'error_at', and 'main'.")
    parser.add_argument("--case", dest="case_id", default=None, help="Run only one case ID.")
    parser.add_argument("--include-manual", action="store_true", help="Include manual-confirm cases in selection.")
    parser.add_argument("--dry-run", action="store_true", help="Print the selected execution plan without opening hardware.")
    parser.add_argument("--log-level", default="INFO", help="Python logging level. Default: INFO.")
    parser.add_argument("--report-dir", default="reports", help="Report output directory.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))

    cases = load_formal_cases(args.cases_dir)
    if args.dry_run:
        selected = [case for case in cases if case.get("id") == args.case_id] if args.case_id else [
            case for case in cases if case.get("suite") == args.suite
        ]
        if not selected:
            raise FormalRunnerError(f"no formal cases matched suite={args.suite!r} case={args.case_id!r}")
        for line in describe_case_selection(selected):
            print(line)
        return 0

    selected = select_cases(
        cases,
        suite=args.suite,
        case_id=args.case_id,
        include_manual=args.include_manual,
    )
    devices = load_devices(args.config)
    runner = FormalAtRunner(devices, report_dir=args.report_dir)

    try:
        runner.open_devices()
        results = run_cases(runner, selected)
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

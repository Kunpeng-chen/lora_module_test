"""LoRa device abstraction for automation flows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

from lora_auto.libs.at_client import AtClient, AtClientError, AtCommandResult
from lora_auto.libs.serial_client import SerialClient

DeviceMode = Literal["at", "work", "unknown"]


class LoraDeviceError(RuntimeError):
    """Raised when a LoRa device operation fails."""


@dataclass(frozen=True)
class LoraDeviceConfig:
    """Connection and role metadata for one LoRa module."""

    name: str
    port: str
    baudrate: int = 9600
    role: Optional[str] = None


@dataclass(frozen=True)
class DeviceCommandStep:
    """One command executed during a device setup flow."""

    command: str
    expected: str
    response: str
    passed: bool


@dataclass(frozen=True)
class DeviceModeProbe:
    """Observed module mode from a lightweight AT probe."""

    mode: DeviceMode
    command: str
    response: str
    passed: bool


class LoraDevice:
    """Represents one LoRa module attached to one serial port."""

    def __init__(
        self,
        name: str,
        port: str,
        baudrate: int = 9600,
        role: Optional[str] = None,
        serial_client: Optional[SerialClient] = None,
        at_client: Optional[AtClient] = None,
    ) -> None:
        self.config = LoraDeviceConfig(name=name, port=port, baudrate=baudrate, role=role)
        self.serial = serial_client or SerialClient(port=port, baudrate=baudrate)
        self.at = at_client or AtClient(self.serial)

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def port(self) -> str:
        return self.config.port

    @property
    def baudrate(self) -> int:
        return self.config.baudrate

    @property
    def role(self) -> Optional[str]:
        return self.config.role

    def open(self) -> None:
        """Open the underlying serial port."""

        self.serial.open()

    def close(self) -> None:
        """Close the underlying serial port."""

        self.serial.close()

    def detect_mode(self, timeout: float = 0.5) -> DeviceModeProbe:
        """Probe whether the device is currently in AT mode.

        ``AT -> OK`` means the module is in AT mode. A non-matching response is
        treated as work mode because sending ``AT`` in transparent mode is just a
        short user payload. Serial/AT transport errors are surfaced as
        ``unknown`` so callers can fail before mutating state.
        """

        try:
            result = self.at.send_cmd("AT", expected="OK", timeout=timeout)
        except AtClientError as exc:
            return DeviceModeProbe(mode="unknown", command="AT", response=str(exc), passed=False)

        mode: DeviceMode = "at" if result.passed else "work"
        return DeviceModeProbe(mode=mode, command=result.command, response=result.response, passed=result.passed)

    def ensure_at_mode(
        self,
        probe_timeout: float = 0.5,
        enter_timeout: float = 2.0,
    ) -> list[DeviceCommandStep]:
        """Ensure the module is in AT mode before AT/config operations."""

        probe = self.detect_mode(timeout=probe_timeout)
        steps = [
            DeviceCommandStep(
                command=probe.command,
                expected="OK",
                response=probe.response,
                passed=probe.mode == "at",
            )
        ]
        if probe.mode == "at":
            return steps
        if probe.mode == "unknown":
            raise LoraDeviceError(f"{self.name}: unable to detect device mode: {probe.response!r}")

        try:
            enter = self.at.enter_at(timeout=enter_timeout)
        except AtClientError as exc:
            raise LoraDeviceError(f"{self.name}: failed to enter AT mode: {exc}") from exc
        enter_step = self._to_step(enter)
        steps.append(enter_step)
        if not enter_step.passed:
            raise LoraDeviceError(
                f"{self.name}: failed to enter AT mode, expected {enter_step.expected!r}, "
                f"response {enter_step.response!r}"
            )

        verify = self.detect_mode(timeout=enter_timeout)
        verify_step = DeviceCommandStep(
            command=verify.command,
            expected="OK",
            response=verify.response,
            passed=verify.mode == "at",
        )
        steps.append(verify_step)
        if verify.mode != "at":
            raise LoraDeviceError(
                f"{self.name}: AT mode verification failed, response {verify.response!r}"
            )
        return steps

    def ensure_work_mode(
        self,
        probe_timeout: float = 0.5,
        exit_timeout: float = 2.0,
    ) -> list[DeviceCommandStep]:
        """Ensure the module is out of AT mode before payload transfer."""

        probe = self.detect_mode(timeout=probe_timeout)
        steps = [
            DeviceCommandStep(
                command=probe.command,
                expected="OK",
                response=probe.response,
                passed=probe.mode == "at",
            )
        ]
        if probe.mode == "work":
            return steps
        if probe.mode == "unknown":
            raise LoraDeviceError(f"{self.name}: unable to detect device mode: {probe.response!r}")

        try:
            exit_result = self.at.exit_at(timeout=exit_timeout)
        except TypeError:
            exit_result = self.at.exit_at()
        except AtClientError as exc:
            raise LoraDeviceError(f"{self.name}: failed to exit AT mode: {exc}") from exc

        exit_step = self._to_step(exit_result)
        steps.append(exit_step)
        if not exit_step.passed:
            raise LoraDeviceError(
                f"{self.name}: failed to exit AT mode, expected {exit_step.expected!r}, "
                f"response {exit_step.response!r}"
            )
        return steps

    def configure_transparent_mode(
        self,
        sleep: str = "2",
        mode: str = "0",
        level: str = "2",
        channel: str = "00",
        command_timeout: float = 2.0,
        reset_timeout: float = 5.0,
    ) -> list[DeviceCommandStep]:
        """Configure the module for MVP transparent transfer mode.

        The flow intentionally stops at the first failed command so callers can
        surface a precise failure reason and avoid running later invalid steps.
        """

        self.serial.clear_buffer()
        steps: list[DeviceCommandStep] = []
        steps.extend(self.ensure_at_mode(probe_timeout=0.5, enter_timeout=command_timeout))
        commands: list[tuple[str, str, float, bool]] = [
            (f"AT+SLEEP{sleep}", "OK", command_timeout, True),
            (f"AT+MODE{mode}", "OK", command_timeout, True),
            (f"AT+LEVEL{level}", "OK", command_timeout, True),
            (f"AT+CHANNEL{channel}", "OK", command_timeout, True),
            ("AT+RESET", "OK", reset_timeout, True),
        ]

        for command, expected, timeout, append_newline in commands:
            try:
                if command == "AT+RESET":
                    result = self.at.reset(timeout=timeout, expected=expected)
                else:
                    result = self.at.send_cmd(
                        command,
                        expected=expected,
                        timeout=timeout,
                        append_newline=append_newline,
                    )
            except AtClientError as exc:
                raise LoraDeviceError(f"{self.name}: failed to execute {command!r}: {exc}") from exc

            step = self._to_step(result)
            steps.append(step)
            if not step.passed:
                raise LoraDeviceError(
                    f"{self.name}: command {command!r} failed, expected {expected!r}, "
                    f"response {step.response!r}"
                )

        return steps

    def _to_step(self, result: AtCommandResult) -> DeviceCommandStep:
        return DeviceCommandStep(
            command=result.command,
            expected=result.expected,
            response=result.response,
            passed=result.passed,
        )

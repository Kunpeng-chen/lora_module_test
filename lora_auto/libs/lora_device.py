"""LoRa device abstraction for automation flows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from lora_auto.libs.at_client import AtClient, AtClientError, AtCommandResult
from lora_auto.libs.serial_client import SerialClient


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

        commands: list[tuple[str, str, float, bool]] = [
            ("+++", self.at.at_entry_expected, command_timeout, False),
            (f"AT+SLEEP{sleep}", "OK", command_timeout, True),
            (f"AT+MODE{mode}", "OK", command_timeout, True),
            (f"AT+LEVEL{level}", "OK", command_timeout, True),
            (f"AT+CHANNEL{channel}", "OK", command_timeout, True),
            ("AT+RESET", "OK", reset_timeout, True),
        ]

        steps: list[DeviceCommandStep] = []
        for command, expected, timeout, append_newline in commands:
            try:
                if command == "+++":
                    result = self.at.enter_at(timeout=timeout)
                elif command == "AT+RESET":
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

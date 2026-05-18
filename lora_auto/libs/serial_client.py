"""Serial communication helper for LoRa module automation."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Optional


class SerialClientError(RuntimeError):
    """Raised when serial communication fails."""


@dataclass(frozen=True)
class SerialResponse:
    """Result returned by a serial read operation."""

    data: str
    matched: bool


class SerialClient:
    """Small wrapper around a pyserial-compatible serial object.

    The class accepts an optional ``serial_instance`` so tests can inject a fake
    serial port without requiring physical LoRa hardware.
    """

    def __init__(
        self,
        port: str,
        baudrate: int = 9600,
        timeout: float = 2.0,
        serial_instance: Optional[Any] = None,
    ) -> None:
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self._serial = serial_instance
        self._owns_serial = serial_instance is None

    @property
    def is_open(self) -> bool:
        return bool(self._serial and getattr(self._serial, "is_open", False))

    def open(self) -> None:
        """Open the serial port."""

        if self.is_open:
            return

        if self._serial is None:
            try:
                import serial  # type: ignore[import-not-found]
            except ImportError as exc:
                raise SerialClientError(
                    "pyserial is required. Install it with: pip install pyserial"
                ) from exc

            try:
                self._serial = serial.Serial(
                    port=self.port,
                    baudrate=self.baudrate,
                    timeout=self.timeout,
                )
            except Exception as exc:  # pragma: no cover - depends on host serial
                raise SerialClientError(f"failed to open serial port {self.port}: {exc}") from exc
            return

        open_method = getattr(self._serial, "open", None)
        if callable(open_method):
            try:
                open_method()
            except Exception as exc:
                raise SerialClientError(f"failed to open serial port {self.port}: {exc}") from exc

    def close(self) -> None:
        """Close the serial port if it is open."""

        if not self._serial:
            return
        close_method = getattr(self._serial, "close", None)
        if callable(close_method):
            close_method()

    def clear_buffer(self) -> None:
        """Clear input and output buffers when supported by the backend."""

        self._require_open()
        for method_name in ("reset_input_buffer", "reset_output_buffer"):
            method = getattr(self._serial, method_name, None)
            if callable(method):
                method()

    def write_text(self, text: str, append_newline: bool = True) -> None:
        """Write text to the serial port using UTF-8 encoding."""

        self._require_open()
        payload = text if not append_newline else f"{text}\r\n"
        self._write_bytes(payload.encode("utf-8"))

    def write_hex(self, hex_str: str) -> None:
        """Write a hexadecimal payload to the serial port."""

        self._require_open()
        normalized = hex_str.replace(" ", "")
        try:
            payload = bytes.fromhex(normalized)
        except ValueError as exc:
            raise SerialClientError(f"invalid hex payload: {hex_str}") from exc
        self._write_bytes(payload)

    def read_all(self, timeout: Optional[float] = None) -> str:
        """Read all available data until timeout expires."""

        self._require_open()
        end_at = time.monotonic() + (self.timeout if timeout is None else timeout)
        chunks: list[bytes] = []

        while time.monotonic() < end_at:
            waiting = int(getattr(self._serial, "in_waiting", 0) or 0)
            read_size = waiting if waiting > 0 else 1
            data = self._serial.read(read_size)
            if data:
                chunks.append(data)
            else:
                time.sleep(0.01)

        return b"".join(chunks).decode("utf-8", errors="replace")

    def read_until(self, expected: str, timeout: Optional[float] = None) -> SerialResponse:
        """Read until ``expected`` appears or timeout expires."""

        self._require_open()
        end_at = time.monotonic() + (self.timeout if timeout is None else timeout)
        chunks: list[bytes] = []

        while time.monotonic() < end_at:
            waiting = int(getattr(self._serial, "in_waiting", 0) or 0)
            read_size = waiting if waiting > 0 else 1
            data = self._serial.read(read_size)
            if data:
                chunks.append(data)
                decoded = b"".join(chunks).decode("utf-8", errors="replace")
                if expected in decoded:
                    return SerialResponse(data=decoded, matched=True)
            else:
                time.sleep(0.01)

        decoded = b"".join(chunks).decode("utf-8", errors="replace")
        return SerialResponse(data=decoded, matched=False)

    def _write_bytes(self, payload: bytes) -> None:
        try:
            self._serial.write(payload)
        except Exception as exc:
            raise SerialClientError(f"failed to write to serial port {self.port}: {exc}") from exc

    def _require_open(self) -> None:
        if not self._serial:
            raise SerialClientError("serial port is not initialized")
        if not getattr(self._serial, "is_open", False):
            raise SerialClientError(f"serial port {self.port} is not open")

from __future__ import annotations

from lora_auto.libs.serial_client import SerialClient, SerialClientError


class FakeSerial:
    def __init__(self, response: bytes = b"") -> None:
        self.is_open = False
        self.response = bytearray(response)
        self.written = bytearray()
        self.input_reset = False
        self.output_reset = False

    @property
    def in_waiting(self) -> int:
        return len(self.response)

    def open(self) -> None:
        self.is_open = True

    def close(self) -> None:
        self.is_open = False

    def write(self, payload: bytes) -> int:
        self.written.extend(payload)
        return len(payload)

    def read(self, size: int = 1) -> bytes:
        if not self.response:
            return b""
        size = min(size, len(self.response))
        data = self.response[:size]
        del self.response[:size]
        return bytes(data)

    def reset_input_buffer(self) -> None:
        self.input_reset = True

    def reset_output_buffer(self) -> None:
        self.output_reset = True


def test_write_text_appends_crlf_and_reads_expected_response() -> None:
    fake = FakeSerial(b"OK\r\n")
    client = SerialClient("FAKE", serial_instance=fake, timeout=0.1)

    client.open()
    client.write_text("AT")
    response = client.read_until("OK", timeout=0.1)

    assert fake.written == b"AT\r\n"
    assert response.matched is True
    assert "OK" in response.data


def test_read_until_returns_unmatched_when_expected_text_is_missing() -> None:
    fake = FakeSerial(b"ERROR\r\n")
    client = SerialClient("FAKE", serial_instance=fake, timeout=0.1)

    client.open()
    response = client.read_until("OK", timeout=0.1)

    assert response.matched is False
    assert "ERROR" in response.data


def test_clear_buffer_calls_supported_backend_methods() -> None:
    fake = FakeSerial()
    client = SerialClient("FAKE", serial_instance=fake, timeout=0.1)

    client.open()
    client.clear_buffer()

    assert fake.input_reset is True
    assert fake.output_reset is True


def test_write_requires_open_port() -> None:
    fake = FakeSerial()
    client = SerialClient("FAKE", serial_instance=fake, timeout=0.1)

    try:
        client.write_text("AT")
    except SerialClientError as exc:
        assert "not open" in str(exc)
    else:
        raise AssertionError("expected SerialClientError")


def test_write_hex_validates_payload() -> None:
    fake = FakeSerial()
    client = SerialClient("FAKE", serial_instance=fake, timeout=0.1)
    client.open()

    try:
        client.write_hex("not-hex")
    except SerialClientError as exc:
        assert "invalid hex payload" in str(exc)
    else:
        raise AssertionError("expected SerialClientError")

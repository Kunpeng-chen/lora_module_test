"""Check whether a LoRa module answers a basic AT command."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running this file directly from a source checkout.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from lora_auto.libs.serial_client import SerialClient, SerialClientError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check LoRa module serial AT connectivity.")
    parser.add_argument("--port", required=True, help="Serial port, for example COM3 or /dev/ttyUSB0.")
    parser.add_argument("--baudrate", type=int, default=9600, help="Serial baudrate. Default: 9600.")
    parser.add_argument("--timeout", type=float, default=2.0, help="Read timeout in seconds. Default: 2.0.")
    parser.add_argument("--command", default="AT", help="Command to send. Default: AT.")
    parser.add_argument("--expected", default="OK", help="Expected response text. Default: OK.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    client = SerialClient(port=args.port, baudrate=args.baudrate, timeout=args.timeout)

    print(f"PORT: {args.port}")
    print(f"TX: {args.command}")

    try:
        client.open()
        client.clear_buffer()
        client.write_text(args.command)
        response = client.read_until(args.expected, timeout=args.timeout)
    except SerialClientError as exc:
        print(f"FAIL: {exc}")
        return 1
    finally:
        client.close()

    print(f"RX: {response.data.strip()}")
    if response.matched:
        print("PASS")
        return 0

    print(f"FAIL: expected response containing {args.expected!r} within {args.timeout}s")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

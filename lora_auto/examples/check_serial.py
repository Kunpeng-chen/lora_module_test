"""Check whether a LoRa module answers a basic AT command."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running this file directly from a source checkout.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from lora_auto.libs.at_client import AtClient, AtClientError
from lora_auto.libs.serial_client import SerialClient, SerialClientError


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check LoRa module serial AT connectivity.")
    parser.add_argument("--port", required=True, help="Serial port, for example COM3 or /dev/ttyUSB0.")
    parser.add_argument("--baudrate", type=int, default=9600, help="Serial baudrate. Default: 9600.")
    parser.add_argument("--timeout", type=float, default=2.0, help="Read timeout in seconds. Default: 2.0.")
    parser.add_argument("--command", default="AT", help="Command to send after entering AT mode. Default: AT.")
    parser.add_argument("--expected", default="OK", help="Expected response text. Default: OK.")
    parser.add_argument(
        "--skip-enter-at",
        action="store_true",
        help="Skip the initial +++ AT-mode entry step. Use only when the module is already in AT mode.",
    )
    parser.add_argument(
        "--skip-exit-at",
        action="store_true",
        help="Skip the final +++ AT-mode exit step after a successful check.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    client = SerialClient(port=args.port, baudrate=args.baudrate, timeout=args.timeout)
    at = AtClient(client)

    print(f"PORT: {args.port}")

    try:
        client.open()
        client.clear_buffer()

        if not args.skip_enter_at:
            print("TX: +++")
            entry = at.enter_at(timeout=args.timeout)
            print(f"RX: {entry.response.strip()}")
            if not entry.passed:
                print(f"FAIL: expected AT entry response containing {entry.expected!r} within {args.timeout}s")
                return 1

        print(f"TX: {args.command}")
        response = at.send_cmd(args.command, expected=args.expected, timeout=args.timeout)
        print(f"RX: {response.response.strip()}")
        if not response.passed:
            print(f"FAIL: expected response containing {args.expected!r} within {args.timeout}s")
            return 1

        print("PASS")

        if not args.skip_exit_at:
            print("TX: +++")
            exit_result = at.send_cmd("+++", expected="Exit AT", timeout=args.timeout)
            print(f"RX: {exit_result.response.strip()}")
            if not exit_result.passed:
                print(f"FAIL: expected AT exit response containing {exit_result.expected!r} within {args.timeout}s")
                return 1

        return 0
    except (SerialClientError, AtClientError) as exc:
        print(f"FAIL: {exc}")
        return 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())

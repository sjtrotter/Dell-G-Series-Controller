#!/usr/bin/python3
"""Explicit hardware test for one persistent AW-ELC power-state animation."""

import argparse

from src.awelc_protocol import AwElcProtocol
from src.hidraw_transport import HidrawReportTransport
from src.usb_transport import DeviceAccessError, DeviceNotFoundError


POWER_STATES = {
    "ac-sleep": 0x5B,
    "ac-charged": 0x5C,
    "ac-charging": 0x5D,
    "dc-sleep": 0x5E,
    "dc-on": 0x5F,
    "dc-low": 0x60,
}


def byte(value: str) -> int:
    number = int(value, 0)
    if not 0 <= number <= 255:
        raise argparse.ArgumentTypeError("color channels must be between 0 and 255")
    return number


def main() -> int:
    parser = argparse.ArgumentParser(
        description="replace one persistent AW-ELC power-state animation"
    )
    parser.add_argument("state", choices=POWER_STATES)
    parser.add_argument("red", type=byte)
    parser.add_argument("green", type=byte)
    parser.add_argument("blue", type=byte)
    parser.add_argument(
        "--write",
        action="store_true",
        help="confirm the persistent controller-flash write",
    )
    args = parser.parse_args()
    animation_id = POWER_STATES[args.state]

    if not args.write:
        parser.error(
            f"this replaces {args.state} animation 0x{animation_id:04x}; "
            "pass --write to confirm"
        )

    try:
        protocol = AwElcProtocol(HidrawReportTransport.discover())
        _, zones = protocol.get_platform()
        protocol.save_static_animation(
            animation_id,
            (args.red, args.green, args.blue),
            tuple(range(zones)),
        )
        protocol.set_dimness(0, tuple(range(zones)))
    except (DeviceAccessError, DeviceNotFoundError) as error:
        parser.error(str(error))

    print(
        f"saved RGB({args.red}, {args.green}, {args.blue}) to "
        f"{args.state} animation 0x{animation_id:04x}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

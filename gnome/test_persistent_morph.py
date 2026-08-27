#!/usr/bin/python3
"""Explicit one-slot hardware test for AW-ELC morph timing fields."""

import argparse

from src.awelc_protocol import AC_CHARGED, AwElcProtocol
from src.hidraw_transport import HidrawReportTransport
from src.usb_transport import DeviceAccessError, DeviceNotFoundError


def bounded_integer(name: str, minimum: int, maximum: int):
    def parse(value: str) -> int:
        number = int(value, 0)
        if not minimum <= number <= maximum:
            raise argparse.ArgumentTypeError(
                f"{name} must be between {minimum} and {maximum}"
            )
        return number

    return parse


def main() -> int:
    parser = argparse.ArgumentParser(
        description="replace AC-charged animation 0x005c with a morph timing test"
    )
    parser.add_argument("duration", type=bounded_integer("duration", 4, 4095))
    parser.add_argument(
        "--tempo",
        type=bounded_integer("tempo", 1, 255),
        default=1,
        help="firmware tempo field (default: 1)",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="confirm replacement of persistent AC-charged animation 0x005c",
    )
    args = parser.parse_args()
    if not args.write:
        parser.error("pass --write to confirm the persistent controller-flash write")

    try:
        protocol = AwElcProtocol(HidrawReportTransport.discover())
        _, zone_count = protocol.get_platform()
        zones = tuple(range(zone_count))
        protocol.save_morph_animation(
            AC_CHARGED,
            (255, 0, 0),
            (0, 0, 255),
            zones,
            args.duration,
            args.tempo,
        )
        protocol.set_dimness(0, zones)
    except (DeviceAccessError, DeviceNotFoundError) as error:
        parser.error(str(error))

    print(
        f"saved red/blue morph, duration {args.duration}, tempo {args.tempo}, "
        "to AC-charged animation 0x005c"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

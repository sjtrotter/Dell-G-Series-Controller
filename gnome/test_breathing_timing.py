#!/usr/bin/python3
"""Probe AW-ELC breathing timing with independent color/black durations."""

import argparse

from src.awelc_protocol import AC_CHARGED, AnimationAction, AwElcProtocol
from src.hidraw_transport import HidrawReportTransport
from src.usb_transport import DeviceAccessError, DeviceNotFoundError


def duration(value: str) -> int:
    number = int(value, 0)
    if not 4 <= number <= 4095:
        raise argparse.ArgumentTypeError("duration must be between 4 and 4095")
    return number


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "replace AC-charged animation 0x005c with a red/black Morph timing test"
        )
    )
    parser.add_argument("color_duration", type=duration)
    parser.add_argument("black_duration", type=duration)
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
        protocol.save_animation(
            AC_CHARGED,
            (
                AnimationAction(2, args.color_duration, 1, (255, 0, 0)),
                AnimationAction(2, args.black_duration, 1, (0, 0, 0)),
            ),
            zones,
        )
        protocol.set_dimness(0, zones)
    except (DeviceAccessError, DeviceNotFoundError) as error:
        parser.error(str(error))

    print(
        "saved red/black Morph to AC-charged animation 0x005c: "
        f"red duration {args.color_duration}, black duration {args.black_duration}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

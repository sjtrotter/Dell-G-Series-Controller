#!/usr/bin/python3
"""Write a bounded multicolor Morph sequence to the AC-charged profile."""

import argparse
import colorsys

from src.awelc_protocol import AC_CHARGED, AwElcProtocol
from src.hidraw_transport import HidrawReportTransport


def palette(count: int) -> tuple[tuple[int, int, int], ...]:
    return tuple(
        tuple(round(channel * 255) for channel in colorsys.hsv_to_rgb(i / count, 1, 1))
        for i in range(count)
    )


def rgb(value: str) -> tuple[int, int, int]:
    value = value.removeprefix("#")
    if len(value) != 6:
        raise argparse.ArgumentTypeError("colors must use six hexadecimal digits")
    try:
        return tuple(int(value[offset : offset + 2], 16) for offset in (0, 2, 4))
    except ValueError as error:
        raise argparse.ArgumentTypeError("colors must use hexadecimal digits") from error


def main() -> int:
    parser = argparse.ArgumentParser(
        description="replace the AC-charged profile with a multicolor Morph test"
    )
    parser.add_argument("count", nargs="?", type=int, choices=range(3, 13), metavar="3..12")
    parser.add_argument("--colors", nargs="+", type=rgb, metavar="RRGGBB")
    parser.add_argument("--duration", type=int, default=600)
    parser.add_argument(
        "--write",
        action="store_true",
        help="confirm the persistent controller-flash write",
    )
    args = parser.parse_args()
    if not 4 <= args.duration <= 4095:
        parser.error("--duration must be between 4 and 4095")
    if not args.write:
        parser.error("pass --write to confirm the persistent controller-flash write")
    if (args.count is None) == (args.colors is None):
        parser.error("provide either a target count or --colors, but not both")
    if args.colors is not None and not 2 <= len(args.colors) <= 12:
        parser.error("--colors requires between 2 and 12 targets")

    colors = tuple(args.colors) if args.colors is not None else palette(args.count)
    protocol = AwElcProtocol(HidrawReportTransport.discover())
    platform, zone_count = protocol.get_platform()
    protocol.save_multicolor_morph_animation(
        AC_CHARGED,
        colors,
        tuple(range(zone_count)),
        args.duration,
    )
    formatted = ", ".join(f"#{r:02x}{g:02x}{b:02x}" for r, g, b in colors)
    print(
        f"saved {len(colors)}-color Morph to AC-charged on platform "
        f"0x{platform:04x}: {formatted}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

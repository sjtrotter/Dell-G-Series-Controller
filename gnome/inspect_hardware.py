#!/usr/bin/python3

from src.awelc_protocol import AwElcProtocol
from src.hidraw_transport import HidrawReportTransport
from src.usb_transport import DeviceAccessError, DeviceNotFoundError


def format_report(report: bytes) -> str:
    return " ".join(f"{value:02x}" for value in report)


def main() -> int:
    try:
        protocol = AwElcProtocol(HidrawReportTransport.discover())
        version = protocol.get_version()
        platform, zones = protocol.get_platform()
        count, maximum_id = protocol.get_animation_count()
        print(f"firmware: {'.'.join(map(str, version))}")
        print(f"platform: 0x{platform:04x}; zones: {zones}")
        print(f"stored animations: {count}; maximum ID: 0x{maximum_id:02x}")
        for index in range(count):
            animation_id, is_custom, raw = protocol.get_animation_by_index(index)
            kind = "custom" if is_custom else "predefined"
            print(
                f"animation[{index}]: ID 0x{animation_id:04x}; {kind}; "
                f"raw: {format_report(raw)}"
            )
    except (DeviceAccessError, DeviceNotFoundError) as error:
        print(f"error: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

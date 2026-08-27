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
        count, animation_id, summary_raw = protocol.get_animation_summary()
        print(f"firmware: {'.'.join(map(str, version))}")
        print(f"platform: 0x{platform:04x}; zones: {zones}")
        print(f"stored animations: {count}")
        print(f"summary raw: {format_report(summary_raw)}")
        if count:
            print(f"firmware-selected animation ID: 0x{animation_id:04x}")
            print("note: firmware 1.1.7 does not expose readable animation contents")
    except (DeviceAccessError, DeviceNotFoundError) as error:
        print(f"error: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

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
        count, animation_ids, directory_raw = protocol.get_animation_directory()
        print(f"firmware: {'.'.join(map(str, version))}")
        print(f"platform: 0x{platform:04x}; zones: {zones}")
        print(f"stored animations: {count}")
        print(f"directory raw: {format_report(directory_raw)}")
        print(
            "advertised IDs: "
            + (", ".join(f"0x{value:04x}" for value in animation_ids) or "none")
        )
        for requested_id in animation_ids:
            animation_id, is_custom, raw = protocol.get_animation_by_id(requested_id)
            kind = "custom" if is_custom else "predefined"
            print(
                f"animation[0x{requested_id:04x}]: returned ID "
                f"0x{animation_id:04x}; {kind}; "
                f"raw: {format_report(raw)}"
            )
    except (DeviceAccessError, DeviceNotFoundError) as error:
        print(f"error: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

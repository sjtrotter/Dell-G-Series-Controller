#!/usr/bin/python3

import time

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
        count, maximum_id, directory_raw = protocol.get_animation_directory()
        print(f"firmware: {'.'.join(map(str, version))}")
        print(f"platform: 0x{platform:04x}; zones: {zones}")
        print(f"stored animations: {count}")
        print(f"directory raw: {format_report(directory_raw)}")
        print(f"maximum candidate ID: 0x{maximum_id:04x}")
        found = 0
        for requested_id in range(min(maximum_id, 0xFF) + 1):
            animation_id, is_custom, raw = protocol.get_animation_by_id(requested_id)
            if animation_id == 0xFFFF:
                time.sleep(0.06)
                continue
            kind = "custom" if is_custom else "predefined"
            print(
                f"animation[0x{requested_id:04x}]: returned ID "
                f"0x{animation_id:04x}; {kind}; "
                f"raw: {format_report(raw)}"
            )
            found += 1
            if found >= count:
                break
            time.sleep(0.06)
        if found != count:
            print(f"warning: found {found} of {count} stored animations")
    except (DeviceAccessError, DeviceNotFoundError) as error:
        print(f"error: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

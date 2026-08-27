import fcntl
import os
from pathlib import Path
from typing import Callable

from .usb_transport import DeviceAccessError, DeviceNotFoundError


REPORT_SIZE = 33
SUPPORTED_HID_IDS = {
    "0003:0000187C:00000550",
    "0003:0000187C:00000551",
}

# Linux _IOC(_IOC_READ | _IOC_WRITE, 'H', command, report_size)
_IOC_READ_WRITE = 3
_IOC_DIRECTION_SHIFT = 30
_IOC_SIZE_SHIFT = 16
_IOC_TYPE_SHIFT = 8
HIDIOCGINPUT = (
    (_IOC_READ_WRITE << _IOC_DIRECTION_SHIFT)
    | (REPORT_SIZE << _IOC_SIZE_SHIFT)
    | (ord("H") << _IOC_TYPE_SHIFT)
    | 0x0A
)
HIDIOCSOUTPUT = (
    (_IOC_READ_WRITE << _IOC_DIRECTION_SHIFT)
    | (REPORT_SIZE << _IOC_SIZE_SHIFT)
    | (ord("H") << _IOC_TYPE_SHIFT)
    | 0x0B
)


class HidrawReportTransport:
    """Use Linux hidraw while leaving hid-generic attached to the controller."""

    def __init__(
        self,
        path: Path,
        opener: Callable = open,
        ioctl: Callable = fcntl.ioctl,
    ):
        self._path = path
        self._opener = opener
        self._ioctl = ioctl

    @classmethod
    def discover(
        cls, sys_class: Path = Path("/sys/class/hidraw")
    ) -> "HidrawReportTransport":
        for entry in sorted(sys_class.glob("hidraw*")):
            try:
                properties = dict(
                    line.split("=", 1)
                    for line in (entry / "device/uevent").read_text().splitlines()
                    if "=" in line
                )
            except OSError:
                continue
            if properties.get("HID_ID") in SUPPORTED_HID_IDS:
                return cls(Path("/dev") / entry.name)
        raise DeviceNotFoundError("No AW-ELC hidraw device found (187c:0550/0551)")

    def exchange(self, report: bytes) -> bytes:
        if len(report) != REPORT_SIZE:
            raise ValueError(f"AW-ELC reports must be {REPORT_SIZE} bytes")
        try:
            with self._opener(self._path, "r+b", buffering=0) as device:
                output = bytearray(report)
                self._ioctl(device, HIDIOCSOUTPUT, output, True)
                reply = bytearray(REPORT_SIZE)
                reply[0] = report[0]
                self._ioctl(device, HIDIOCGINPUT, reply, True)
                return bytes(reply)
        except OSError as error:
            if error.errno in (13,):
                detail = (
                    "access denied; grant this user read/write access to the "
                    "supported hidraw node (the included udev rule is optional)"
                )
            else:
                detail = os.strerror(error.errno) if error.errno else str(error)
            raise DeviceAccessError(
                f"AW-ELC hidraw exchange failed for {self._path}: {detail}"
            ) from error

from typing import Any


VENDOR_ID = 0x187C
PRODUCT_IDS = (0x0550, 0x0551)
HID_SET_REPORT = 0x09
HID_GET_REPORT = 0x01
HID_OUTPUT_REPORT = 0x0200
HID_INPUT_REPORT = 0x0100
REPORT_SIZE = 33


class DeviceNotFoundError(RuntimeError):
    pass


class DeviceAccessError(RuntimeError):
    pass


class UsbReportTransport:
    """Exchange AW-ELC HID reports without resetting or detaching the device."""

    def __init__(self, device: Any):
        self._device = device

    @classmethod
    def discover(cls) -> "UsbReportTransport":
        try:
            import usb.core
        except ImportError as error:
            raise DeviceAccessError(
                "PyUSB is required for AW-ELC hardware access"
            ) from error

        for product_id in PRODUCT_IDS:
            device = usb.core.find(idVendor=VENDOR_ID, idProduct=product_id)
            if device is not None:
                return cls(device)
        supported = ", ".join(f"187c:{product_id:04x}" for product_id in PRODUCT_IDS)
        raise DeviceNotFoundError(f"No AW-ELC controller found ({supported})")

    def exchange(self, report: bytes) -> bytes:
        if len(report) != REPORT_SIZE:
            raise ValueError(f"AW-ELC reports must be {REPORT_SIZE} bytes")
        try:
            written = self._device.ctrl_transfer(
                0x21,
                HID_SET_REPORT,
                HID_OUTPUT_REPORT,
                0,
                report,
            )
            if written != REPORT_SIZE:
                raise DeviceAccessError(
                    f"AW-ELC accepted {written} of {REPORT_SIZE} output bytes"
                )
            reply = self._device.ctrl_transfer(
                0xA1,
                HID_GET_REPORT,
                HID_INPUT_REPORT,
                0,
                REPORT_SIZE,
            )
        except DeviceAccessError:
            raise
        except Exception as error:
            raise DeviceAccessError(f"AW-ELC USB exchange failed: {error}") from error
        return bytes(reply)

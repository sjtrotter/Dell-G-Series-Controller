import unittest
from unittest.mock import patch

import usb.core

from src.usb_transport import (
    DeviceAccessError,
    DeviceNotFoundError,
    UsbReportTransport,
)


class FakeDevice:
    def __init__(self, written=33, reply=None):
        self.written = written
        self.reply = reply or bytes(range(33))
        self.calls = []

    def ctrl_transfer(self, *args):
        self.calls.append(args)
        return self.written if len(self.calls) == 1 else self.reply


class UsbReportTransportTest(unittest.TestCase):
    def test_exchanges_hid_control_reports(self):
        device = FakeDevice()
        report = bytes(33)

        reply = UsbReportTransport(device).exchange(report)

        self.assertEqual(reply, bytes(range(33)))
        self.assertEqual(device.calls[0], (0x21, 9, 0x0200, 0, report))
        self.assertEqual(device.calls[1], (0xA1, 1, 0x0100, 0, 33))

    def test_rejects_partial_output_report(self):
        with self.assertRaisesRegex(DeviceAccessError, "accepted 12 of 33"):
            UsbReportTransport(FakeDevice(written=12)).exchange(bytes(33))

    def test_rejects_wrong_report_size_before_usb_access(self):
        device = FakeDevice()
        with self.assertRaisesRegex(ValueError, "must be 33 bytes"):
            UsbReportTransport(device).exchange(bytes(32))
        self.assertEqual(device.calls, [])

    @patch("usb.core.find", return_value=None)
    def test_reports_missing_supported_device(self, find):
        with self.assertRaisesRegex(DeviceNotFoundError, "187c:0550, 187c:0551"):
            UsbReportTransport.discover()
        self.assertEqual(find.call_count, 2)

    @patch("usb.core.find", side_effect=usb.core.NoBackendError("missing"))
    def test_reports_missing_libusb_backend(self, _find):
        with self.assertRaisesRegex(DeviceAccessError, "load a libusb backend"):
            UsbReportTransport.discover()


if __name__ == "__main__":
    unittest.main()

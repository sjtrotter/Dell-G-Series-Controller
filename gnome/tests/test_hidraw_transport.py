import tempfile
import unittest
from pathlib import Path

from src.hidraw_transport import (
    HIDIOCGINPUT,
    HIDIOCSOUTPUT,
    HidrawReportTransport,
)
from src.usb_transport import DeviceNotFoundError


class FakeFile:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None


class HidrawReportTransportTest(unittest.TestCase):
    def test_discovers_supported_hid_id(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            device = root / "hidraw4/device"
            device.mkdir(parents=True)
            (device / "uevent").write_text(
                "DRIVER=hid-generic\nHID_ID=0003:0000187C:00000550\n"
            )
            transport = HidrawReportTransport.discover(root)
            self.assertEqual(transport._path, Path("/dev/hidraw4"))

    def test_rejects_tree_without_supported_device(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(DeviceNotFoundError):
                HidrawReportTransport.discover(Path(directory))

    def test_exchanges_output_and_input_reports(self):
        calls = []

        def ioctl(_device, request, buffer, mutate):
            calls.append((request, bytes(buffer), mutate))
            if request == HIDIOCGINPUT:
                buffer[:] = bytes((3, 0x20, 0, 1, 1, 7)).ljust(33, b"\0")

        transport = HidrawReportTransport(
            Path("/dev/hidraw-test"),
            opener=lambda *_args, **_kwargs: FakeFile(),
            ioctl=ioctl,
        )
        report = bytes((3, 0x20)).ljust(33, b"\0")
        reply = transport.exchange(report)

        self.assertEqual(calls[0], (HIDIOCSOUTPUT, report, True))
        self.assertEqual(calls[1][0], HIDIOCGINPUT)
        self.assertEqual(reply[:6], bytes((3, 0x20, 0, 1, 1, 7)))


if __name__ == "__main__":
    unittest.main()

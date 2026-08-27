import unittest

from src.awelc_protocol import AwElcProtocol, ProtocolError, build_report


class FakeTransport:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.reports = []

    def exchange(self, report):
        self.reports.append(report)
        return next(self.replies)


class BuildReportTest(unittest.TestCase):
    def test_builds_padded_33_byte_report(self):
        report = build_report(0x27, bytes((255, 0, 0, 0, 1, 0)))
        self.assertEqual(len(report), 33)
        self.assertEqual(report[:8], bytes((3, 0x27, 255, 0, 0, 0, 1, 0)))


class ProtocolTest(unittest.TestCase):
    def test_parses_observed_controller_identity(self):
        version = bytes((3, 0x20, 0, 1, 1, 7)).ljust(33, b"\0")
        platform = bytes((3, 0x20, 2, 0x0e, 0x09, 1)).ljust(33, b"\0")
        protocol = AwElcProtocol(FakeTransport((version, platform)))
        self.assertEqual(protocol.get_version(), (1, 1, 7))
        self.assertEqual(protocol.get_platform(), (0x0e09, 1))

    def test_builds_single_zone_color_command(self):
        reply = bytes((3, 0x27, 255, 0, 0, 0, 1, 0)).ljust(33, b"\0")
        transport = FakeTransport((reply,))
        AwElcProtocol(transport).set_color((255, 0, 0), (0,))
        self.assertEqual(
            transport.reports[0][:8], bytes((3, 0x27, 255, 0, 0, 0, 1, 0))
        )

    def test_rejects_mismatched_reply(self):
        reply = bytes((3, 0x26)).ljust(33, b"\0")
        with self.assertRaisesRegex(ProtocolError, "does not match"):
            AwElcProtocol(FakeTransport((reply,))).set_color((255, 0, 0), (0,))


if __name__ == "__main__":
    unittest.main()

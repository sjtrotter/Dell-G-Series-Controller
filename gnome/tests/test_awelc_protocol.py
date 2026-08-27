import unittest

from src.awelc_protocol import (
    AnimationAction,
    AwElcProtocol,
    ProtocolError,
    build_report,
)


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

    def test_reads_animation_summary_using_observed_layout(self):
        count_reply = bytes((3, 0x20, 3, 0, 1, 0, 0x81)).ljust(33, b"\0")
        transport = FakeTransport((count_reply,))
        protocol = AwElcProtocol(transport)

        count, animation_id, summary_raw = protocol.get_animation_summary()
        self.assertEqual((count, animation_id), (1, 0x81))
        self.assertEqual(summary_raw, count_reply)
        self.assertEqual(transport.reports[0][:3], bytes((3, 0x20, 3)))

    def test_rejects_mismatched_reply(self):
        reply = bytes((3, 0x26)).ljust(33, b"\0")
        with self.assertRaisesRegex(ProtocolError, "does not match"):
            AwElcProtocol(FakeTransport((reply,))).set_color((255, 0, 0), (0,))

    def test_builds_persistent_static_animation_transaction(self):
        commands = (0x22, 0x22, 0x23, 0x24, 0x22, 0x22)
        replies = tuple(bytes((3, command)).ljust(33, b"\0") for command in commands)
        transport = FakeTransport(replies)

        AwElcProtocol(transport).save_static_animation(0x5D, (255, 0, 0), (0,))

        prefixes = [
            bytes((3, 0x22, 0, 4, 0, 0x5D)),
            bytes((3, 0x22, 0, 1, 0, 0x5D)),
            bytes((3, 0x23, 1, 0, 1, 0)),
            bytes((3, 0x24, 0, 0xFF, 0xFF, 0, 1, 255, 0, 0)),
            bytes((3, 0x22, 0, 2, 0, 0x5D)),
            bytes((3, 0x22, 0, 6, 0, 0x5D)),
        ]
        self.assertEqual(
            [report[: len(prefix)] for report, prefix in zip(transport.reports, prefixes)],
            prefixes,
        )

    def test_validates_animation_action_fields(self):
        with self.assertRaisesRegex(ValueError, "duration"):
            AnimationAction(0, 0x10000, 1, (255, 0, 0))

    def test_builds_two_color_morph_actions(self):
        commands = (0x22, 0x22, 0x23, 0x24, 0x22, 0x22)
        replies = tuple(bytes((3, command)).ljust(33, b"\0") for command in commands)
        transport = FakeTransport(replies)

        AwElcProtocol(transport).save_morph_animation(
            0x5C, (255, 0, 0), (0, 0, 255), (0,), duration=500
        )

        action_report = transport.reports[3]
        self.assertEqual(
            action_report[:18],
            bytes(
                (
                    3,
                    0x24,
                    2,
                    0x01,
                    0xF4,
                    0,
                    1,
                    255,
                    0,
                    0,
                    2,
                    0x01,
                    0xF4,
                    0,
                    1,
                    0,
                    0,
                    255,
                )
            ),
        )


if __name__ == "__main__":
    unittest.main()

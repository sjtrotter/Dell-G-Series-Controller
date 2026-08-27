#!/usr/bin/python3

import unittest

import awelc


class FakeElc:
    def __init__(self, zone_count):
        self.zone_count = zone_count

    def get_platform(self):
        return (bytes((0x0e, 0x09)), self.zone_count)


class GetZonesTest(unittest.TestCase):
    def test_single_zone_controller(self):
        self.assertEqual(awelc.get_zones(FakeElc(1)), [0])

    def test_four_zone_controller(self):
        self.assertEqual(awelc.get_zones(FakeElc(4)), [0, 1, 2, 3])

    def test_zero_zones_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "invalid zone count"):
            awelc.get_zones(FakeElc(0))

    def test_oversized_zone_count_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "invalid zone count"):
            awelc.get_zones(FakeElc(29))


if __name__ == "__main__":
    unittest.main()

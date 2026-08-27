import unittest

from src.keyboard_layout import KEY_COUNT, layout_for_device


class KeyboardLayoutTest(unittest.TestCase):
    def test_single_zone_is_validated_as_all_keys(self):
        layout = layout_for_device(0x0E09, 1)
        self.assertTrue(layout.validated)
        self.assertEqual(layout.zones[0].firmware_id, 0)
        self.assertEqual(layout.zones[0].label, "All keys")
        self.assertEqual(len(layout.zones[0].key_indices), KEY_COUNT)

    def test_unknown_multizone_layout_is_non_authoritative(self):
        layout = layout_for_device(0x1234, 4)
        self.assertFalse(layout.validated)
        self.assertEqual([zone.firmware_id for zone in layout.zones], [0, 1, 2, 3])
        represented = tuple(
            key for zone in layout.zones for key in zone.key_indices
        )
        self.assertEqual(tuple(sorted(represented)), tuple(range(KEY_COUNT)))

    def test_rejects_invalid_zone_count(self):
        with self.assertRaisesRegex(ValueError, "at least one"):
            layout_for_device(None, 0)


if __name__ == "__main__":
    unittest.main()

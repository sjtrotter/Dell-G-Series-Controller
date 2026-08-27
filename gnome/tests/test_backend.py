import unittest

from src.backend import DemoBackend, LightingEffect, LightingSettings


class LightingSettingsTest(unittest.TestCase):
    def test_valid_static_settings(self):
        settings = LightingSettings(
            enabled=True,
            effect=LightingEffect.STATIC,
            primary_color=(255, 128, 0),
            brightness=75,
        )
        self.assertEqual(settings.primary_color, (255, 128, 0))

    def test_rejects_invalid_color(self):
        with self.assertRaisesRegex(ValueError, "primary_color"):
            LightingSettings(
                enabled=True,
                effect=LightingEffect.STATIC,
                primary_color=(256, 0, 0),
                brightness=100,
            )

    def test_morph_requires_secondary_color_and_duration(self):
        with self.assertRaisesRegex(ValueError, "secondary color"):
            LightingSettings(
                enabled=True,
                effect=LightingEffect.MORPH,
                primary_color=(255, 0, 0),
                brightness=100,
            )


class DemoBackendTest(unittest.TestCase):
    def test_applies_valid_settings(self):
        backend = DemoBackend()
        settings = LightingSettings(
            enabled=False,
            effect=LightingEffect.STATIC,
            primary_color=(0, 0, 255),
            brightness=40,
        )
        backend.apply_lighting(settings)
        self.assertEqual(backend.settings, settings)


if __name__ == "__main__":
    unittest.main()

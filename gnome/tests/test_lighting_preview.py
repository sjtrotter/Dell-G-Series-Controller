import unittest

from src.backend import LightingEffect
from src.lighting_preview import preview_color


class LightingPreviewTest(unittest.TestCase):
    def test_static_color_respects_brightness(self):
        color, alpha = preview_color(
            enabled=True,
            effect=LightingEffect.STATIC,
            colors=((200, 100, 0),),
            brightness=50,
            duration_ms=500,
            tempo=100,
            elapsed_seconds=0,
        )
        self.assertEqual(color, (100 / 255, 50 / 255, 0))
        self.assertEqual(alpha, 0.92)

    def test_morph_interpolates_between_colors(self):
        color, _alpha = preview_color(
            enabled=True,
            effect=LightingEffect.MORPH,
            colors=((255, 0, 0), (0, 0, 255)),
            brightness=100,
            duration_ms=1000,
            tempo=100,
            elapsed_seconds=0.5,
        )
        self.assertEqual(color, (0.5, 0, 0.5))

    def test_breathing_inserts_dark_transition(self):
        color, _alpha = preview_color(
            enabled=True,
            effect=LightingEffect.BREATHING,
            colors=((255, 0, 0),),
            brightness=100,
            duration_ms=1000,
            tempo=100,
            elapsed_seconds=1,
        )
        self.assertEqual(color, (0, 0, 0))

    def test_disabled_preview_is_dim_and_unlit(self):
        color, alpha = preview_color(
            enabled=False,
            effect=LightingEffect.STATIC,
            colors=((255, 0, 0),),
            brightness=100,
            duration_ms=500,
            tempo=100,
            elapsed_seconds=0,
        )
        self.assertEqual((color, alpha), ((0.08, 0.08, 0.08), 0.28))


if __name__ == "__main__":
    unittest.main()

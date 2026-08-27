import tempfile
import unittest
from pathlib import Path

from src.backend import LightingEffect, LightingSettings
from src.settings_store import LightingSettingsStore


class LightingSettingsStoreTest(unittest.TestCase):
    def test_round_trips_settings(self):
        settings = LightingSettings(
            enabled=True,
            effect=LightingEffect.STATIC,
            primary_color=(10, 20, 30),
            brightness=65,
        )
        with tempfile.TemporaryDirectory() as directory:
            store = LightingSettingsStore(Path(directory) / "settings.json")
            store.save(settings)
            self.assertEqual(store.load(), settings)

    def test_invalid_file_is_treated_as_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text("not json", encoding="utf-8")
            self.assertIsNone(LightingSettingsStore(path).load())

    def test_round_trips_morph_settings(self):
        settings = LightingSettings(
            enabled=True,
            effect=LightingEffect.MORPH,
            primary_color=(255, 0, 0),
            secondary_color=(0, 0, 255),
            duration=750,
            brightness=80,
        )
        with tempfile.TemporaryDirectory() as directory:
            store = LightingSettingsStore(Path(directory) / "settings.json")
            store.save(settings)
            self.assertEqual(store.load(), settings)

    def test_round_trips_pulse_settings(self):
        settings = LightingSettings(
            enabled=True,
            effect=LightingEffect.PULSE,
            primary_color=(0, 255, 0),
            duration=600,
            brightness=90,
        )
        with tempfile.TemporaryDirectory() as directory:
            store = LightingSettingsStore(Path(directory) / "settings.json")
            store.save(settings)
            self.assertEqual(store.load(), settings)


if __name__ == "__main__":
    unittest.main()

import tempfile
import unittest
from pathlib import Path

from src.backend import BrightnessMode, LightingEffect, LightingSettings, PowerState
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
            tempo=100,
            brightness=90,
        )
        with tempfile.TemporaryDirectory() as directory:
            store = LightingSettingsStore(Path(directory) / "settings.json")
            store.save(settings)
            self.assertEqual(store.load(), settings)

    def test_migrates_legacy_setting_to_awake_profiles(self):
        settings = LightingSettings(
            enabled=True,
            effect=LightingEffect.STATIC,
            primary_color=(10, 20, 30),
            brightness=65,
        )
        with tempfile.TemporaryDirectory() as directory:
            store = LightingSettingsStore(Path(directory) / "settings.json")
            store.save(settings)
            profiles = store.load_profiles()
            self.assertEqual(profiles[PowerState.AC_CHARGED], settings)
            self.assertEqual(profiles[PowerState.AC_CHARGING], settings)
            self.assertEqual(profiles[PowerState.BATTERY_ON], settings)
            self.assertFalse(profiles[PowerState.AC_SLEEP].enabled)
            self.assertEqual(
                profiles[PowerState.BATTERY_LOW].effect, LightingEffect.PULSE
            )

    def test_round_trips_independent_power_profiles(self):
        with tempfile.TemporaryDirectory() as directory:
            store = LightingSettingsStore(Path(directory) / "settings.json")
            profiles = store.load_profiles()
            profiles[PowerState.AC_CHARGING] = LightingSettings(
                True, LightingEffect.STATIC, (255, 128, 0), 75
            )
            store.save_profiles(profiles)
            loaded = store.load_profiles()
            self.assertEqual(
                loaded[PowerState.AC_CHARGING].primary_color, (255, 128, 0)
            )
            self.assertNotEqual(
                loaded[PowerState.AC_CHARGED], loaded[PowerState.AC_CHARGING]
            )

    def test_round_trips_brightness_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            store = LightingSettingsStore(Path(directory) / "settings.json")
            store.save_profiles(
                store.load_profiles(), BrightnessMode.EXACT_SERVICE
            )
            self.assertEqual(
                store.load_brightness_mode(), BrightnessMode.EXACT_SERVICE
            )


if __name__ == "__main__":
    unittest.main()

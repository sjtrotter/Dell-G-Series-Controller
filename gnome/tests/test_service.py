import tempfile
import unittest
from pathlib import Path

from service import BrightnessService, detect_power_state
from src.backend import BrightnessMode, LightingEffect, LightingSettings, PowerState
from src.settings_store import LightingSettingsStore


def power_supply(root: Path, name: str, **fields: str) -> None:
    path = root / name
    path.mkdir()
    for field, value in fields.items():
        (path / field).write_text(value, encoding="utf-8")


class DetectPowerStateTest(unittest.TestCase):
    def test_detects_ac_charged_and_charging(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            power_supply(root, "AC", type="Mains", online="1")
            power_supply(root, "BAT0", type="Battery", status="Full", capacity="100")
            self.assertEqual(detect_power_state(root), PowerState.AC_CHARGED)
            (root / "BAT0" / "status").write_text("Charging", encoding="utf-8")
            self.assertEqual(detect_power_state(root), PowerState.AC_CHARGING)

    def test_detects_battery_on_and_low(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            power_supply(root, "AC", type="Mains", online="0")
            power_supply(
                root, "BAT0", type="Battery", status="Discharging", capacity="50"
            )
            self.assertEqual(detect_power_state(root), PowerState.BATTERY_ON)
            (root / "BAT0" / "capacity").write_text("10", encoding="utf-8")
            self.assertEqual(detect_power_state(root), PowerState.BATTERY_LOW)


class FakeProtocol:
    def __init__(self):
        self.dimness_calls = []

    def get_platform(self):
        return 0x0E09, 1

    def set_dimness(self, dimness, zones):
        self.dimness_calls.append((dimness, zones))


class BrightnessServiceTest(unittest.TestCase):
    def test_applies_exact_brightness_once_per_unchanged_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            power_supply(root, "AC", type="Mains", online="1")
            power_supply(root, "BAT0", type="Battery", status="Full", capacity="100")
            store = LightingSettingsStore(root / "settings.json")
            profiles = store.load_profiles()
            profiles[PowerState.AC_CHARGED] = LightingSettings(
                enabled=True,
                effect=LightingEffect.STATIC,
                primary_color=(255, 255, 255),
                brightness=40,
            )
            store.save_profiles(profiles, BrightnessMode.EXACT_SERVICE)
            protocol = FakeProtocol()
            service = BrightnessService(store, root, protocol)

            self.assertEqual(service.update(), (PowerState.AC_CHARGED, 40))
            self.assertIsNone(service.update())
            self.assertEqual(protocol.dimness_calls, [(60, (0,))])

    def test_rediscovers_the_protocol_after_disconnect(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            power_supply(root, "AC", type="Mains", online="1")
            power_supply(root, "BAT0", type="Battery", status="Full", capacity="100")
            store = LightingSettingsStore(root / "settings.json")
            store.save_profiles(store.load_profiles(), BrightnessMode.EXACT_SERVICE)
            protocols = [FakeProtocol(), FakeProtocol()]
            service = BrightnessService(
                store,
                root,
                protocol_factory=lambda: protocols.pop(0),
            )

            self.assertEqual(service.update(), (PowerState.AC_CHARGED, 100))
            first = service.protocol
            service.disconnect()
            self.assertEqual(service.update(), (PowerState.AC_CHARGED, 100))
            self.assertIsNot(service.protocol, first)


if __name__ == "__main__":
    unittest.main()

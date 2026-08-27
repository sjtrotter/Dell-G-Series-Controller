import tempfile
import unittest
from pathlib import Path

from service import detect_power_state
from src.backend import PowerState


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


if __name__ == "__main__":
    unittest.main()

import tempfile
import unittest
from pathlib import Path

from src.platform_hardware import inspect_hwmon, inspect_platform_profile


class PlatformHardwareTest(unittest.TestCase):
    def test_reads_fan_temperature_and_platform_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            hwmon = root / "class" / "hwmon" / "hwmon8"
            hwmon.mkdir(parents=True)
            self._write(hwmon, "name", "alienware_wmi")
            self._write(hwmon, "fan1_label", "CPU Fan")
            self._write(hwmon, "fan1_input", "2808")
            self._write(hwmon, "fan1_min", "0")
            self._write(hwmon, "fan1_max", "4800")
            self._write(hwmon, "fan1_boost", "0")
            self._write(hwmon, "temp1_label", "CPU")
            self._write(hwmon, "temp1_input", "80000")
            acpi = root / "firmware" / "acpi"
            acpi.mkdir(parents=True)
            self._write(acpi, "platform_profile", "balanced")
            self._write(
                acpi,
                "platform_profile_choices",
                "quiet balanced performance",
            )

            fans, temperatures = inspect_hwmon(root)
            profile = inspect_platform_profile(root)

            self.assertEqual(fans[0].label, "CPU Fan")
            self.assertEqual(fans[0].rpm, 2808)
            self.assertEqual(fans[0].maximum_rpm, 4800)
            self.assertEqual(temperatures[0].millidegrees_celsius, 80000)
            self.assertEqual(profile.active, "balanced")
            self.assertEqual(profile.choices, ("quiet", "balanced", "performance"))

    @staticmethod
    def _write(directory, name, value):
        (directory / name).write_text(value + "\n", encoding="utf-8")


if __name__ == "__main__":
    unittest.main()

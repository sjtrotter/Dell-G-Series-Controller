import unittest

from src.backend import (
    AwElcBackend,
    BrightnessMode,
    DemoBackend,
    LightingEffect,
    LightingSettings,
    PowerState,
)


class FakeProtocol:
    def __init__(self):
        self.calls = []

    def get_version(self):
        return (1, 1, 7)

    def get_platform(self):
        return (0x0E09, 1)

    def set_dimness(self, dimness, zones):
        self.calls.append(("dimness", dimness, zones))

    def set_color(self, color, zones):
        self.calls.append(("color", color, zones))

    def save_static_animation(self, animation_id, color, zones):
        self.calls.append(("save-static", animation_id, color, zones))

    def save_morph_animation(
        self, animation_id, primary_color, secondary_color, zones, duration
    ):
        self.calls.append(
            (
                "save-morph",
                animation_id,
                primary_color,
                secondary_color,
                zones,
                duration,
            )
        )

    def save_pulse_animation(self, animation_id, color, zones, duration, tempo):
        self.calls.append(
            ("save-pulse", animation_id, color, zones, duration, tempo)
        )


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


class AwElcBackendTest(unittest.TestCase):
    def test_reads_identity_and_exposes_verified_capabilities(self):
        backend = AwElcBackend(FakeProtocol())
        self.assertEqual(backend.info.firmware, "1.1.7")
        self.assertEqual(backend.info.platform, "0x0e09")
        self.assertEqual(backend.info.zones, 1)
        self.assertEqual(
            backend.capabilities.effects,
            {LightingEffect.STATIC, LightingEffect.PULSE, LightingEffect.MORPH},
        )
        self.assertTrue(backend.capabilities.persistent_power_states)

    def test_applies_static_color_and_inverse_dimness(self):
        protocol = FakeProtocol()
        backend = AwElcBackend(protocol)
        settings = LightingSettings(
            enabled=True,
            effect=LightingEffect.STATIC,
            primary_color=(20, 40, 60),
            brightness=75,
        )
        backend.apply_lighting(settings)
        self.assertEqual(
            protocol.calls,
            [
                ("save-static", 0x5C, (20, 40, 60), (0,)),
                ("save-static", 0x5D, (20, 40, 60), (0,)),
                ("save-static", 0x5F, (20, 40, 60), (0,)),
                ("dimness", 25, (0,)),
            ],
        )

    def test_disabling_saves_black_for_awake_power_states(self):
        protocol = FakeProtocol()
        backend = AwElcBackend(protocol)
        backend.apply_lighting(
            LightingSettings(
                enabled=False,
                effect=LightingEffect.STATIC,
                primary_color=(20, 40, 60),
                brightness=75,
            )
        )
        self.assertEqual(
            protocol.calls,
            [
                ("save-static", 0x5C, (0, 0, 0), (0,)),
                ("save-static", 0x5D, (0, 0, 0), (0,)),
                ("save-static", 0x5F, (0, 0, 0), (0,)),
                ("dimness", 25, (0,)),
            ],
        )

    def test_applies_two_color_morph_to_awake_power_states(self):
        protocol = FakeProtocol()
        backend = AwElcBackend(protocol)
        backend.apply_lighting(
            LightingSettings(
                enabled=True,
                effect=LightingEffect.MORPH,
                primary_color=(255, 0, 0),
                secondary_color=(0, 0, 255),
                duration=500,
                brightness=80,
            )
        )
        self.assertEqual(
            protocol.calls[:3],
            [
                ("save-morph", 0x5C, (255, 0, 0), (0, 0, 255), (0,), 500),
                ("save-morph", 0x5D, (255, 0, 0), (0, 0, 255), (0,), 500),
                ("save-morph", 0x5F, (255, 0, 0), (0, 0, 255), (0,), 500),
            ],
        )
        self.assertEqual(protocol.calls[3], ("dimness", 20, (0,)))

    def test_applies_verified_flashing_pulse_to_awake_power_states(self):
        protocol = FakeProtocol()
        backend = AwElcBackend(protocol)
        backend.apply_lighting(
            LightingSettings(
                enabled=True,
                effect=LightingEffect.PULSE,
                primary_color=(0, 255, 0),
                duration=600,
                tempo=100,
                brightness=90,
            )
        )
        self.assertEqual(
            protocol.calls[:3],
            [
                ("save-pulse", 0x5C, (0, 255, 0), (0,), 600, 100),
                ("save-pulse", 0x5D, (0, 255, 0), (0,), 600, 100),
                ("save-pulse", 0x5F, (0, 255, 0), (0,), 600, 100),
            ],
        )
        self.assertEqual(protocol.calls[3], ("dimness", 10, (0,)))

    def test_applies_only_selected_power_state(self):
        protocol = FakeProtocol()
        backend = AwElcBackend(protocol)
        settings = LightingSettings(
            enabled=True,
            effect=LightingEffect.STATIC,
            primary_color=(255, 0, 0),
            brightness=70,
        )
        backend.apply_power_state(PowerState.BATTERY_LOW, settings)
        self.assertEqual(
            protocol.calls,
            [
                ("save-static", 0x60, (255, 0, 0), (0,)),
                ("dimness", 30, (0,)),
            ],
        )

    def test_embeds_profile_brightness_by_scaling_colors(self):
        protocol = FakeProtocol()
        backend = AwElcBackend(protocol)
        settings = LightingSettings(
            enabled=True,
            effect=LightingEffect.MORPH,
            primary_color=(200, 100, 50),
            secondary_color=(20, 40, 60),
            duration=500,
            brightness=50,
        )
        backend.apply_power_state(
            PowerState.BATTERY_ON,
            settings,
            BrightnessMode.HARDWARE_SCALING,
        )
        self.assertEqual(
            protocol.calls,
            [
                ("save-morph", 0x5F, (100, 50, 25), (10, 20, 30), (0,), 500),
                ("dimness", 0, (0,)),
            ],
        )

    def test_exact_profile_brightness_uses_global_dimness(self):
        protocol = FakeProtocol()
        backend = AwElcBackend(protocol)
        settings = LightingSettings(
            enabled=True,
            effect=LightingEffect.STATIC,
            primary_color=(200, 100, 50),
            brightness=50,
        )
        backend.apply_power_state(
            PowerState.AC_CHARGED,
            settings,
            BrightnessMode.EXACT_SERVICE,
        )
        self.assertEqual(
            protocol.calls,
            [
                ("save-static", 0x5C, (200, 100, 50), (0,)),
                ("dimness", 50, (0,)),
            ],
        )


if __name__ == "__main__":
    unittest.main()

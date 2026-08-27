import json
import os
from pathlib import Path

from .backend import BrightnessMode, LightingEffect, LightingSettings, PowerState


class LightingSettingsStore:
    """Remember settings locally because AW-ELC 1.1.7 cannot read them back."""

    def __init__(self, path: Path | None = None):
        if path is None:
            config_home = Path(
                os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")
            )
            path = config_home / "dell-g-series-controller" / "settings.json"
        self.path = path

    def load(self) -> LightingSettings | None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if "profiles" in data:
                profile = data["profiles"].get(PowerState.AC_CHARGED.name)
                return self._decode(profile) if profile is not None else None
            return self._decode(data)
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None

    def save(self, settings: LightingSettings) -> None:
        self._write(self._encode(settings))

    def load_profiles(self) -> dict[PowerState, LightingSettings]:
        defaults = self._default_profiles()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if "profiles" not in data:
                legacy = self._decode(data)
                for state in (
                    PowerState.AC_CHARGED,
                    PowerState.AC_CHARGING,
                    PowerState.BATTERY_ON,
                ):
                    defaults[state] = legacy
                return defaults
            for state in PowerState:
                encoded = data["profiles"].get(state.name)
                if encoded is not None:
                    defaults[state] = self._decode(encoded)
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            pass
        return defaults

    def load_brightness_mode(self) -> BrightnessMode:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return BrightnessMode(
                data.get(
                    "brightness_mode", BrightnessMode.HARDWARE_SCALING.value
                )
            )
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            return BrightnessMode.HARDWARE_SCALING

    def load_separate_power_profiles(self) -> bool:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return bool(data.get("separate_power_profiles", True))
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            return True

    def save_profiles(
        self,
        profiles: dict[PowerState, LightingSettings],
        brightness_mode: BrightnessMode = BrightnessMode.HARDWARE_SCALING,
        separate_power_profiles: bool = True,
    ) -> None:
        data = self._read_document()
        saved_configurations = data.get("saved_configurations", {})
        self._write(
            {
                "version": 4,
                "brightness_mode": brightness_mode.value,
                "separate_power_profiles": separate_power_profiles,
                "profiles": {
                    state.name: self._encode(settings)
                    for state, settings in profiles.items()
                },
                "saved_configurations": saved_configurations,
            }
        )

    def list_saved_configurations(self) -> tuple[str, ...]:
        saved = self._read_document().get("saved_configurations", {})
        if not isinstance(saved, dict):
            return ()
        return tuple(sorted(saved, key=str.casefold))

    def save_configuration(
        self,
        name: str,
        profiles: dict[PowerState, LightingSettings],
        brightness_mode: BrightnessMode,
        separate_power_profiles: bool,
    ) -> None:
        name = name.strip()
        if not name or len(name) > 64:
            raise ValueError("configuration name must contain 1 to 64 characters")
        data = self._read_document()
        saved = data.setdefault("saved_configurations", {})
        saved[name] = {
            "brightness_mode": brightness_mode.value,
            "separate_power_profiles": separate_power_profiles,
            "profiles": {
                state.name: self._encode(settings)
                for state, settings in profiles.items()
            },
        }
        self._write(data)

    def load_configuration(
        self, name: str
    ) -> tuple[dict[PowerState, LightingSettings], BrightnessMode, bool]:
        saved = self._read_document()["saved_configurations"][name]
        defaults = self._default_profiles()
        for state in PowerState:
            encoded = saved["profiles"].get(state.name)
            if encoded is not None:
                defaults[state] = self._decode(encoded)
        return (
            defaults,
            BrightnessMode(saved["brightness_mode"]),
            bool(saved["separate_power_profiles"]),
        )

    def delete_configuration(self, name: str) -> None:
        data = self._read_document()
        saved = data.get("saved_configurations", {})
        if name in saved:
            del saved[name]
            self._write(data)

    def _read_document(self) -> dict:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            return {}

    def _write(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(data, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)

    @staticmethod
    def _encode(settings: LightingSettings) -> dict:
        return {
            "enabled": settings.enabled,
            "effect": settings.effect.value,
            "primary_color": list(settings.primary_color),
            "brightness": settings.brightness,
            "secondary_color": (
                list(settings.secondary_color)
                if settings.secondary_color is not None
                else None
            ),
            "colors": (
                [list(color) for color in settings.colors]
                if settings.additional_colors
                else None
            ),
            "duration": settings.duration,
            "tempo": settings.tempo,
        }

    @staticmethod
    def _decode(data: dict) -> LightingSettings:
        colors = tuple(tuple(color) for color in (data.get("colors") or ()))
        primary_color = colors[0] if colors else tuple(data["primary_color"])
        if len(colors) > 1:
            secondary_color = None
            additional_colors = colors[1:]
        else:
            secondary_color = (
                tuple(data["secondary_color"])
                if data.get("secondary_color") is not None
                else None
            )
            additional_colors = ()
        return LightingSettings(
            enabled=bool(data["enabled"]),
            effect=LightingEffect(data["effect"]),
            primary_color=primary_color,
            brightness=int(data["brightness"]),
            secondary_color=secondary_color,
            duration=(int(data["duration"]) if data.get("duration") is not None else None),
            tempo=(int(data["tempo"]) if data.get("tempo") is not None else None),
            additional_colors=additional_colors,
        )

    @staticmethod
    def _default_profiles() -> dict[PowerState, LightingSettings]:
        awake = LightingSettings(True, LightingEffect.STATIC, (255, 255, 255), 100)
        asleep = LightingSettings(False, LightingEffect.STATIC, (0, 0, 0), 100)
        low = LightingSettings(
            True,
            LightingEffect.PULSE,
            (255, 0, 0),
            100,
            duration=255,
            tempo=100,
        )
        return {
            PowerState.AC_SLEEP: asleep,
            PowerState.AC_CHARGED: awake,
            PowerState.AC_CHARGING: awake,
            PowerState.BATTERY_SLEEP: asleep,
            PowerState.BATTERY_ON: awake,
            PowerState.BATTERY_LOW: low,
        }

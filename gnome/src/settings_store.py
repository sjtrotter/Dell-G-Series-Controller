import json
import os
from pathlib import Path

from .backend import LightingEffect, LightingSettings, PowerState


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

    def save_profiles(self, profiles: dict[PowerState, LightingSettings]) -> None:
        self._write(
            {
                "version": 2,
                "profiles": {
                    state.name: self._encode(settings)
                    for state, settings in profiles.items()
                },
            }
        )

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
            "duration": settings.duration,
            "tempo": settings.tempo,
        }

    @staticmethod
    def _decode(data: dict) -> LightingSettings:
        return LightingSettings(
            enabled=bool(data["enabled"]),
            effect=LightingEffect(data["effect"]),
            primary_color=tuple(data["primary_color"]),
            brightness=int(data["brightness"]),
            secondary_color=(
                tuple(data["secondary_color"])
                if data.get("secondary_color") is not None
                else None
            ),
            duration=(int(data["duration"]) if data.get("duration") is not None else None),
            tempo=(int(data["tempo"]) if data.get("tempo") is not None else None),
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

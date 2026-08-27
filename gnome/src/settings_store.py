import json
import os
from pathlib import Path

from .backend import LightingEffect, LightingSettings


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
            return LightingSettings(
                enabled=bool(data["enabled"]),
                effect=LightingEffect(data["effect"]),
                primary_color=tuple(data["primary_color"]),
                brightness=int(data["brightness"]),
            )
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None

    def save(self, settings: LightingSettings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(
                {
                    "enabled": settings.enabled,
                    "effect": settings.effect.value,
                    "primary_color": list(settings.primary_color),
                    "brightness": settings.brightness,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)

from dataclasses import dataclass
from enum import Enum
from typing import Protocol, TypeAlias


RgbColor: TypeAlias = tuple[int, int, int]


class LightingEffect(Enum):
    STATIC = "static"
    MORPH = "morph"
    STATIC_AND_MORPH = "static-and-morph"


@dataclass(frozen=True)
class LightingCapabilities:
    effects: frozenset[LightingEffect]
    brightness: bool
    persistent_power_states: bool
    zone_count: int

    def __post_init__(self) -> None:
        if self.zone_count < 1:
            raise ValueError("zone_count must be at least one")


@dataclass(frozen=True)
class DeviceInfo:
    name: str
    controller: str
    firmware: str
    platform: str
    zones: int


@dataclass(frozen=True)
class LightingSettings:
    enabled: bool
    effect: LightingEffect
    primary_color: RgbColor
    brightness: int
    secondary_color: RgbColor | None = None
    duration: int | None = None

    def __post_init__(self) -> None:
        self._validate_color("primary_color", self.primary_color)
        if self.secondary_color is not None:
            self._validate_color("secondary_color", self.secondary_color)
        if not 0 <= self.brightness <= 100:
            raise ValueError("brightness must be between 0 and 100")
        if self.effect is not LightingEffect.STATIC:
            if self.secondary_color is None:
                raise ValueError("morph effects require a secondary color")
            if self.duration is None or self.duration < 1:
                raise ValueError("morph effects require a positive duration")

    @staticmethod
    def _validate_color(name: str, color: RgbColor) -> None:
        if len(color) != 3 or any(not 0 <= channel <= 255 for channel in color):
            raise ValueError(f"{name} channels must be between 0 and 255")


class LightingBackend(Protocol):
    @property
    def info(self) -> DeviceInfo: ...

    @property
    def capabilities(self) -> LightingCapabilities: ...

    @property
    def settings(self) -> LightingSettings: ...

    def apply_lighting(self, settings: LightingSettings) -> None: ...


class DemoBackend:
    """In-memory backend used for safe UI development and screenshots."""

    def __init__(self):
        self._info = DeviceInfo(
            name="Dell G16 7620",
            controller="Alienware AW-ELC 187c:0550",
            firmware="1.1.7",
            platform="0x0e09",
            zones=1,
        )
        self._capabilities = LightingCapabilities(
            effects=frozenset(
                {
                    LightingEffect.STATIC,
                    LightingEffect.MORPH,
                    LightingEffect.STATIC_AND_MORPH,
                }
            ),
            brightness=True,
            persistent_power_states=True,
            zone_count=self._info.zones,
        )
        self._settings = LightingSettings(
            enabled=True,
            effect=LightingEffect.STATIC,
            primary_color=(255, 0, 0),
            brightness=100,
        )

    @property
    def info(self) -> DeviceInfo:
        return self._info

    @property
    def capabilities(self) -> LightingCapabilities:
        return self._capabilities

    @property
    def settings(self) -> LightingSettings:
        return self._settings

    def apply_lighting(self, settings: LightingSettings) -> None:
        if settings.effect not in self.capabilities.effects:
            raise ValueError(f"unsupported lighting effect: {settings.effect.value}")
        self._settings = settings

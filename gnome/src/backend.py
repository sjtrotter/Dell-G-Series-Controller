from dataclasses import dataclass, replace
from enum import Enum
from typing import Protocol, TypeAlias

from .awelc_protocol import (
    AC_CHARGED,
    AC_CHARGING,
    AC_SLEEP,
    DC_LOW,
    DC_ON,
    DC_SLEEP,
    AwElcProtocol,
)
from .hidraw_transport import HidrawReportTransport


RgbColor: TypeAlias = tuple[int, int, int]


class LightingEffect(Enum):
    STATIC = "static"
    PULSE = "pulse"
    MORPH = "morph"
    BREATHING = "breathing"
    RAINBOW = "rainbow"
    STATIC_AND_MORPH = "static-and-morph"


class PowerState(Enum):
    AC_SLEEP = ("AC sleep", AC_SLEEP)
    AC_CHARGED = ("AC charged", AC_CHARGED)
    AC_CHARGING = ("AC charging", AC_CHARGING)
    BATTERY_SLEEP = ("Battery sleep", DC_SLEEP)
    BATTERY_ON = ("Battery on", DC_ON)
    BATTERY_LOW = ("Battery low", DC_LOW)

    def __init__(self, label: str, animation_id: int):
        self.label = label
        self.animation_id = animation_id


class BrightnessMode(Enum):
    HARDWARE_SCALING = "hardware-scaling"
    EXACT_SERVICE = "exact-service"


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
    tempo: int | None = None
    additional_colors: tuple[RgbColor, ...] = ()

    def __post_init__(self) -> None:
        self._validate_color("primary_color", self.primary_color)
        if self.secondary_color is not None:
            self._validate_color("secondary_color", self.secondary_color)
        for index, color in enumerate(self.additional_colors, start=2):
            self._validate_color(f"additional_colors[{index}]", color)
        if len(self.colors) > 12:
            raise ValueError("animations support at most 12 colors")
        if not 0 <= self.brightness <= 100:
            raise ValueError("brightness must be between 0 and 100")
        if self.effect is LightingEffect.MORPH:
            if len(self.colors) < 2:
                raise ValueError("morph effects require at least two colors")
        if self.effect is LightingEffect.BREATHING and len(self.colors) > 6:
            raise ValueError("breathing effects support at most six colors")
        if self.effect in {
            LightingEffect.PULSE,
            LightingEffect.MORPH,
            LightingEffect.BREATHING,
            LightingEffect.RAINBOW,
        }:
            if self.duration is None or self.duration < 1:
                raise ValueError("animated effects require a positive duration")
        if self.effect is LightingEffect.PULSE:
            if self.tempo is None or not 1 <= self.tempo <= 255:
                raise ValueError("pulse effects require a tempo between 1 and 255")

    @property
    def colors(self) -> tuple[RgbColor, ...]:
        if self.additional_colors:
            return (self.primary_color, *self.additional_colors)
        if self.secondary_color is not None:
            return (self.primary_color, self.secondary_color)
        return (self.primary_color,)

    @staticmethod
    def _validate_color(name: str, color: RgbColor) -> None:
        if len(color) != 3 or any(not 0 <= channel <= 255 for channel in color):
            raise ValueError(f"{name} channels must be between 0 and 255")


def unified_power_profiles(
    settings: LightingSettings,
) -> dict[PowerState, LightingSettings]:
    """Use one awake policy while keeping both firmware sleep slots off."""
    sleep = replace(settings, enabled=False)
    return {
        state: sleep
        if state in {PowerState.AC_SLEEP, PowerState.BATTERY_SLEEP}
        else settings
        for state in PowerState
    }


class LightingBackend(Protocol):
    @property
    def info(self) -> DeviceInfo: ...

    @property
    def capabilities(self) -> LightingCapabilities: ...

    @property
    def settings(self) -> LightingSettings: ...

    def apply_lighting(self, settings: LightingSettings) -> None: ...

    def apply_power_state(
        self,
        power_state: PowerState,
        settings: LightingSettings,
        brightness_mode: BrightnessMode = BrightnessMode.EXACT_SERVICE,
    ) -> None: ...


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
                    LightingEffect.PULSE,
                    LightingEffect.MORPH,
                    LightingEffect.BREATHING,
                    LightingEffect.RAINBOW,
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

    def apply_power_state(
        self,
        _power_state: PowerState,
        settings: LightingSettings,
        _brightness_mode: BrightnessMode = BrightnessMode.EXACT_SERVICE,
    ) -> None:
        self.apply_lighting(settings)


class AwElcBackend:
    """Hardware backend using verified persistent AW-ELC commands."""

    def __init__(
        self,
        protocol: AwElcProtocol,
        name: str = "Dell G Series laptop",
        initial_settings: LightingSettings | None = None,
    ):
        self._protocol = protocol
        version = protocol.get_version()
        platform, zone_count = protocol.get_platform()
        self._zones = tuple(range(zone_count))
        self._info = DeviceInfo(
            name=name,
            controller="Alienware AW-ELC",
            firmware=".".join(str(component) for component in version),
            platform=f"0x{platform:04x}",
            zones=zone_count,
        )
        self._capabilities = LightingCapabilities(
            effects=frozenset(
                {
                    LightingEffect.STATIC,
                    LightingEffect.PULSE,
                    LightingEffect.MORPH,
                    LightingEffect.BREATHING,
                    LightingEffect.RAINBOW,
                }
            ),
            brightness=True,
            persistent_power_states=True,
            zone_count=zone_count,
        )
        # Firmware 1.1.7 cannot read back the stored animation contents.
        self._settings = initial_settings or LightingSettings(
            enabled=False,
            effect=LightingEffect.STATIC,
            primary_color=(255, 255, 255),
            brightness=100,
        )

    @classmethod
    def discover(
        cls, initial_settings: LightingSettings | None = None
    ) -> "AwElcBackend":
        return cls(
            AwElcProtocol(HidrawReportTransport.discover()),
            initial_settings=initial_settings,
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

        for animation_id in (AC_CHARGED, AC_CHARGING, DC_ON):
            self._save_animation(animation_id, settings)
        # AW-ELC dimness is inverse: zero is full brightness.
        self._protocol.set_dimness(100 - settings.brightness, self._zones)
        self._settings = settings

    def apply_power_state(
        self,
        power_state: PowerState,
        settings: LightingSettings,
        brightness_mode: BrightnessMode = BrightnessMode.EXACT_SERVICE,
    ) -> None:
        if settings.effect not in self.capabilities.effects:
            raise ValueError(f"unsupported lighting effect: {settings.effect.value}")
        if power_state in {PowerState.AC_SLEEP, PowerState.BATTERY_SLEEP}:
            # A user service cannot run while the machine is suspended.
            brightness_mode = BrightnessMode.HARDWARE_SCALING
        stored_settings = settings
        if brightness_mode is BrightnessMode.HARDWARE_SCALING:
            stored_settings = self._scaled_settings(settings)
        self._save_animation(power_state.animation_id, stored_settings)
        dimness = 0 if brightness_mode is BrightnessMode.HARDWARE_SCALING else 100 - settings.brightness
        self._protocol.set_dimness(dimness, self._zones)
        self._settings = settings

    @staticmethod
    def _scaled_settings(settings: LightingSettings) -> LightingSettings:
        def scale(color: RgbColor | None) -> RgbColor | None:
            if color is None:
                return None
            return tuple(round(channel * settings.brightness / 100) for channel in color)

        return LightingSettings(
            enabled=settings.enabled,
            effect=settings.effect,
            primary_color=scale(settings.primary_color),
            brightness=100,
            secondary_color=scale(settings.secondary_color),
            duration=settings.duration,
            tempo=settings.tempo,
            additional_colors=tuple(scale(color) for color in settings.additional_colors),
        )

    def _save_animation(self, animation_id: int, settings: LightingSettings) -> None:
        color = settings.primary_color if settings.enabled else (0, 0, 0)
        if settings.enabled and settings.effect is LightingEffect.MORPH:
            if len(settings.colors) == 2:
                self._protocol.save_morph_animation(
                    animation_id,
                    settings.colors[0],
                    settings.colors[1],
                    self._zones,
                    settings.duration,
                )
            else:
                self._protocol.save_multicolor_morph_animation(
                    animation_id,
                    settings.colors,
                    self._zones,
                    settings.duration,
                )
        elif settings.enabled and settings.effect is LightingEffect.BREATHING:
            breathing_actions = tuple(
                action
                for color in settings.colors
                for action in (color, (0, 0, 0))
            )
            self._protocol.save_multicolor_morph_animation(
                animation_id,
                breathing_actions,
                self._zones,
                settings.duration,
            )
        elif settings.enabled and settings.effect is LightingEffect.RAINBOW:
            self._protocol.save_multicolor_morph_animation(
                animation_id,
                (
                    (255, 0, 0),
                    (255, 165, 0),
                    (255, 255, 0),
                    (0, 255, 0),
                    (0, 255, 255),
                    (0, 0, 255),
                    (128, 0, 255),
                ),
                self._zones,
                settings.duration,
            )
        elif settings.enabled and settings.effect is LightingEffect.PULSE:
            self._protocol.save_pulse_animation(
                animation_id,
                settings.primary_color,
                self._zones,
                settings.duration,
                settings.tempo,
            )
        else:
            self._protocol.save_static_animation(animation_id, color, self._zones)

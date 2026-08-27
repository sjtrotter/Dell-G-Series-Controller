from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FanReading:
    source: str
    index: int
    label: str
    rpm: int
    minimum_rpm: int | None
    maximum_rpm: int | None
    boost: int | None
    target_rpm: int | None
    pwm: int | None
    pwm_enable: int | None


@dataclass(frozen=True)
class TemperatureReading:
    source: str
    index: int
    label: str
    millidegrees_celsius: int


@dataclass(frozen=True)
class PlatformProfile:
    active: str
    choices: tuple[str, ...]


def inspect_hwmon(sys_root: Path = Path("/sys")):
    fans = []
    temperatures = []
    for device in sorted((sys_root / "class" / "hwmon").glob("hwmon*")):
        source = _read_text(device / "name")
        if source is None:
            continue
        for input_path in sorted(device.glob("fan*_input")):
            index = int(input_path.stem.removeprefix("fan").removesuffix("_input"))
            rpm = _read_int(input_path)
            if rpm is None:
                continue
            prefix = f"fan{index}"
            fans.append(
                FanReading(
                    source=source,
                    index=index,
                    label=_read_text(device / f"{prefix}_label") or f"Fan {index}",
                    rpm=rpm,
                    minimum_rpm=_read_int(device / f"{prefix}_min"),
                    maximum_rpm=_read_int(device / f"{prefix}_max"),
                    boost=_read_int(device / f"{prefix}_boost"),
                    target_rpm=_read_int(device / f"{prefix}_target"),
                    pwm=_read_int(device / f"pwm{index}"),
                    pwm_enable=_read_int(device / f"pwm{index}_enable"),
                )
            )
        for input_path in sorted(device.glob("temp*_input")):
            index = int(input_path.stem.removeprefix("temp").removesuffix("_input"))
            value = _read_int(input_path)
            if value is None:
                continue
            temperatures.append(
                TemperatureReading(
                    source=source,
                    index=index,
                    label=(
                        _read_text(device / f"temp{index}_label")
                        or f"Temperature {index}"
                    ),
                    millidegrees_celsius=value,
                )
            )
    return tuple(fans), tuple(temperatures)


def inspect_platform_profile(sys_root: Path = Path("/sys")):
    profile_root = sys_root / "firmware" / "acpi"
    active = _read_text(profile_root / "platform_profile")
    choices = _read_text(profile_root / "platform_profile_choices")
    if active is None or choices is None:
        return None
    return PlatformProfile(active, tuple(choices.split()))


def _read_text(path):
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def _read_int(path):
    value = _read_text(path)
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None

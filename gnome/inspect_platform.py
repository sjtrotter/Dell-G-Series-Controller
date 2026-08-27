#!/usr/bin/python3

from src.platform_hardware import inspect_hwmon, inspect_platform_profile


def main():
    fans, temperatures = inspect_hwmon()
    profile = inspect_platform_profile()

    print("fans:")
    if not fans:
        print("  none exposed by hwmon")
    for fan in fans:
        details = [f"{fan.rpm} RPM"]
        if fan.minimum_rpm is not None and fan.maximum_rpm is not None:
            details.append(f"range {fan.minimum_rpm}–{fan.maximum_rpm} RPM")
        if fan.boost is not None:
            details.append(f"boost {fan.boost}")
        if fan.target_rpm is not None:
            details.append(f"target {fan.target_rpm} RPM")
        if fan.pwm is not None:
            details.append(f"PWM {fan.pwm}")
        if fan.pwm_enable is not None:
            details.append(f"PWM mode {fan.pwm_enable}")
        print(f"  {fan.source}: {fan.label}: " + "; ".join(details))

    print("temperatures:")
    for reading in temperatures:
        if reading.source not in {"alienware_wmi", "dell_ddv", "dell_smm"}:
            continue
        celsius = reading.millidegrees_celsius / 1000
        print(f"  {reading.source}: {reading.label}: {celsius:.1f} °C")

    print("platform profile:")
    if profile is None:
        print("  not exposed")
    else:
        print(f"  active: {profile.active}")
        print(f"  choices: {', '.join(profile.choices)}")


if __name__ == "__main__":
    main()

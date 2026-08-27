#!/usr/bin/python3
"""Apply exact per-profile AW-ELC dimness as awake power state changes."""

import argparse
import signal
import time
from pathlib import Path

from src.awelc_protocol import AwElcProtocol
from src.backend import BrightnessMode, PowerState
from src.hidraw_transport import HidrawReportTransport
from src.settings_store import LightingSettingsStore
from src.usb_transport import DeviceAccessError, DeviceNotFoundError


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def detect_power_state(root: Path = Path("/sys/class/power_supply")) -> PowerState:
    ac_online = any(
        _read(path / "type") == "Mains" and _read(path / "online") == "1"
        for path in root.iterdir()
    )
    batteries = [path for path in root.iterdir() if _read(path / "type") == "Battery"]
    battery = batteries[0] if batteries else None
    status = _read(battery / "status") if battery else None
    try:
        capacity = int(_read(battery / "capacity") or "100") if battery else 100
    except ValueError:
        capacity = 100

    if ac_online:
        return PowerState.AC_CHARGED if status == "Full" else PowerState.AC_CHARGING
    return PowerState.BATTERY_LOW if capacity <= 15 else PowerState.BATTERY_ON


class BrightnessService:
    def __init__(
        self,
        store: LightingSettingsStore,
        power_supply_root: Path,
        protocol: AwElcProtocol | None = None,
    ):
        self.store = store
        self.power_supply_root = power_supply_root
        self.protocol = protocol or AwElcProtocol(HidrawReportTransport.discover())
        _, zone_count = self.protocol.get_platform()
        self.zones = tuple(range(zone_count))
        self.last_signature = None

    def update(self) -> tuple[PowerState, int] | None:
        if self.store.load_brightness_mode() is not BrightnessMode.EXACT_SERVICE:
            return None
        state = detect_power_state(self.power_supply_root)
        settings = self.store.load_profiles()[state]
        try:
            modified = self.store.path.stat().st_mtime_ns
        except OSError:
            modified = 0
        signature = (state, settings.brightness, modified)
        if signature == self.last_signature:
            return None
        self.protocol.set_dimness(100 - settings.brightness, self.zones)
        self.last_signature = signature
        return state, settings.brightness


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="apply once and exit")
    parser.add_argument("--interval", type=float, default=2.0)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    if args.interval <= 0:
        parser.error("--interval must be positive")

    try:
        service = BrightnessService(
            LightingSettingsStore(), Path("/sys/class/power_supply")
        )
    except (DeviceAccessError, DeviceNotFoundError) as error:
        parser.error(str(error))

    running = True

    def stop(_signal, _frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    while running:
        changed = service.update()
        if args.verbose and changed is not None:
            state, brightness = changed
            print(
                f"applied {state.label} brightness {brightness}%",
                flush=True,
            )
        if args.once:
            break
        time.sleep(args.interval)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/python3

import argparse
import sys

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from src.application import Application
from src.backend import AwElcBackend, DemoBackend, PowerState
from src.settings_store import LightingSettingsStore


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--demo",
        action="store_true",
        help="show the interface without accessing hardware",
    )
    mode.add_argument(
        "--zone-demo",
        action="store_true",
        help="show a synthetic four-zone layout without accessing hardware",
    )
    mode.add_argument(
        "--hardware",
        action="store_true",
        help="connect to a supported AW-ELC controller",
    )
    mode.add_argument(
        "--loading-demo",
        action="store_true",
        help="show only the persistent hardware loading window",
    )
    args = parser.parse_args()

    if args.hardware:
        settings_store = LightingSettingsStore()
        profiles = settings_store.load_profiles()
        backend = None
        backend_factory = lambda: AwElcBackend.discover(
            profiles[PowerState.AC_CHARGED]
        )
    elif args.demo or args.zone_demo:
        backend = DemoBackend(
            zone_count=4 if args.zone_demo else 1,
            platform="zone-demo" if args.zone_demo else "0x0e09",
        )
        settings_store = None
        backend_factory = None
    else:
        backend = None
        settings_store = None
        backend_factory = None

    app = Application(
        backend,
        settings_store,
        backend_factory,
        loading_only=args.loading_demo,
    )
    return app.run(sys.argv[:1])


if __name__ == "__main__":
    raise SystemExit(main())

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
    parser.add_argument(
        "--demo",
        action="store_true",
        help="show the interface without accessing hardware",
    )
    parser.add_argument(
        "--hardware",
        action="store_true",
        help="connect to a supported AW-ELC controller",
    )
    args = parser.parse_args()

    if args.demo == args.hardware:
        parser.error("choose exactly one of --demo or --hardware")

    if args.hardware:
        settings_store = LightingSettingsStore()
        profiles = settings_store.load_profiles()
        backend = None
        backend_factory = lambda: AwElcBackend.discover(
            profiles[PowerState.AC_CHARGED]
        )
    else:
        backend = DemoBackend()
        settings_store = None
        backend_factory = None

    app = Application(backend, settings_store, backend_factory)
    return app.run(sys.argv[:1])


if __name__ == "__main__":
    raise SystemExit(main())

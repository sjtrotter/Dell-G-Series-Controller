#!/usr/bin/python3

import argparse
import sys

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from src.application import Application
from src.backend import AwElcBackend, DemoBackend
from src.settings_store import LightingSettingsStore
from src.usb_transport import DeviceAccessError, DeviceNotFoundError


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
        try:
            backend = AwElcBackend.discover(settings_store.load())
        except (DeviceAccessError, DeviceNotFoundError) as error:
            parser.error(str(error))
    else:
        backend = DemoBackend()
        settings_store = None

    app = Application(backend, settings_store)
    return app.run(sys.argv[:1])


if __name__ == "__main__":
    raise SystemExit(main())

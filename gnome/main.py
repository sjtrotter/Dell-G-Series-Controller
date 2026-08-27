#!/usr/bin/python3

import argparse
import sys

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from src.application import Application
from src.backend import DemoBackend


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--demo",
        action="store_true",
        help="show the interface without accessing hardware",
    )
    args = parser.parse_args()

    if not args.demo:
        parser.error("hardware mode is not implemented yet; use --demo")

    app = Application(DemoBackend())
    return app.run(sys.argv[:1])


if __name__ == "__main__":
    raise SystemExit(main())

# GNOME frontend

This directory contains an experimental GTK 4/libadwaita frontend. It is kept
separate from the legacy Qt application while the hardware backend and
packaging are stabilized.

Run the interface without accessing hardware:

```sh
python3 gnome/main.py --demo
```

Hardware access is deliberately unavailable until the AW-ELC backend has a
safe, testable API and appropriate device permissions.

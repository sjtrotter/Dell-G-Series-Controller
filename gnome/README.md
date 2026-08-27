# GNOME frontend

This directory contains an experimental GTK 4/libadwaita frontend. It is kept
separate from the legacy Qt application while the hardware backend and
packaging are stabilized.

Run the interface without accessing hardware:

```sh
python3 gnome/main.py --demo
```

Connect to an AW-ELC controller using the tested static-color backend:

```sh
python3 gnome/main.py --hardware
```

Hardware mode does not invoke `sudo`, reset the USB device, or detach its
kernel driver. The USB device must be accessible to the current user; a
narrowly scoped udev rule will be provided with the packaged application.

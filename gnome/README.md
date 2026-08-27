# GNOME frontend

This directory contains an experimental GTK 4/libadwaita frontend. It is kept
separate from the legacy Qt application while the hardware backend and
packaging are stabilized.

Run the interface without accessing hardware:

```sh
python3 gnome/main.py --demo
```

Connect to an AW-ELC controller using the tested persistent static-color backend:

```sh
python3 gnome/main.py --hardware
```

Hardware mode does not invoke `sudo`, reset the USB device, or detach its
kernel driver. The USB device must be accessible to the current user; a
narrowly scoped udev rule will be provided with the packaged application.
The power-state selector edits any one of the controller's six firmware slots:
AC sleep, charged, and charging; and battery sleep, on, and low. Apply writes
only the selected slot. Brightness remains global because AW-ELC exposes
dimness separately from the stored animations.

Verified effects on AW-ELC firmware 1.1.7 are static color, a two-color smooth
morph, and the firmware's pulse effect. Pulse is presented as Flash: it uses
one color, with duration controlling the action cycle and tempo controlling
the flash rate. Morph accepts the same tempo field at the protocol level, but
testing on firmware 1.1.7 found no visible effect; its UI exposes duration only.

For development, install the included device-access rule and reload udev:

```sh
sudo install -Dm644 gnome/data/70-dell-g-series-controller.rules \
  /usr/lib/udev/rules.d/70-dell-g-series-controller.rules
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=usb --attr-match=idVendor=187c
```

The rule uses systemd-logind's `uaccess` tag, granting access only to the
active local session rather than making the controller globally writable.

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

For development, install the included device-access rule and reload udev:

```sh
sudo install -Dm644 gnome/data/70-dell-g-series-controller.rules \
  /usr/lib/udev/rules.d/70-dell-g-series-controller.rules
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=usb --attr-match=idVendor=187c
```

The rule uses systemd-logind's `uaccess` tag, granting access only to the
active local session rather than making the controller globally writable.

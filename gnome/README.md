# Dell G-Series Laptop Keyboard Controller

This directory contains an experimental GTK 4/libadwaita frontend for the
Dell G-Series Laptop Keyboard Controller. It is kept separate from the legacy
Qt application while the hardware backend and packaging are stabilized.

## Interface design

The interface takes GNOME Settings' Power panel as its main reference. AC and
battery behavior are presented as power policies instead of exposing the
controller's six firmware slots in a drop-down. Common lighting controls remain
visible, while animation timing, brightness-backend choices, and hardware
details use native libadwaita expander rows. Unavailable performance and fan
controls are omitted.

Run the interface without accessing hardware:

```sh
python3 gnome/main.py --demo
```

To inspect the hardware loading window without accessing USB hardware or
automatically dismissing it:

```bash
python3 gnome/main.py --loading-demo
```

The marks displayed there are sourced from the Simple Icons
[Alienware](https://simpleicons.org/?q=alienware) and
[Dell](https://simpleicons.org/?q=dell) assets. Dell and Alienware are
trademarks of Dell Inc. or its subsidiaries; their appearance identifies
compatible hardware and does not imply endorsement of this application.

Connect to an AW-ELC controller using the tested persistent static-color backend:

```sh
python3 gnome/main.py --hardware
```

Hardware mode does not invoke `sudo`, reset the USB device, or detach its
kernel driver. The USB device must be accessible to the current user; a
narrowly scoped udev rule will be provided with the packaged application.
The Profile selector edits the controller's AC, battery, sleep, and low-battery
animation slots independently. Turning off **Customize by power state** hides
those selectors and writes the same settings into the four awake firmware
slots while explicitly saving both sleep slots as off. The controller does not
provide profile inheritance or a fallback slot. Profile brightness offers two
implementations:

- **Hardware-only color scaling** stores brightness-adjusted RGB values and
  leaves global dimness at full. It works before login and during suspend, but
  low levels lose some RGB precision.
- **Exact brightness service** stores unmodified RGB values. The unprivileged
  user service watches AC/battery state and sends the controller's separate
  global dimness command. Sleep profiles still use hardware scaling because a
  user service cannot run while the machine is suspended.

Verified primitive effects on AW-ELC firmware 1.1.7 are static color, Morph,
and the firmware's Pulse effect. Pulse is presented as Flash: it uses one
color, with duration controlling the action cycle and tempo controlling the
flash rate. Morph accepts the same tempo field at the protocol level, but
testing on firmware 1.1.7 found no visible effect; its UI exposes duration only.
Breathing is composed from Morph targets for the selected color and black.
Rainbow is composed from seven predefined Morph targets.
The animation protocol and hardware were also verified with Morph sequences of
up to 12 color targets across four action reports. The Morph editor supports
adding, removing, and reordering targets within that verified limit. Firmware
Morph can introduce a dark phase between some otherwise bright color pairs
(including red and yellow), so this is treated as controller behavior rather
than software RGB interpolation.

For an unpackaged development checkout, test exact brightness once with:

```sh
python3 gnome/service.py --once
```

Run it continuously in the foreground on any desktop with:

```sh
python3 gnome/service.py --verbose
```

On a systemd desktop, install a user unit pointing at the current development
checkout and enable it:

```sh
sh gnome/install-dev-service.sh
systemctl --user enable --now dell-g-series-controller-brightness.service
systemctl --user status dell-g-series-controller-brightness.service
```

This is a user unit: it runs as the logged-in user and never uses `sudo`.
It is the same long-running foreground service wrapped by systemd, so a timer
is neither required nor installed. State changes are written to the user
journal and can be inspected with:

```sh
journalctl --user -u dell-g-series-controller-brightness.service
```

The foreground and systemd launch paths share a per-user runtime lock. The
interface uses that lock to report whether exact brightness is active, and a
second service instance is rejected before it can compete for the controller.

The packaged service unit is
`dell-g-series-controller-brightness.service`. After its executable and unit
are installed, enable it with:

```sh
systemctl --user enable --now dell-g-series-controller-brightness.service
```

For development, install the included device-access rule and reload udev:

```sh
sudo install -Dm644 gnome/data/70-dell-g-series-controller.rules \
  /usr/lib/udev/rules.d/70-dell-g-series-controller.rules
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=usb --attr-match=idVendor=187c
```

The rule uses systemd-logind's `uaccess` tag, granting access only to the
active local session rather than making the controller globally writable.

The service rediscovers the hidraw device after temporary access failures,
USB re-enumeration, and suspend/resume. Brightness persistence is currently
treated as a platform capability: global dimness is known to be volatile on
firmware 1.1.7/platform `0x0e09`, but must be verified independently on other
AW-ELC firmware and platform combinations.

## Packaging test

The GNOME frontend has an isolated Meson project. Build, test, and stage an
installation without modifying the host system:

```sh
meson setup gnome/_build gnome
meson test -C gnome/_build
DESTDIR="$PWD/gnome/_stage" meson install -C gnome/_build
```

The staged tree contains the application launcher, runtime, desktop entry,
AppStream metadata, icon, systemd user unit, and udev rule. Installing the
staged files system-wide is intentionally a separate packaging step.

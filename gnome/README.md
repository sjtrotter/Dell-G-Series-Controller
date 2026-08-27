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

The bottom bar keeps Apply, Configurations, and Save New available while the
settings page scrolls. Selecting a named configuration loads its complete set
of AC, battery, and sleep profiles into the editor; it is not written to the
keyboard until **Apply** is pressed. Apply remains disabled until the editor
contains unapplied changes. The configurations popover presents every saved
item as a directly loadable row with its own delete action.

Controller writes run on a worker thread. During a transaction the Apply button
shows **Applying…**, duplicate writes and configuration changes are disabled,
and GTK continues drawing and responding to window events.

## Settings storage

Installed GNOME builds prefer GSettings (normally backed by dconf) using the
included `io.github.cemkaya_mpi.dell-g-series-controller` schema. If the schema
or GIO settings support is unavailable, the same versioned document is stored
as JSON at:

```text
~/.config/dell-g-series-controller/settings.json
```

On first use of GSettings, an existing JSON document is imported automatically.
The JSON file is left in place as a recoverable migration source. Explicit file
paths used by tests and portable integrations always select the JSON backend.

Run the interface without accessing hardware:

```sh
python3 gnome/main.py --demo
```

The frontend requires Python 3, PyGObject, GTK 4, and libadwaita. Building and
running the packaging tests additionally requires Meson and GLib's schema
compiler. On Fedora these development-checkout dependencies can be installed
with:

```sh
sudo dnf install python3-gobject gtk4 libadwaita meson glib2-devel
```

Preview the multi-zone interaction without accessing USB hardware:

```sh
python3 gnome/main.py --zone-demo
```

This is a stateful, in-memory four-zone mock. Click anywhere on the rendered
keyboard to select the nearest zone, edit each zone independently, and use
**Apply** to write the settings back to mock memory. The colored zone geometry
is intentionally synthetic: AW-ELC reports zone IDs and a count, but not their
physical keyboard positions. This mode verifies UI behavior only and is not
evidence that a particular controller supports every effect combination.

To inspect the hardware loading window without accessing USB hardware or
automatically dismissing it:

```bash
python3 gnome/main.py --loading-demo
```

Connect to an AW-ELC controller using the tested persistent static-color backend:

```sh
python3 gnome/main.py --hardware
```

Hardware mode does not invoke `sudo`, reset the USB device, or detach its
kernel driver. The USB device must be accessible to the current user; the
packaged application can include a narrowly scoped udev rule. Neither udev nor
systemd is a runtime dependency of the application.

Inspect kernel-provided fan, temperature, and platform-profile support without
making hardware changes:

```sh
python3 gnome/inspect_platform.py
```

On supported systems these controls come from the standard `alienware_wmi`,
`dell_wmi_ddv`, and `dell_smm_hwmon` drivers. New code must use those kernel
interfaces instead of invoking the legacy application's raw ACPI methods.
The Profile selector edits the controller's AC, battery, sleep, and low-battery
animation slots independently. Turning off **Customize by power state** hides
those selectors and writes the same settings into the four awake firmware
slots while explicitly saving both sleep slots as off. The controller does not
provide profile inheritance or a fallback slot. Profile brightness offers two
implementations:

Morph supports up to 12 transition colors. Breathing uses the same verified
Morph primitive with black inserted between selected colors, supporting up to
six colors within the verified 12-action bound.

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

The protocol can place multiple action series, each targeting a different set
of zone IDs, inside one stored power-state animation. That transaction shape is
implemented and unit tested from the legacy controller behavior, but has not
been exercised on this project's single-zone Dell G16 7620 test machine.
Independent multi-zone effects, synchronization, physical zone maps, and
device-specific action limits therefore require validation on real multi-zone
hardware before they should be enabled as a production editing mode.

## Upstream hardware test checklist

Use `--zone-demo` first to review the interaction without a controller. On a
test machine with AW-ELC hardware:

1. Confirm the USB ID is `187c:0550` or `187c:0551` and install the scoped udev
   rule shown below.
2. Run `python3 gnome/main.py --hardware` as the desktop user, never with
   `sudo`.
3. Verify static color and brightness, then Morph, Breathing, Rainbow, and
   Flash. **Apply** replaces the selected firmware power-state animation.
4. Confirm the stored effect returns after the controller's lighting timeout,
   suspend/resume, AC changes, and reboot.
5. On multi-zone hardware, record the platform ID, reported zone count, actual
   physical zone ordering, supported independent effects, and any transaction
   failure before adding its layout to the validated registry.

The firmware does not expose readable animation contents on the tested
firmware. Keep a known-good configuration available because an interrupted
write may require applying it again.

Linux hidraw report ioctls do not provide a portable per-call timeout. Hardware
writes therefore run outside the GTK thread, and the systemd service has a
bounded stop timeout, but a wedged kernel/device ioctl can leave one Apply
worker waiting until the kernel returns it. This is a known transport limitation
and is a reason to keep the frontend experimental while broader hardware is
tested.

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
sudo udevadm trigger --subsystem-match=hidraw
```

The rule uses systemd-logind's `uaccess` tag, granting access only to the
active local session rather than making the controller globally writable.

### Systems without udev or systemd

The controller backend opens `/dev/hidraw*` directly and identifies candidates
through `/sys/class/hidraw/*/device/uevent`. A system using eudev or another
udev-compatible manager can use the included rule when its seat/ACL integration
implements the `uaccess` tag. Other device managers must grant the logged-in
user read/write access to only the hidraw node whose `HID_ID` is one of:

```text
0003:0000187C:00000550
0003:0000187C:00000551
```

For a temporary test, an administrator can identify the matching node under
`/sys/class/hidraw`, then grant an ACL with:

```sh
sudo setfacl -m "u:$USER:rw" /dev/hidrawN
```

That ACL normally disappears when the device is re-enumerated. A persistent
mdev/devtmpfs setup should apply an equivalent owner, group, or ACL rule during
device creation. Do not run the graphical application as root and do not make
every hidraw node world-writable.

The exact-brightness helper is an ordinary foreground process and can be run
under any user service supervisor:

```sh
python3 gnome/service.py --verbose
```

Packagers can omit both integration files:

```sh
meson setup gnome/_build gnome \
  -Dinstall_udev_rule=false \
  -Dinstall_systemd_user_unit=false
```

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

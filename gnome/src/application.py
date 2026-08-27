import gi
import threading
import time

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw, Gdk, GLib, Gtk

from .backend import (
    BrightnessMode,
    LightingEffect,
    LightingSettings,
    PowerState,
    unified_power_profiles,
)
from .service_status import service_is_running
from .usb_transport import DeviceAccessError, DeviceNotFoundError


class Application(Adw.Application):
    MINIMUM_LOADING_SECONDS = 1.25

    def __init__(
        self,
        backend,
        settings_store=None,
        backend_factory=None,
        loading_only=False,
    ):
        application_id = "io.github.cemkaya_mpi.DellGSeriesController"
        if settings_store is None:
            application_id += ".Demo"
        super().__init__(application_id=application_id)
        self.backend = backend
        self.backend_factory = backend_factory
        self.settings_store = settings_store
        self.loading_only = loading_only
        if settings_store is not None:
            self.profiles = settings_store.load_profiles()
            self.brightness_mode = settings_store.load_brightness_mode()
            self.separate_power_profiles = (
                settings_store.load_separate_power_profiles()
            )
        elif backend is not None:
            self.profiles = {state: backend.settings for state in PowerState}
            self.brightness_mode = BrightnessMode.HARDWARE_SCALING
            self.separate_power_profiles = True
        else:
            self.profiles = {
                state: LightingSettings() for state in PowerState
            }
            self.brightness_mode = BrightnessMode.HARDWARE_SCALING
            self.separate_power_profiles = True
        self.connect("activate", self.on_activate)
        self._discovering = False

    def on_activate(self, _application):
        window = self.props.active_window
        if window is None:
            if self.loading_only:
                LoadingWindow(self).present()
                return
            if self.backend is None:
                window = LoadingWindow(self)
                window.present()
                self._start_discovery(window)
                return
            window = MainWindow(self, self.backend, self.settings_store)
        window.present()

    def _start_discovery(self, loading_window):
        if self._discovering:
            return
        self._discovering = True

        def discover():
            try:
                backend = self.backend_factory()
            except (DeviceAccessError, DeviceNotFoundError) as error:
                GLib.idle_add(self._discovery_failed, loading_window, str(error))
                return
            GLib.idle_add(self._discovery_finished, loading_window, backend)

        threading.Thread(target=discover, daemon=True).start()

    def _discovery_finished(self, loading_window, backend):
        remaining = self.MINIMUM_LOADING_SECONDS - (
            time.monotonic() - loading_window.shown_at
        )
        if remaining > 0:
            GLib.timeout_add(
                max(1, round(remaining * 1000)),
                self._discovery_finished,
                loading_window,
                backend,
            )
            return GLib.SOURCE_REMOVE
        self._discovering = False
        self.backend = backend
        loading_window.close()
        MainWindow(self, backend, self.settings_store).present()
        return GLib.SOURCE_REMOVE

    def _discovery_failed(self, loading_window, message):
        self._discovering = False
        dialog = Adw.AlertDialog(
            heading="Keyboard controller unavailable",
            body=message,
        )
        dialog.add_response("close", "Close")
        dialog.set_default_response("close")
        dialog.connect("response", lambda *_args: self.quit())
        dialog.present(loading_window)
        return GLib.SOURCE_REMOVE


class LoadingWindow(Adw.ApplicationWindow):
    def __init__(self, application):
        super().__init__(application=application)
        self.shown_at = time.monotonic()
        self.set_title("Dell G-Series Laptop Keyboard Controller")
        self.set_default_size(460, 540)
        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(Adw.HeaderBar())
        status = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        status.set_halign(Gtk.Align.CENTER)
        status.set_valign(Gtk.Align.CENTER)
        status.append(AlienMark())
        brands = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        brands.set_halign(Gtk.Align.CENTER)
        alienware = Gtk.Label(label="ALIENWARE")
        alienware.add_css_class("heading")
        brands.append(alienware)
        separator = Gtk.Label(label="•")
        separator.add_css_class("dim-label")
        brands.append(separator)
        dell = Gtk.Label(label="DELL G-SERIES")
        dell.add_css_class("heading")
        brands.append(dell)
        status.append(brands)
        keyboard = Gtk.Image.new_from_icon_name("input-keyboard-symbolic")
        keyboard.set_pixel_size(44)
        status.append(keyboard)
        title = Gtk.Label(label="Connecting to keyboard")
        title.add_css_class("title-1")
        status.append(title)
        description = Gtk.Label(label="Waiting for the Alienware AW-ELC controller")
        description.add_css_class("dim-label")
        status.append(description)
        spinner = Adw.Spinner()
        spinner.set_size_request(32, 32)
        spinner.set_halign(Gtk.Align.CENTER)
        status.append(spinner)
        toolbar_view.set_content(status)
        self.set_content(toolbar_view)


class AlienMark(Gtk.DrawingArea):
    """Small original monochrome alien motif for the connection screen."""

    def __init__(self):
        super().__init__()
        self.set_content_width(156)
        self.set_content_height(123)
        self.set_size_request(156, 123)
        self.set_draw_func(self._draw)

    @staticmethod
    def _draw(_area, context, width, height):
        context.save()
        context.translate(width / 2, height / 2)
        context.scale(width / 104, height / 82)

        context.set_source_rgba(1, 1, 1, 0.96)
        context.move_to(0, -36)
        context.curve_to(-34, -34, -46, -13, -35, 12)
        context.curve_to(-27, 30, -11, 39, 0, 40)
        context.curve_to(11, 39, 27, 30, 35, 12)
        context.curve_to(46, -13, 34, -34, 0, -36)
        context.close_path()
        context.fill()

        context.set_source_rgba(0.08, 0.09, 0.11, 1)
        for x in (-17, 17):
            context.save()
            context.translate(x, 2)
            context.rotate(-0.22 if x < 0 else 0.22)
            context.scale(1.0, 1.65)
            context.arc(0, 0, 7, 0, 6.283185307)
            context.fill()
            context.restore()
        context.restore()


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, application, backend, settings_store=None):
        super().__init__(application=application)
        self.backend = backend
        self.settings_store = settings_store
        self.profiles = application.profiles
        self.brightness_mode = application.brightness_mode
        self.separate_power_profiles = application.separate_power_profiles
        self.set_title("Dell G-Series Laptop Keyboard Controller")
        self.set_default_size(620, 640)

        self.toast_overlay = Adw.ToastOverlay()
        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(Adw.HeaderBar())
        toolbar_view.set_content(self._build_page())
        self.toast_overlay.set_child(toolbar_view)
        self.set_content(self.toast_overlay)

    def _build_page(self):
        page = Adw.PreferencesPage()

        profile_group = Adw.PreferencesGroup(title="Power profile")
        profile_group.set_description(
            "Choose how the keyboard behaves in each power state."
        )
        self.profile_mode = Adw.SwitchRow(
            title="Customize by power state",
            subtitle="Use separate lighting for AC, battery, and sleep states",
        )
        self.profile_mode.set_active(self.separate_power_profiles)
        profile_group.add(self.profile_mode)
        profile_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.profile_box = profile_box
        self.power_source = self._toggle_group(
            (("ac", "AC Power"), ("battery", "Battery"))
        )
        self.ac_state = self._toggle_group(
            (("charged", "Charged"), ("charging", "Charging"), ("sleep", "Sleep"))
        )
        self.battery_state = self._toggle_group(
            (("normal", "Normal"), ("low", "Low"), ("sleep", "Sleep"))
        )
        self.power_source.set_active_name("ac")
        self.ac_state.set_active_name("charged")
        self.battery_state.set_active_name("normal")
        self.battery_state.set_visible(False)
        profile_box.append(self.power_source)
        profile_box.append(self.ac_state)
        profile_box.append(self.battery_state)
        profile_group.add(profile_box)
        page.add(profile_group)

        lighting_group = Adw.PreferencesGroup(title="Keyboard lighting")
        if self.backend.capabilities.persistent_power_states:
            lighting_group.set_description(
                "Displayed values are remembered locally because firmware 1.1.7 "
                "cannot read them back. Applied changes persist across timeouts."
            )
        else:
            lighting_group.set_description(
                "Static changes are sent directly to the connected controller."
            )

        self.brightness_modes = [
            BrightnessMode.HARDWARE_SCALING,
            BrightnessMode.EXACT_SERVICE,
        ]
        self.brightness_method = Gtk.DropDown.new_from_strings(
            ["Hardware-only color scaling", "Exact brightness service"]
        )
        self.brightness_method.set_selected(
            self.brightness_modes.index(self.brightness_mode)
        )
        self.brightness_method_row = Adw.ActionRow(title="Method")
        self.brightness_method_row.add_suffix(self.brightness_method)
        self.brightness_method_row.set_activatable_widget(self.brightness_method)

        self.enabled = Adw.SwitchRow(title="Lighting enabled")
        self.enabled.set_active(self.backend.settings.enabled)
        lighting_group.add(self.enabled)

        self.effects = [LightingEffect.STATIC]
        if LightingEffect.PULSE in self.backend.capabilities.effects:
            self.effects.append(LightingEffect.PULSE)
        if LightingEffect.MORPH in self.backend.capabilities.effects:
            self.effects.append(LightingEffect.MORPH)
        if LightingEffect.BREATHING in self.backend.capabilities.effects:
            self.effects.append(LightingEffect.BREATHING)
        if LightingEffect.RAINBOW in self.backend.capabilities.effects:
            self.effects.append(LightingEffect.RAINBOW)
        self.effect = Gtk.DropDown.new_from_strings(
            [
                {
                    LightingEffect.STATIC: "Static",
                    LightingEffect.PULSE: "Flash (firmware Pulse)",
                    LightingEffect.MORPH: "Morph",
                    LightingEffect.BREATHING: "Breathing",
                    LightingEffect.RAINBOW: "Rainbow",
                }[effect]
                for effect in self.effects
            ]
        )
        try:
            selected_effect = self.effects.index(self.backend.settings.effect)
        except ValueError:
            selected_effect = 0
        self.effect.set_selected(selected_effect)
        effect_row = Adw.ActionRow(
            title="Effect", subtitle="Static or firmware animation recipe"
        )
        effect_row.add_suffix(self.effect)
        effect_row.set_activatable_widget(self.effect)
        lighting_group.add(effect_row)

        self.color = Gtk.ColorDialogButton(dialog=Gtk.ColorDialog(title="Keyboard color"))
        rgba = Gdk.RGBA()
        red, green, blue = self.backend.settings.primary_color
        rgba.red, rgba.green, rgba.blue, rgba.alpha = (
            red / 255,
            green / 255,
            blue / 255,
            1.0,
        )
        self.color.set_rgba(rgba)
        color_row = Adw.ActionRow(title="Color", subtitle="Static keyboard color")
        self.color_row = color_row
        color_row.add_suffix(self.color)
        color_row.set_activatable_widget(self.color)
        lighting_group.add(color_row)

        self.morph_colors = Adw.ExpanderRow(
            title="Morph colors",
            subtitle="Additional transition targets",
        )
        self.additional_color_rows = []
        self.additional_color_buttons = []
        self.add_color_button = Gtk.Button(label="Add Color")
        self.add_color_button.set_valign(Gtk.Align.CENTER)
        self.add_color_button.connect("clicked", self._add_color_clicked)
        self.add_color_row = Adw.ActionRow(
            title="Add another color",
            subtitle="Up to 12 transition targets",
        )
        self.add_color_row.add_suffix(self.add_color_button)
        self.add_color_row.set_activatable_widget(self.add_color_button)
        initial_colors = self.backend.settings.colors[1:] or ((0, 0, 255),)
        for color in initial_colors:
            self._add_morph_color(color)
        self.morph_colors.add_row(self.add_color_row)
        lighting_group.add(self.morph_colors)

        self.duration = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 4, 4095, 1
        )
        self.duration.set_value(self.backend.settings.duration or 500)
        self.duration.set_size_request(220, -1)
        self.duration.set_hexpand(True)
        self.duration.set_draw_value(True)
        self.duration.set_value_pos(Gtk.PositionType.RIGHT)
        self.duration_row = Adw.ActionRow(
            title="Effect duration", subtitle="Firmware animation timing"
        )
        self.duration_row.add_suffix(self.duration)

        self.tempo = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 1, 255, 1)
        self.tempo.set_value(self.backend.settings.tempo or 100)
        self.tempo.set_size_request(220, -1)
        self.tempo.set_hexpand(True)
        self.tempo.set_draw_value(True)
        self.tempo.set_value_pos(Gtk.PositionType.RIGHT)
        self.tempo_row = Adw.ActionRow(
            title="Flash tempo", subtitle="Pulse flash rate"
        )
        self.tempo_row.add_suffix(self.tempo)

        self.brightness = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 0, 100, 1
        )
        self.brightness.set_value(self.backend.settings.brightness)
        self.brightness.set_size_request(220, -1)
        self.brightness.set_hexpand(True)
        self.brightness.set_draw_value(True)
        self.brightness.set_value_pos(Gtk.PositionType.RIGHT)
        brightness_row = Adw.ActionRow(
            title="Brightness", subtitle="Global AW-ELC dimness"
        )
        brightness_row.add_suffix(self.brightness)
        lighting_group.add(brightness_row)

        apply_row = Adw.ActionRow(
            title="Apply lighting",
            subtitle="Save the selected color and brightness to the controller",
        )
        apply_button = Gtk.Button(label="Apply")
        apply_button.add_css_class("suggested-action")
        apply_button.set_valign(Gtk.Align.CENTER)
        apply_button.connect("clicked", self._apply)
        apply_row.add_suffix(apply_button)
        apply_row.set_activatable_widget(apply_button)
        lighting_group.add(apply_row)
        page.add(lighting_group)

        advanced_group = Adw.PreferencesGroup(title="Additional options")
        self.animation_timing = Adw.ExpanderRow(
            title="Animation timing",
            subtitle="Duration and flash rate",
        )
        self.animation_timing.add_row(self.duration_row)
        self.animation_timing.add_row(self.tempo_row)
        advanced_group.add(self.animation_timing)

        self.brightness_behavior = Adw.ExpanderRow(
            title="Brightness behavior",
        )
        self.brightness_behavior.add_row(self.brightness_method_row)
        advanced_group.add(self.brightness_behavior)
        page.add(advanced_group)

        device_group = Adw.PreferencesGroup(title="Device")
        info = self.backend.info
        device_details = Adw.ExpanderRow(
            title=info.name,
            subtitle="Controller and firmware details",
        )
        device_details.add_row(self._value_row("Controller", info.controller))
        device_details.add_row(self._value_row("Firmware", info.firmware))
        device_details.add_row(self._value_row("Platform", info.platform))
        device_details.add_row(self._value_row("Lighting zones", str(info.zones)))
        device_group.add(device_details)
        page.add(device_group)

        self.effect.connect("notify::selected", self._effect_changed)
        self.brightness_method.connect(
            "notify::selected", self._brightness_method_changed
        )
        self.power_source.connect("notify::active-name", self._power_source_changed)
        self.ac_state.connect("notify::active-name", self._power_state_changed)
        self.battery_state.connect("notify::active-name", self._power_state_changed)
        self.profile_mode.connect("notify::active", self._profile_mode_changed)
        self._profile_mode_changed()
        self._effect_changed()
        self._refresh_service_status()
        self._service_status_timer = GLib.timeout_add_seconds(
            2, self._refresh_service_status
        )
        return page

    @staticmethod
    def _toggle_group(items):
        group = Adw.ToggleGroup()
        group.set_hexpand(True)
        for name, label in items:
            group.add(Adw.Toggle(name=name, label=label))
        return group

    @staticmethod
    def _value_row(title, value):
        row = Adw.ActionRow(title=title)
        label = Gtk.Label(label=value)
        label.add_css_class("dim-label")
        label.set_selectable(True)
        label.set_valign(Gtk.Align.CENTER)
        row.add_suffix(label)
        return row

    def _apply(self, _button):
        rgba = self.color.get_rgba()
        color = tuple(
            round(channel * 255) for channel in (rgba.red, rgba.green, rgba.blue)
        )
        selected_effect = self.effects[self.effect.get_selected()]
        settings = LightingSettings(
            enabled=self.enabled.get_active(),
            effect=selected_effect,
            primary_color=color,
            brightness=round(self.brightness.get_value()),
            additional_colors=(
                tuple(self._button_color(button) for button in self.additional_color_buttons)
                if selected_effect is LightingEffect.MORPH
                else ()
            ),
            duration=(
                round(self.duration.get_value())
                if selected_effect
                in {
                    LightingEffect.PULSE,
                    LightingEffect.MORPH,
                    LightingEffect.BREATHING,
                    LightingEffect.RAINBOW,
                }
                else None
            ),
            tempo=(
                round(self.tempo.get_value())
                if selected_effect is LightingEffect.PULSE
                else None
            ),
        )
        power_state = self._selected_power_state()
        brightness_mode = self.brightness_modes[
            self.brightness_method.get_selected()
        ]
        separate_power_profiles = self.profile_mode.get_active()
        if separate_power_profiles:
            self.backend.apply_power_state(power_state, settings, brightness_mode)
            self.profiles[power_state] = settings
        else:
            unified = unified_power_profiles(settings)
            for state, profile_settings in unified.items():
                self.backend.apply_power_state(
                    state, profile_settings, brightness_mode
                )
                self.profiles[state] = profile_settings
        if self.settings_store is not None:
            self.settings_store.save_profiles(
                self.profiles,
                brightness_mode,
                separate_power_profiles,
            )
        self.toast_overlay.add_toast(Adw.Toast(title="Lighting settings applied"))

    def _effect_changed(self, *_args):
        is_morph = self.effects[self.effect.get_selected()] is LightingEffect.MORPH
        is_animated = self.effects[self.effect.get_selected()] in {
            LightingEffect.PULSE,
            LightingEffect.MORPH,
            LightingEffect.BREATHING,
            LightingEffect.RAINBOW,
        }
        self.morph_colors.set_visible(is_morph)
        self.color_row.set_visible(
            self.effects[self.effect.get_selected()] is not LightingEffect.RAINBOW
        )
        self.duration_row.set_visible(is_animated)
        self.tempo_row.set_visible(
            self.effects[self.effect.get_selected()] is LightingEffect.PULSE
        )
        self.animation_timing.set_visible(is_animated)

    def _add_color_clicked(self, _button):
        if len(self.additional_color_buttons) >= 11:
            return
        self.morph_colors.remove(self.add_color_row)
        self._add_morph_color((255, 255, 255))
        self.morph_colors.add_row(self.add_color_row)

    def _add_morph_color(self, color):
        button = Gtk.ColorDialogButton(
            dialog=Gtk.ColorDialog(title="Morph target color")
        )
        self._set_color(button, color)
        row = Adw.ActionRow()
        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        up = Gtk.Button(icon_name="go-up-symbolic")
        up.set_tooltip_text("Move color earlier")
        down = Gtk.Button(icon_name="go-down-symbolic")
        down.set_tooltip_text("Move color later")
        remove = Gtk.Button(icon_name="user-trash-symbolic")
        remove.set_tooltip_text("Remove color")
        up.connect("clicked", lambda _button: self._move_morph_color(button, -1))
        down.connect("clicked", lambda _button: self._move_morph_color(button, 1))
        remove.connect("clicked", lambda _button: self._remove_morph_color(button))
        controls.append(button)
        controls.append(up)
        controls.append(down)
        controls.append(remove)
        row.add_suffix(controls)
        self.additional_color_rows.append(row)
        self.additional_color_buttons.append(button)
        self.morph_colors.add_row(row)
        self._update_morph_color_rows()

    def _remove_morph_color(self, button):
        if len(self.additional_color_buttons) <= 1:
            return
        index = self.additional_color_buttons.index(button)
        self.morph_colors.remove(self.additional_color_rows[index])
        self.additional_color_rows.pop(index)
        self.additional_color_buttons.pop(index)
        self._update_morph_color_rows()

    def _move_morph_color(self, button, offset):
        buttons = [self.color, *self.additional_color_buttons]
        index = buttons.index(button)
        target = index + offset
        if not 0 <= target < len(buttons):
            return
        first = self._button_color(buttons[index])
        second = self._button_color(buttons[target])
        self._set_color(buttons[index], second)
        self._set_color(buttons[target], first)

    def _set_morph_colors(self, colors):
        self.morph_colors.remove(self.add_color_row)
        for row in self.additional_color_rows:
            self.morph_colors.remove(row)
        self.additional_color_rows.clear()
        self.additional_color_buttons.clear()
        for color in colors:
            self._add_morph_color(color)
        self.morph_colors.add_row(self.add_color_row)

    def _update_morph_color_rows(self):
        total = len(self.additional_color_rows) + 1
        for index, row in enumerate(self.additional_color_rows, start=2):
            row.set_title(f"Color {index}")
        self.morph_colors.set_subtitle(f"{total} transition colors")
        self.add_color_button.set_sensitive(total < 12)

    @staticmethod
    def _button_color(button):
        rgba = button.get_rgba()
        return tuple(
            round(channel * 255) for channel in (rgba.red, rgba.green, rgba.blue)
        )

    def _brightness_method_changed(self, *_args):
        self._refresh_service_status()

    def _refresh_service_status(self):
        exact = (
            self.brightness_modes[self.brightness_method.get_selected()]
            is BrightnessMode.EXACT_SERVICE
        )
        if not exact:
            subtitle = "Stored in hardware; works without a user service"
        elif service_is_running():
            subtitle = "Exact brightness service is running"
        else:
            subtitle = "Exact brightness service is not running"
        self.brightness_behavior.set_subtitle(subtitle)
        return GLib.SOURCE_CONTINUE

    def _power_source_changed(self, *_args):
        on_ac = self.power_source.get_active_name() == "ac"
        self.ac_state.set_visible(on_ac)
        self.battery_state.set_visible(not on_ac)
        self._power_state_changed()

    def _profile_mode_changed(self, *_args):
        separate = self.profile_mode.get_active()
        self.profile_box.set_visible(separate)
        if separate:
            subtitle = "Use separate lighting for AC, battery, and sleep states"
        else:
            subtitle = "Use the same lighting while awake; turn it off during sleep"
        self.profile_mode.set_subtitle(subtitle)

    def _selected_power_state(self):
        if self.power_source.get_active_name() == "ac":
            return {
                "charged": PowerState.AC_CHARGED,
                "charging": PowerState.AC_CHARGING,
                "sleep": PowerState.AC_SLEEP,
            }[self.ac_state.get_active_name()]
        return {
            "normal": PowerState.BATTERY_ON,
            "low": PowerState.BATTERY_LOW,
            "sleep": PowerState.BATTERY_SLEEP,
        }[self.battery_state.get_active_name()]

    def _power_state_changed(self, *_args):
        state = self._selected_power_state()
        settings = self.profiles[state]
        self.enabled.set_active(settings.enabled)
        self.effect.set_selected(
            self.effects.index(settings.effect)
            if settings.effect in self.effects
            else 0
        )
        self._set_color(self.color, settings.primary_color)
        self._set_morph_colors(settings.colors[1:] or ((0, 0, 255),))
        self.brightness.set_value(settings.brightness)
        self.duration.set_value(settings.duration or 500)
        self.tempo.set_value(settings.tempo or 100)
        self._effect_changed()

    @staticmethod
    def _set_color(button, color):
        rgba = Gdk.RGBA()
        rgba.red, rgba.green, rgba.blue = (channel / 255 for channel in color)
        rgba.alpha = 1.0
        button.set_rgba(rgba)

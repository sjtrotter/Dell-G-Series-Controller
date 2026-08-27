import math
import threading
import time

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw, Gdk, GLib, GObject, Gtk

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
            self.profiles = {}
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
        self.set_default_size(460, 280)
        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(Adw.HeaderBar())
        status = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        status.set_halign(Gtk.Align.CENTER)
        status.set_valign(Gtk.Align.CENTER)
        status.append(LightingKeyboard())
        title = Gtk.Label(label="Dell G-Series Keyboard")
        title.add_css_class("title-1")
        status.append(title)
        unofficial = Gtk.Label(label="Unofficial community utility")
        unofficial.add_css_class("dim-label")
        status.append(unofficial)
        toolbar_view.set_content(status)
        self.set_content(toolbar_view)


class LightingKeyboard(Gtk.DrawingArea):
    """Decorative keyboard with a subtle traveling backlight animation."""

    ROW_LENGTHS = (10, 10, 9, 7)

    def __init__(self):
        super().__init__()
        self.set_content_width(184)
        self.set_content_height(72)
        self.set_size_request(184, 72)
        self.set_draw_func(self._draw)
        self.add_tick_callback(self._animate)

    def _animate(self, _widget, _frame_clock):
        self.queue_draw()
        return GLib.SOURCE_CONTINUE

    @classmethod
    def _draw(cls, _area, context, width, height):
        now = time.monotonic()
        scale = min(width / 184, height / 72)
        context.save()
        context.translate((width - 184 * scale) / 2, (height - 72 * scale) / 2)
        context.scale(scale, scale)

        context.set_line_width(2)
        context.set_source_rgba(1, 1, 1, 0.55)
        context.rectangle(1, 1, 182, 70)
        context.stroke()

        key_index = 0
        for row, columns in enumerate(cls.ROW_LENGTHS):
            key_width = 14
            gap = 3
            row_width = columns * key_width + (columns - 1) * gap
            start_x = (184 - row_width) / 2
            y = 9 + row * 14
            for column in range(columns):
                phase = now * 2.4 - key_index * 0.32
                glow = max(0.0, math.sin(phase)) ** 2
                context.set_source_rgba(
                    0.21,
                    0.52,
                    0.89,
                    0.16 + 0.78 * glow,
                )
                context.rectangle(start_x + column * 17, y, key_width, 9)
                context.fill()
                key_index += 1
        context.restore()


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, application, backend, settings_store=None):
        super().__init__(application=application)
        self.backend = backend
        self.settings_store = settings_store
        self.profiles = application.profiles
        self.brightness_mode = application.brightness_mode
        self.separate_power_profiles = application.separate_power_profiles
        self._updating_controls = True
        self._apply_in_progress = False
        self._edit_generation = 0
        self.set_title("Dell G-Series Laptop Keyboard Controller")
        self.set_default_size(620, 640)
        self.color_panel_css = Gtk.CssProvider()
        self.color_panel_css.load_from_string(
            ".color-index { color: white; font-weight: 700; "
            "text-shadow: 0 1px 2px rgba(0, 0, 0, 0.95); }"
        )
        Gtk.StyleContext.add_provider_for_display(
            self.get_display(),
            self.color_panel_css,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        self.toast_overlay = Adw.ToastOverlay()
        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(Adw.HeaderBar())
        toolbar_view.set_content(self._build_page())
        toolbar_view.add_bottom_bar(self._build_action_bar())
        self.toast_overlay.set_child(toolbar_view)
        self.set_content(self.toast_overlay)
        self._updating_controls = False
        self._set_dirty(False)

    def _build_action_bar(self):
        action_bar = Gtk.ActionBar()
        action_bar.add_css_class("view")
        if self.settings_store is not None:
            configurations = Gtk.MenuButton()
            self.configurations_menu = configurations
            configurations.set_label("Configurations")
            configurations.set_always_show_arrow(True)
            configurations.set_popover(self._build_configurations_popover())
            action_bar.pack_start(configurations)
            self.save_configuration_button = Gtk.Button(label="Save New")
            self.save_configuration_button.set_tooltip_text(
                "Save the current settings as a new configuration"
            )
            self.save_configuration_button.connect(
                "clicked", self._show_save_configuration_dialog
            )
            action_bar.pack_start(self.save_configuration_button)
        self.apply_button = Gtk.Button(label="Apply")
        self.apply_button.add_css_class("suggested-action")
        self.apply_button.set_tooltip_text(
            "Save the current lighting settings to the keyboard"
        )
        self.apply_button.connect("clicked", self._apply)
        action_bar.pack_end(self.apply_button)
        return action_bar

    def _build_configurations_popover(self):
        popover = Gtk.Popover()
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(12)
        content.set_margin_end(12)

        title = Gtk.Label(label="Saved configurations", xalign=0)
        title.add_css_class("heading")
        content.append(title)
        self.configurations_list = Gtk.ListBox()
        self.configurations_list.add_css_class("boxed-list")
        self.configurations_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self.configurations_list.connect(
            "row-activated", self._configuration_activated
        )
        content.append(self.configurations_list)
        popover.set_child(content)
        self._refresh_saved_configurations()
        return popover

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
        self.color_panel_row = Adw.PreferencesRow()
        color_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        color_panel.set_margin_top(12)
        color_panel.set_margin_bottom(12)
        color_panel.set_margin_start(12)
        color_panel.set_margin_end(12)
        self.color_panel_title = Gtk.Label(label="Color", xalign=0)
        self.color_panel_title.add_css_class("heading")
        color_panel.append(self.color_panel_title)
        self.color_panel_subtitle = Gtk.Label(
            label="Static keyboard color", xalign=0
        )
        self.color_panel_subtitle.add_css_class("dim-label")
        color_panel.append(self.color_panel_subtitle)
        self.color_flow = Gtk.FlowBox()
        self.color_flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self.color_flow.set_halign(Gtk.Align.START)
        self.color_flow.set_homogeneous(False)
        self.color_flow.set_column_spacing(8)
        self.color_flow.set_row_spacing(8)
        self.color_flow.set_max_children_per_line(7)
        color_panel.append(self.color_flow)
        self.color_panel_row.set_child(color_panel)
        lighting_group.add(self.color_panel_row)

        self.additional_color_buttons = []
        self.add_color_button = Gtk.Button(icon_name="list-add-symbolic")
        self.add_color_button.set_size_request(40, 40)
        self.add_color_button.set_halign(Gtk.Align.START)
        self.add_color_button.set_hexpand(False)
        self.add_color_button.set_tooltip_text("Add another color")
        self.add_color_button.connect("clicked", self._add_color_clicked)
        initial_colors = self.backend.settings.colors[1:]
        for color in initial_colors:
            self._add_morph_color(color)
        self._refresh_color_panel()

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
        self.effect.connect("notify::selected", self._control_changed)
        self.brightness_method.connect(
            "notify::selected", self._brightness_method_changed
        )
        self.enabled.connect("notify::active", self._control_changed)
        self.color.connect("notify::rgba", self._control_changed)
        self.duration.connect("value-changed", self._control_changed)
        self.tempo.connect("value-changed", self._control_changed)
        self.brightness.connect("value-changed", self._control_changed)
        self.power_source.connect("notify::active-name", self._power_source_changed)
        self.ac_state.connect("notify::active-name", self._power_state_changed)
        self.battery_state.connect("notify::active-name", self._power_state_changed)
        self.profile_mode.connect("notify::active", self._profile_mode_changed)
        self.profile_mode.connect("notify::active", self._control_changed)
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
        if self._apply_in_progress:
            return
        settings = self._settings_from_controls()
        power_state = self._selected_power_state()
        brightness_mode = self.brightness_modes[
            self.brightness_method.get_selected()
        ]
        separate_power_profiles = self.profile_mode.get_active()
        profiles = dict(self.profiles)
        if separate_power_profiles:
            operations = ((power_state, settings),)
            profiles[power_state] = settings
        else:
            unified = unified_power_profiles(settings)
            operations = tuple(unified.items())
            profiles.update(unified)
        generation = self._edit_generation
        self._set_apply_in_progress(True)

        def apply_in_background():
            try:
                for state, profile_settings in operations:
                    self.backend.apply_power_state(
                        state, profile_settings, brightness_mode
                    )
                if self.settings_store is not None:
                    self.settings_store.save_profiles(
                        profiles,
                        brightness_mode,
                        separate_power_profiles,
                    )
            except Exception as error:
                GLib.idle_add(self._apply_failed, str(error))
                return
            GLib.idle_add(
                self._apply_finished,
                profiles,
                brightness_mode,
                separate_power_profiles,
                generation,
            )

        threading.Thread(target=apply_in_background, daemon=True).start()

    def _set_apply_in_progress(self, in_progress):
        self._apply_in_progress = in_progress
        self.apply_button.set_label("Applying…" if in_progress else "Apply")
        self.apply_button.set_sensitive(self.dirty and not in_progress)
        if self.settings_store is not None:
            self.configurations_menu.set_sensitive(not in_progress)
            self.save_configuration_button.set_sensitive(not in_progress)

    def _apply_finished(
        self,
        profiles,
        brightness_mode,
        separate_power_profiles,
        generation,
    ):
        self.profiles = profiles
        self.brightness_mode = brightness_mode
        self.separate_power_profiles = separate_power_profiles
        self._set_apply_in_progress(False)
        if self._edit_generation == generation:
            self._set_dirty(False)
        self.toast_overlay.add_toast(Adw.Toast(title="Lighting settings applied"))
        return GLib.SOURCE_REMOVE

    def _apply_failed(self, message):
        self._set_apply_in_progress(False)
        self._set_dirty(True)
        self.toast_overlay.add_toast(
            Adw.Toast(title=f"Could not apply lighting: {message}")
        )
        return GLib.SOURCE_REMOVE

    def _control_changed(self, *_args):
        if not self._updating_controls:
            self._edit_generation += 1
            self._set_dirty(True)

    def _set_dirty(self, dirty):
        self.dirty = dirty
        if hasattr(self, "apply_button"):
            self.apply_button.set_sensitive(
                dirty and not self._apply_in_progress
            )

    def _settings_from_controls(self):
        rgba = self.color.get_rgba()
        color = tuple(
            round(channel * 255) for channel in (rgba.red, rgba.green, rgba.blue)
        )
        selected_effect = self.effects[self.effect.get_selected()]
        return LightingSettings(
            enabled=self.enabled.get_active(),
            effect=selected_effect,
            primary_color=color,
            brightness=round(self.brightness.get_value()),
            additional_colors=(
                tuple(self._button_color(button) for button in self.additional_color_buttons)
                if selected_effect in {LightingEffect.MORPH, LightingEffect.BREATHING}
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

    def _profiles_with_current_edits(self):
        profiles = dict(self.profiles)
        settings = self._settings_from_controls()
        if self.profile_mode.get_active():
            profiles[self._selected_power_state()] = settings
        else:
            profiles.update(unified_power_profiles(settings))
        return profiles

    def _refresh_saved_configurations(self):
        self.saved_configuration_names = list(
            self.settings_store.list_saved_configurations()
        )
        while child := self.configurations_list.get_first_child():
            self.configurations_list.remove(child)
        if not self.saved_configuration_names:
            empty = Gtk.Label(label="No saved configurations")
            empty.add_css_class("dim-label")
            empty.set_margin_top(12)
            empty.set_margin_bottom(12)
            self.configurations_list.append(empty)
            return
        for name in self.saved_configuration_names:
            row = Gtk.ListBoxRow()
            row.configuration_name = name
            contents = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL,
                spacing=12,
            )
            contents.set_margin_top(6)
            contents.set_margin_bottom(6)
            contents.set_margin_start(12)
            contents.set_margin_end(6)
            label = Gtk.Label(label=name, xalign=0)
            label.set_hexpand(True)
            delete = Gtk.Button(icon_name="user-trash-symbolic")
            delete.add_css_class("flat")
            delete.set_tooltip_text(f'Delete “{name}”')
            delete.connect(
                "clicked",
                lambda _button, saved_name=name: self._confirm_delete_configuration(
                    saved_name
                ),
            )
            contents.append(label)
            contents.append(delete)
            row.set_child(contents)
            self.configurations_list.append(row)

    def _show_save_configuration_dialog(self, _button):
        dialog = Adw.AlertDialog(
            heading="Save Configuration",
            body="Name this complete set of keyboard profiles.",
        )
        entry = Gtk.Entry(placeholder_text="Configuration name")
        entry.set_activates_default(True)
        dialog.set_extra_child(entry)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("save", "Save")
        dialog.set_default_response("save")
        dialog.set_close_response("cancel")
        dialog.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)
        dialog.connect(
            "response", self._save_configuration_response, entry
        )
        dialog.present(self)

    def _save_configuration_response(self, _dialog, response, entry):
        if response != "save":
            return
        name = entry.get_text().strip()
        try:
            self.settings_store.save_configuration(
                name,
                self._profiles_with_current_edits(),
                self.brightness_modes[self.brightness_method.get_selected()],
                self.profile_mode.get_active(),
            )
        except ValueError as error:
            self.toast_overlay.add_toast(Adw.Toast(title=str(error)))
            return
        self._refresh_saved_configurations()
        self.toast_overlay.add_toast(
            Adw.Toast(title=f'Saved configuration “{name}”')
        )

    def _configuration_activated(self, _list_box, row):
        name = getattr(row, "configuration_name", None)
        if name is not None:
            self._load_configuration(name)
            self.configurations_menu.popdown()

    def _load_configuration(self, name):
        profiles, brightness_mode, separate = (
            self.settings_store.load_configuration(name)
        )
        self._updating_controls = True
        self.profiles = profiles
        self.brightness_mode = brightness_mode
        self.separate_power_profiles = separate
        self.profile_mode.set_active(separate)
        self.brightness_method.set_selected(
            self.brightness_modes.index(brightness_mode)
        )
        self._power_state_changed()
        self._updating_controls = False
        self._edit_generation += 1
        self._set_dirty(True)
        self.toast_overlay.add_toast(
            Adw.Toast(title=f'Loaded “{name}”; press Apply to use it')
        )

    def _confirm_delete_configuration(self, name):
        dialog = Adw.AlertDialog(
            heading="Delete Configuration?",
            body=f'“{name}” will be permanently removed.',
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("delete", "Delete")
        dialog.set_close_response("cancel")
        dialog.set_response_appearance(
            "delete", Adw.ResponseAppearance.DESTRUCTIVE
        )
        dialog.connect(
            "response", self._delete_configuration_response, name
        )
        dialog.present(self)

    def _delete_configuration_response(self, _dialog, response, name):
        if response != "delete":
            return
        self.settings_store.delete_configuration(name)
        self._refresh_saved_configurations()
        self.toast_overlay.add_toast(
            Adw.Toast(title=f'Deleted configuration “{name}”')
        )

    def _effect_changed(self, *_args):
        selected_effect = self.effects[self.effect.get_selected()]
        is_morph = selected_effect is LightingEffect.MORPH
        is_breathing = selected_effect is LightingEffect.BREATHING
        if is_morph and not self.additional_color_buttons:
            self._add_morph_color((0, 0, 255))
        self._refresh_color_panel()
        is_animated = selected_effect in {
            LightingEffect.PULSE,
            LightingEffect.MORPH,
            LightingEffect.BREATHING,
            LightingEffect.RAINBOW,
        }
        self.color_panel_row.set_visible(
            self.effects[self.effect.get_selected()] is not LightingEffect.RAINBOW
        )
        self.duration_row.set_visible(is_animated)
        self.tempo_row.set_visible(
            self.effects[self.effect.get_selected()] is LightingEffect.PULSE
        )
        self.animation_timing.set_visible(is_animated)

    def _add_color_clicked(self, _button):
        selected_effect = self.effects[self.effect.get_selected()]
        maximum = 6 if selected_effect is LightingEffect.BREATHING else 12
        if len(self.additional_color_buttons) + 1 >= maximum:
            return
        self._add_morph_color((255, 255, 255))
        self._refresh_color_panel()
        self._control_changed()

    def _add_morph_color(self, color):
        button = Gtk.ColorDialogButton(
            dialog=Gtk.ColorDialog(title="Animation color")
        )
        self._set_color(button, color)
        self.additional_color_buttons.append(button)
        button.connect("notify::rgba", self._control_changed)

    def _remove_morph_color(self, button):
        is_morph = self.effects[self.effect.get_selected()] is LightingEffect.MORPH
        if is_morph and len(self.additional_color_buttons) <= 1:
            return
        index = self.additional_color_buttons.index(button)
        self.additional_color_buttons.pop(index)
        self._refresh_color_panel()
        self._control_changed()

    def _prepare_color_drag(self, _source, _x, _y, button):
        buttons = [self.color, *self.additional_color_buttons]
        return Gdk.ContentProvider.new_for_value(str(buttons.index(button)))

    def _drop_color(self, _target, value, _x, _y, target_button):
        buttons = [self.color, *self.additional_color_buttons]
        try:
            source_index = int(value)
            target_index = buttons.index(target_button)
            colors = [self._button_color(button) for button in buttons]
            moved = colors.pop(source_index)
        except (ValueError, IndexError):
            return False
        if source_index < target_index:
            target_index -= 1
        colors.insert(target_index, moved)
        for button, color in zip(buttons, colors, strict=True):
            self._set_color(button, color)
        self._control_changed()
        return True

    def _set_morph_colors(self, colors):
        self.additional_color_buttons.clear()
        for color in colors:
            self._add_morph_color(color)
        self._refresh_color_panel()

    def _refresh_color_panel(self):
        while child := self.color_flow.get_first_child():
            self.color_flow.remove(child)
        effect = self.effects[self.effect.get_selected()]
        multicolor = effect in {LightingEffect.MORPH, LightingEffect.BREATHING}
        buttons = [self.color, *self.additional_color_buttons] if multicolor else [self.color]
        for index, button in enumerate(buttons, start=1):
            tile = Gtk.Overlay()
            tile.set_size_request(40, 40)
            tile.set_halign(Gtk.Align.START)
            tile.set_hexpand(False)
            button.set_size_request(40, 40)
            button.set_halign(Gtk.Align.FILL)
            button.set_hexpand(False)
            tile.set_child(button)
            number = Gtk.Label(label=str(index))
            number.set_can_target(False)
            number.add_css_class("color-index")
            tile.add_overlay(number)
            if index > 1:
                remove = Gtk.Button(icon_name="window-close-symbolic")
                remove.add_css_class("flat")
                remove.set_halign(Gtk.Align.END)
                remove.set_valign(Gtk.Align.START)
                remove.set_tooltip_text(f"Remove color {index}")
                remove.connect(
                    "clicked",
                    lambda _remove, color_button=button: self._remove_morph_color(
                        color_button
                    ),
                )
                tile.add_overlay(remove)
            drag = Gtk.DragSource(actions=Gdk.DragAction.MOVE)
            drag.connect("prepare", self._prepare_color_drag, button)
            tile.add_controller(drag)
            drop = Gtk.DropTarget.new(GObject.TYPE_STRING, Gdk.DragAction.MOVE)
            drop.connect("drop", self._drop_color, button)
            tile.add_controller(drop)
            self.color_flow.append(tile)
        total = len(buttons)
        if effect is LightingEffect.MORPH:
            title = "Morph colors"
            subtitle = f"{total} transition colors · drag to reorder"
        elif effect is LightingEffect.BREATHING:
            title = "Breathing colors"
            subtitle = f"{total} colors separated by darkness · drag to reorder"
        else:
            title = "Color"
            subtitle = "Keyboard color"
        self.color_panel_title.set_label(title)
        self.color_panel_subtitle.set_label(subtitle)
        maximum = 6 if effect is LightingEffect.BREATHING else 12
        self.add_color_button.set_sensitive(total < maximum)
        if multicolor:
            self.color_flow.append(self.add_color_button)

    @staticmethod
    def _button_color(button):
        rgba = button.get_rgba()
        return tuple(
            round(channel * 255) for channel in (rgba.red, rgba.green, rgba.blue)
        )

    def _brightness_method_changed(self, *_args):
        self._refresh_service_status()
        self._control_changed()

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
        was_updating = self._updating_controls
        self._updating_controls = True
        state = self._selected_power_state()
        settings = self.profiles[state]
        self.enabled.set_active(settings.enabled)
        self.effect.set_selected(
            self.effects.index(settings.effect)
            if settings.effect in self.effects
            else 0
        )
        self._set_color(self.color, settings.primary_color)
        self._set_morph_colors(settings.colors[1:])
        self.brightness.set_value(settings.brightness)
        self.duration.set_value(settings.duration or 500)
        self.tempo.set_value(settings.tempo or 100)
        self._effect_changed()
        self._updating_controls = was_updating

    @staticmethod
    def _set_color(button, color):
        rgba = Gdk.RGBA()
        rgba.red, rgba.green, rgba.blue = (channel / 255 for channel in color)
        rgba.alpha = 1.0
        button.set_rgba(rgba)

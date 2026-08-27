import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw, Gdk, GLib, Gtk

from .backend import BrightnessMode, LightingEffect, LightingSettings, PowerState
from .service_status import service_is_running


class Application(Adw.Application):
    def __init__(self, backend, settings_store=None):
        super().__init__(application_id="io.github.cemkaya_mpi.DellGSeriesController")
        self.backend = backend
        self.settings_store = settings_store
        if settings_store is not None:
            self.profiles = settings_store.load_profiles()
            self.brightness_mode = settings_store.load_brightness_mode()
        else:
            self.profiles = {state: backend.settings for state in PowerState}
            self.brightness_mode = BrightnessMode.HARDWARE_SCALING
        self.connect("activate", self.on_activate)

    def on_activate(self, _application):
        window = self.props.active_window
        if window is None:
            window = MainWindow(self, self.backend, self.settings_store)
        window.present()


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, application, backend, settings_store=None):
        super().__init__(application=application)
        self.backend = backend
        self.settings_store = settings_store
        self.set_title("Dell G-Series Laptop Keyboard Controller")
        self.set_default_size(620, 700)

        self.toast_overlay = Adw.ToastOverlay()
        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(Adw.HeaderBar())
        toolbar_view.set_content(self._build_page())
        self.toast_overlay.set_child(toolbar_view)
        self.set_content(self.toast_overlay)

    def _build_page(self):
        page = Adw.PreferencesPage()

        device_group = Adw.PreferencesGroup(title="Device")
        device_group.set_description("Connected lighting controller")
        info = self.backend.info
        device_group.add(self._value_row("Model", info.name))
        device_group.add(self._value_row("Controller", info.controller))
        device_group.add(
            self._value_row(
                "Firmware",
                f"{info.firmware}  ·  Platform {info.platform}  ·  {info.zones} zone",
            )
        )
        page.add(device_group)

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

        self.power_states = list(PowerState)
        self.power_state = Gtk.DropDown.new_from_strings(
            [state.label for state in self.power_states]
        )
        self.power_state.set_selected(self.power_states.index(PowerState.AC_CHARGED))
        power_state_row = Adw.ActionRow(
            title="Profile", subtitle="AC, battery, sleep, or low-battery behavior"
        )
        power_state_row.add_suffix(self.power_state)
        power_state_row.set_activatable_widget(self.power_state)
        lighting_group.add(power_state_row)

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
        self.brightness_method_row = Adw.ActionRow(
            title="Profile brightness",
        )
        self.brightness_method_row.add_suffix(self.brightness_method)
        self.brightness_method_row.set_activatable_widget(self.brightness_method)
        lighting_group.add(self.brightness_method_row)
        self.brightness_method.connect(
            "notify::selected", self._brightness_method_changed
        )
        self._refresh_service_status()
        self._service_status_timer = GLib.timeout_add_seconds(
            2, self._refresh_service_status
        )

        self.enabled = Adw.SwitchRow(title="Lighting enabled")
        self.enabled.set_active(self.backend.settings.enabled)
        lighting_group.add(self.enabled)

        self.effects = [LightingEffect.STATIC]
        if LightingEffect.PULSE in self.backend.capabilities.effects:
            self.effects.append(LightingEffect.PULSE)
        if LightingEffect.MORPH in self.backend.capabilities.effects:
            self.effects.append(LightingEffect.MORPH)
        self.effect = Gtk.DropDown.new_from_strings(
            [
                {
                    LightingEffect.STATIC: "Static",
                    LightingEffect.PULSE: "Flash (firmware Pulse)",
                    LightingEffect.MORPH: "Morph",
                }[effect]
                for effect in self.effects
            ]
        )
        try:
            selected_effect = self.effects.index(self.backend.settings.effect)
        except ValueError:
            selected_effect = 0
        self.effect.set_selected(selected_effect)
        self.effect.connect("notify::selected", self._effect_changed)
        effect_row = Adw.ActionRow(
            title="Effect", subtitle="Static, flashing pulse, or smooth morph"
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
        color_row.add_suffix(self.color)
        color_row.set_activatable_widget(self.color)
        lighting_group.add(color_row)

        self.secondary_color = Gtk.ColorDialogButton(
            dialog=Gtk.ColorDialog(title="Second keyboard color")
        )
        secondary = self.backend.settings.secondary_color or (0, 0, 255)
        secondary_rgba = Gdk.RGBA()
        secondary_rgba.red, secondary_rgba.green, secondary_rgba.blue = (
            channel / 255 for channel in secondary
        )
        secondary_rgba.alpha = 1.0
        self.secondary_color.set_rgba(secondary_rgba)
        self.secondary_color_row = Adw.ActionRow(
            title="Second color", subtitle="Alternate morph target"
        )
        self.secondary_color_row.add_suffix(self.secondary_color)
        self.secondary_color_row.set_activatable_widget(self.secondary_color)
        lighting_group.add(self.secondary_color_row)

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
        lighting_group.add(self.duration_row)

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
        lighting_group.add(self.tempo_row)
        self._effect_changed()
        self.power_state.connect("notify::selected", self._power_state_changed)

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

        system_group = Adw.PreferencesGroup(title="Performance and fans")
        system_group.set_description(
            "Unavailable in demo mode. Privileged controls will use a scoped helper."
        )
        unavailable = Adw.ActionRow(
            title="System controls",
            subtitle="No privileged helper is connected",
        )
        unavailable.set_sensitive(False)
        system_group.add(unavailable)
        page.add(system_group)
        return page

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
        secondary_rgba = self.secondary_color.get_rgba()
        secondary_color = tuple(
            round(channel * 255)
            for channel in (
                secondary_rgba.red,
                secondary_rgba.green,
                secondary_rgba.blue,
            )
        )
        settings = LightingSettings(
            enabled=self.enabled.get_active(),
            effect=selected_effect,
            primary_color=color,
            brightness=round(self.brightness.get_value()),
            secondary_color=(
                secondary_color if selected_effect is LightingEffect.MORPH else None
            ),
            duration=(
                round(self.duration.get_value())
                if selected_effect in {LightingEffect.PULSE, LightingEffect.MORPH}
                else None
            ),
            tempo=(
                round(self.tempo.get_value())
                if selected_effect is LightingEffect.PULSE
                else None
            ),
        )
        power_state = self.power_states[self.power_state.get_selected()]
        brightness_mode = self.brightness_modes[
            self.brightness_method.get_selected()
        ]
        self.backend.apply_power_state(power_state, settings, brightness_mode)
        self.profiles[power_state] = settings
        if self.settings_store is not None:
            self.settings_store.save_profiles(self.profiles, brightness_mode)
        self.toast_overlay.add_toast(Adw.Toast(title="Lighting settings applied"))

    def _effect_changed(self, *_args):
        is_morph = self.effects[self.effect.get_selected()] is LightingEffect.MORPH
        is_animated = self.effects[self.effect.get_selected()] in {
            LightingEffect.PULSE,
            LightingEffect.MORPH,
        }
        self.secondary_color_row.set_visible(is_morph)
        self.duration_row.set_visible(is_animated)
        self.tempo_row.set_visible(
            self.effects[self.effect.get_selected()] is LightingEffect.PULSE
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
        self.brightness_method_row.set_subtitle(subtitle)
        return GLib.SOURCE_CONTINUE

    def _power_state_changed(self, *_args):
        state = self.power_states[self.power_state.get_selected()]
        settings = self.profiles[state]
        self.enabled.set_active(settings.enabled)
        self.effect.set_selected(
            self.effects.index(settings.effect)
            if settings.effect in self.effects
            else 0
        )
        self._set_color(self.color, settings.primary_color)
        self._set_color(
            self.secondary_color, settings.secondary_color or (0, 0, 255)
        )
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

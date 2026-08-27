import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw, Gdk, Gtk

from .backend import LightingEffect, LightingSettings


class Application(Adw.Application):
    def __init__(self, backend, settings_store=None):
        super().__init__(application_id="io.github.cemkaya_mpi.DellGSeriesController")
        self.backend = backend
        self.settings_store = settings_store
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
        self.set_title("Dell G Series Controller")
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

        self.enabled = Adw.SwitchRow(title="Lighting enabled")
        self.enabled.set_active(self.backend.settings.enabled)
        lighting_group.add(self.enabled)

        self.effects = [LightingEffect.STATIC]
        if LightingEffect.MORPH in self.backend.capabilities.effects:
            self.effects.append(LightingEffect.MORPH)
        self.effect = Gtk.DropDown.new_from_strings(
            ["Static" if effect is LightingEffect.STATIC else "Morph" for effect in self.effects]
        )
        try:
            selected_effect = self.effects.index(self.backend.settings.effect)
        except ValueError:
            selected_effect = 0
        self.effect.set_selected(selected_effect)
        self.effect.connect("notify::selected", self._effect_changed)
        effect_row = Adw.ActionRow(title="Effect", subtitle="Static color or smooth morph")
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
            title="Morph duration", subtitle="Firmware transition duration"
        )
        self.duration_row.add_suffix(self.duration)
        lighting_group.add(self.duration_row)
        self._effect_changed()

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
                if selected_effect is LightingEffect.MORPH
                else None
            ),
        )
        self.backend.apply_lighting(settings)
        if self.settings_store is not None:
            self.settings_store.save(settings)
        self.toast_overlay.add_toast(Adw.Toast(title="Lighting settings applied"))

    def _effect_changed(self, *_args):
        is_morph = self.effects[self.effect.get_selected()] is LightingEffect.MORPH
        self.secondary_color_row.set_visible(is_morph)
        self.duration_row.set_visible(is_morph)

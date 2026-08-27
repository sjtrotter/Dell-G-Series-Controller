#!/bin/sh
set -eu

gnome_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
python_path=$(command -v python3)
config_home=${XDG_CONFIG_HOME:-"$HOME/.config"}
unit_dir="$config_home/systemd/user"
unit_name=dell-g-series-controller-brightness.service
template="$gnome_dir/data/dell-g-series-controller-brightness-development.service.in"
temporary=$(mktemp)
trap 'rm -f "$temporary"' EXIT HUP INT TERM

sed \
    -e "s|@PYTHON@|$python_path|g" \
    -e "s|@SERVICE@|$gnome_dir/service.py|g" \
    "$template" > "$temporary"
install -Dm644 "$temporary" "$unit_dir/$unit_name"
systemctl --user daemon-reload

printf '%s\n' "Installed development user unit: $unit_dir/$unit_name"
printf '%s\n' "Enable it with: systemctl --user enable --now $unit_name"

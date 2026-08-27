"""Keyboard-zone presentation layouts, separate from firmware zone IDs."""

from dataclasses import dataclass


ROW_LENGTHS = (10, 10, 9, 7)
KEY_COUNT = sum(ROW_LENGTHS)


@dataclass(frozen=True)
class KeyboardZone:
    firmware_id: int
    label: str
    key_indices: tuple[int, ...]


@dataclass(frozen=True)
class KeyboardLayout:
    platform_id: int | None
    zones: tuple[KeyboardZone, ...]
    validated: bool


def layout_for_device(platform_id: int | None, zone_count: int) -> KeyboardLayout:
    """Return a display layout without claiming unknown geometry is authoritative."""
    if zone_count < 1:
        raise ValueError("zone_count must be at least one")
    if zone_count == 1:
        return KeyboardLayout(
            platform_id,
            (KeyboardZone(0, "All keys", tuple(range(KEY_COUNT))),),
            True,
        )

    # Firmware reports IDs and a count, but not where those zones are physically
    # located. Equal groups provide a neutral read-only fallback until a platform
    # map has been verified on real hardware.
    zone_keys = [[] for _zone in range(zone_count)]
    key_index = 0
    for columns in ROW_LENGTHS:
        for column in range(columns):
            normalized_x = (column + 0.5) / columns
            firmware_id = min(int(normalized_x * zone_count), zone_count - 1)
            zone_keys[firmware_id].append(key_index)
            key_index += 1

    zones = []
    for firmware_id in range(zone_count):
        zones.append(
            KeyboardZone(
                firmware_id,
                f"Zone {firmware_id + 1}",
                tuple(zone_keys[firmware_id]),
            )
        )
    return KeyboardLayout(platform_id, tuple(zones), False)

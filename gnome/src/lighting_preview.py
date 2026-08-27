"""Deterministic, hardware-free lighting effect previews."""

from .backend import LightingEffect, RgbColor


NormalizedColor = tuple[float, float, float]

RAINBOW: tuple[NormalizedColor, ...] = (
    (1, 0, 0),
    (1, 1, 0),
    (0, 1, 0),
    (0, 1, 1),
    (0, 0, 1),
    (1, 0, 1),
)


def _mix(
    first: NormalizedColor,
    second: NormalizedColor,
    amount: float,
) -> NormalizedColor:
    return tuple(
        start + (end - start) * amount
        for start, end in zip(first, second, strict=True)
    )


def preview_color(
    *,
    enabled: bool,
    effect: LightingEffect,
    colors: tuple[RgbColor, ...],
    brightness: int,
    duration_ms: int,
    tempo: int,
    elapsed_seconds: float,
) -> tuple[NormalizedColor, float]:
    """Return the approximate preview RGB and opacity for one instant."""
    if not enabled:
        return (0.08, 0.08, 0.08), 0.28
    if not colors:
        raise ValueError("a lighting preview requires at least one color")

    normalized = tuple(
        tuple(channel / 255 for channel in color) for color in colors
    )
    duration_seconds = max(duration_ms, 1) / 1000
    level = max(0, min(brightness, 100)) / 100

    if effect is LightingEffect.RAINBOW:
        sequence = RAINBOW
    elif effect is LightingEffect.BREATHING:
        sequence = tuple(
            item for color in normalized for item in (color, (0, 0, 0))
        )
    else:
        sequence = normalized

    if effect is LightingEffect.PULSE:
        visible = (elapsed_seconds * max(tempo, 1) / 18) % 1 < 0.48
        color = sequence[0] if visible else (0, 0, 0)
    elif len(sequence) > 1:
        position = (elapsed_seconds / duration_seconds) % len(sequence)
        index = int(position)
        color = _mix(
            sequence[index],
            sequence[(index + 1) % len(sequence)],
            position - index,
        )
    else:
        color = sequence[0]

    return tuple(channel * level for channel in color), 0.92

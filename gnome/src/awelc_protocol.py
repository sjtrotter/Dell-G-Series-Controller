from dataclasses import dataclass
from typing import Protocol


REPORT_SIZE = 33
REPORT_ID = 0x03
USER_ANIMATION = 0x21
POWER_ANIMATION = 0x22
POWER_ANIMATION_IDS = range(0x5B, 0x61)
AC_SLEEP = 0x5B
AC_CHARGED = 0x5C
AC_CHARGING = 0x5D
DC_SLEEP = 0x5E
DC_ON = 0x5F
DC_LOW = 0x60


@dataclass(frozen=True)
class AnimationAction:
    effect: int
    duration: int
    tempo: int
    color: tuple[int, int, int]

    def __post_init__(self) -> None:
        if not 0 <= self.effect <= 0xFF:
            raise ValueError("effect must fit in one byte")
        if not 0 <= self.duration <= 0xFFFF:
            raise ValueError("duration must fit in two bytes")
        if not 0 <= self.tempo <= 0xFFFF:
            raise ValueError("tempo must fit in two bytes")
        if len(self.color) != 3 or any(not 0 <= value <= 0xFF for value in self.color):
            raise ValueError("color channels must fit in one byte")

    def encode(self) -> bytes:
        return (
            bytes((self.effect,))
            + self.duration.to_bytes(2, "big")
            + self.tempo.to_bytes(2, "big")
            + bytes(self.color)
        )


class ProtocolError(RuntimeError):
    pass


class ReportTransport(Protocol):
    def exchange(self, report: bytes) -> bytes: ...


def build_report(command: int, payload: bytes = b"") -> bytes:
    report = bytes((REPORT_ID, command)) + payload
    if len(report) > REPORT_SIZE:
        raise ValueError("AW-ELC report exceeds 33 bytes")
    return report.ljust(REPORT_SIZE, b"\0")


class AwElcProtocol:
    def __init__(self, transport: ReportTransport):
        self._transport = transport

    def exchange(self, command: int, payload: bytes = b"") -> bytes:
        reply = self._transport.exchange(build_report(command, payload))
        if len(reply) != REPORT_SIZE:
            raise ProtocolError(
                f"AW-ELC returned {len(reply)} bytes; expected {REPORT_SIZE}"
            )
        if reply[:2] != bytes((REPORT_ID, command)):
            raise ProtocolError("AW-ELC reply does not match the command")
        return reply

    def get_version(self) -> tuple[int, int, int]:
        reply = self.exchange(0x20, bytes((0x00,)))
        return tuple(reply[3:6])

    def get_platform(self) -> tuple[int, int]:
        reply = self.exchange(0x20, bytes((0x02,)))
        platform = int.from_bytes(reply[3:5], byteorder="big")
        zone_count = reply[5]
        if zone_count < 1:
            raise ProtocolError("AW-ELC reported zero lighting zones")
        return platform, zone_count

    def get_animation_summary(self) -> tuple[int, int, bytes]:
        """Return the stored count, firmware-selected animation ID, and reply.

        Existing AW-ELC clients use the second 16-bit field as the ID passed to
        an animation command (for example, REMOVE).  It is not a directory bound.
        """
        reply = self.exchange(0x20, bytes((0x03,)))
        count = int.from_bytes(reply[3:5], byteorder="big")
        animation_id = int.from_bytes(reply[5:7], byteorder="big")
        return count, animation_id, reply

    def set_dimness(self, dimness: int, zones: tuple[int, ...]) -> None:
        if not 0 <= dimness <= 100:
            raise ValueError("dimness must be between 0 and 100")
        self.exchange(0x26, self._zone_payload(bytes((dimness,)), zones))

    def set_color(self, color: tuple[int, int, int], zones: tuple[int, ...]) -> None:
        if len(color) != 3 or any(not 0 <= channel <= 255 for channel in color):
            raise ValueError("color channels must be between 0 and 255")
        self.exchange(0x27, self._zone_payload(bytes(color), zones))

    def animation_command(self, subcommand: int, animation_id: int) -> None:
        if not 0 <= subcommand <= 0xFFFF:
            raise ValueError("animation subcommand must fit in two bytes")
        if not 0 <= animation_id <= 0xFFFF:
            raise ValueError("animation ID must fit in two bytes")
        command = (
            POWER_ANIMATION if animation_id in POWER_ANIMATION_IDS else USER_ANIMATION
        )
        payload = subcommand.to_bytes(2, "big") + animation_id.to_bytes(2, "big")
        self.exchange(command, payload)

    def start_series(self, zones: tuple[int, ...], loop: bool = True) -> None:
        payload = bytes((int(loop),)) + len(zones).to_bytes(2, "big") + bytes(zones)
        self._validate_zones(zones)
        self.exchange(0x23, payload)

    def add_actions(self, actions: tuple[AnimationAction, ...]) -> None:
        if not 1 <= len(actions) <= 3:
            raise ValueError("an action report must contain between one and three actions")
        self.exchange(0x24, b"".join(action.encode() for action in actions))

    def save_animation(
        self,
        animation_id: int,
        actions: tuple[AnimationAction, ...],
        zones: tuple[int, ...],
    ) -> None:
        """Replace one animation slot with a looping action series."""
        if not actions:
            raise ValueError("an animation must contain at least one action")
        self.animation_command(0x04, animation_id)  # remove
        self.animation_command(0x01, animation_id)  # start new
        self.start_series(zones)
        for offset in range(0, len(actions), 3):
            self.add_actions(actions[offset : offset + 3])
        self.animation_command(0x02, animation_id)  # finish and save
        self.animation_command(0x06, animation_id)  # make default

    def save_static_animation(
        self,
        animation_id: int,
        color: tuple[int, int, int],
        zones: tuple[int, ...],
        duration: int = 0xFFFF,
        tempo: int = 1,
    ) -> None:
        """Replace one animation slot with a looping static-color series."""
        action = AnimationAction(0, duration, tempo, color)
        self.save_animation(animation_id, (action,), zones)

    def save_morph_animation(
        self,
        animation_id: int,
        primary_color: tuple[int, int, int],
        secondary_color: tuple[int, int, int],
        zones: tuple[int, ...],
        duration: int,
        tempo: int = 1,
    ) -> None:
        """Replace one slot with a looping two-color morph animation.

        Firmware 1.1.7 accepts the tempo field, but hardware testing found no
        visible difference between tempo 1 and 100. Duration controls the
        interpolation timing.
        """
        actions = (
            AnimationAction(2, duration, tempo, primary_color),
            AnimationAction(2, duration, tempo, secondary_color),
        )
        self.save_animation(animation_id, actions, zones)

    def save_pulse_animation(
        self,
        animation_id: int,
        color: tuple[int, int, int],
        zones: tuple[int, ...],
        duration: int,
        tempo: int = 1,
    ) -> None:
        """Replace one slot with the firmware's colored flashing effect."""
        self.save_animation(
            animation_id,
            (AnimationAction(1, duration, tempo, color),),
            zones,
        )

    @staticmethod
    def _zone_payload(prefix: bytes, zones: tuple[int, ...]) -> bytes:
        AwElcProtocol._validate_zones(zones)
        return prefix + len(zones).to_bytes(2, byteorder="big") + bytes(zones)

    @staticmethod
    def _validate_zones(zones: tuple[int, ...]) -> None:
        if not zones:
            raise ValueError("at least one zone is required")
        if len(zones) > 0xff or any(not 0 <= zone <= 0xff for zone in zones):
            raise ValueError("zone IDs and count must fit in one byte")

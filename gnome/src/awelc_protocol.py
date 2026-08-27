from typing import Protocol


REPORT_SIZE = 33
REPORT_ID = 0x03


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

    def get_animation_count(self) -> tuple[int, int]:
        """Return the stored animation count and firmware's maximum ID."""
        reply = self.exchange(0x20, bytes((0x03,)))
        count = int.from_bytes(reply[3:5], byteorder="big")
        return count, reply[5]

    def get_animation_by_index(self, index: int) -> tuple[int, bool, bytes]:
        """Read one stored animation directory entry without changing it."""
        if not 0 <= index <= 0xFF:
            raise ValueError("animation index must fit in one byte")
        reply = self.exchange(0x20, bytes((0x04, index)))
        animation_id = int.from_bytes(reply[3:5], byteorder="big")
        is_custom = reply[5] == 0
        return animation_id, is_custom, reply

    def set_dimness(self, dimness: int, zones: tuple[int, ...]) -> None:
        if not 0 <= dimness <= 100:
            raise ValueError("dimness must be between 0 and 100")
        self.exchange(0x26, self._zone_payload(bytes((dimness,)), zones))

    def set_color(self, color: tuple[int, int, int], zones: tuple[int, ...]) -> None:
        if len(color) != 3 or any(not 0 <= channel <= 255 for channel in color):
            raise ValueError("color channels must be between 0 and 255")
        self.exchange(0x27, self._zone_payload(bytes(color), zones))

    @staticmethod
    def _zone_payload(prefix: bytes, zones: tuple[int, ...]) -> bytes:
        if not zones:
            raise ValueError("at least one zone is required")
        if len(zones) > 0xff or any(not 0 <= zone <= 0xff for zone in zones):
            raise ValueError("zone IDs and count must fit in one byte")
        return prefix + len(zones).to_bytes(2, byteorder="big") + bytes(zones)

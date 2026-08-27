from dataclasses import dataclass


@dataclass(frozen=True)
class DeviceInfo:
    name: str
    controller: str
    firmware: str
    platform: str
    zones: int


class DemoBackend:
    """In-memory backend used for safe UI development and screenshots."""

    def __init__(self):
        self.info = DeviceInfo(
            name="Dell G16 7620",
            controller="Alienware AW-ELC 187c:0550",
            firmware="1.1.7",
            platform="0x0e09",
            zones=1,
        )
        self.enabled = True
        self.color = (255, 0, 0)
        self.brightness = 100

    def apply_lighting(self, enabled, color, brightness):
        self.enabled = enabled
        self.color = color
        self.brightness = brightness

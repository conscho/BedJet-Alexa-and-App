"""BedJet V3 BLE Protocol constants and packet codec."""

from dataclasses import dataclass
from enum import IntEnum

# BLE UUIDs (base: 0000XXXX-bed0-0080-aa55-4265644a6574)
BEDJET_SERVICE_UUID = "00001000-bed0-0080-aa55-4265644a6574"
BEDJET_STATUS_UUID = "00002000-bed0-0080-aa55-4265644a6574"
BEDJET_NAME_UUID = "00002001-bed0-0080-aa55-4265644a6574"
BEDJET_COMMAND_UUID = "00002004-bed0-0080-aa55-4265644a6574"
BEDJET_BIORHYTHM_UUID = "00002005-bed0-0080-aa55-4265644a6574"

BEDJET_ADVERTISEMENT_PREFIX = "BEDJET"


class BedjetMode(IntEnum):
    STANDBY = 0
    HEAT = 1
    TURBO = 2
    EXTENDED_HEAT = 3
    COOL = 4
    DRY = 5
    WAIT = 6


MODE_NAMES = {
    BedjetMode.STANDBY: "Standby",
    BedjetMode.HEAT: "Heat",
    BedjetMode.TURBO: "Turbo",
    BedjetMode.EXTENDED_HEAT: "Extended Heat",
    BedjetMode.COOL: "Cool",
    BedjetMode.DRY: "Dry",
    BedjetMode.WAIT: "Wait",
}


class BedjetButton(IntEnum):
    OFF = 0x01
    COOL = 0x02
    HEAT = 0x03
    TURBO = 0x04
    DRY = 0x05
    EXTENDED_HEAT = 0x06
    M1 = 0x20
    M2 = 0x21
    M3 = 0x22


class BedjetCommand(IntEnum):
    BUTTON = 0x01
    SET_RUNTIME = 0x02
    SET_TEMP = 0x03
    STATUS = 0x06
    SET_FAN = 0x07
    SET_CLOCK = 0x08


# Temperature constants
TEMP_STEP_SIZE = 0.5  # Each step = 0.5°C
MIN_TEMP_F = 66
MAX_TEMP_F = 109
MIN_TEMP_STEP = 38
MAX_TEMP_STEP = 86

# Fan constants
FAN_SPEED_COUNT = 20  # Steps 0-19
FAN_STEP_PERCENT = 5  # Each step = 5%


@dataclass
class BedjetStatus:
    """Parsed BedJet status packet."""
    mode: BedjetMode = BedjetMode.STANDBY
    target_temp_step: int = 0
    actual_temp_step: int = 0
    ambient_temp_step: int = 0
    fan_step: int = 0
    time_remaining_hours: int = 0
    time_remaining_minutes: int = 0
    time_remaining_seconds: int = 0
    max_hours: int = 0
    max_minutes: int = 0
    is_connected: bool = False

    @property
    def target_temp_f(self) -> float:
        return 0.9 * self.target_temp_step + 32.0

    @property
    def actual_temp_f(self) -> float:
        return 0.9 * self.actual_temp_step + 32.0

    @property
    def ambient_temp_f(self) -> float:
        return 0.9 * self.ambient_temp_step + 32.0

    @property
    def target_temp_c(self) -> float:
        return self.target_temp_step * TEMP_STEP_SIZE

    @property
    def actual_temp_c(self) -> float:
        return self.actual_temp_step * TEMP_STEP_SIZE

    @property
    def fan_percent(self) -> int:
        return (self.fan_step + 1) * FAN_STEP_PERCENT

    @property
    def time_remaining_str(self) -> str:
        return f"{self.time_remaining_hours}:{self.time_remaining_minutes:02d}:{self.time_remaining_seconds:02d}"

    def to_dict(self) -> dict:
        return {
            "mode": MODE_NAMES.get(self.mode, "Unknown"),
            "mode_value": int(self.mode),
            "target_temp_f": round(self.target_temp_f, 1),
            "actual_temp_f": round(self.actual_temp_f, 1),
            "ambient_temp_f": round(self.ambient_temp_f, 1),
            "target_temp_c": round(self.target_temp_c, 1),
            "actual_temp_c": round(self.actual_temp_c, 1),
            "fan_percent": self.fan_percent,
            "fan_step": self.fan_step,
            "time_remaining": self.time_remaining_str,
            "time_remaining_hours": self.time_remaining_hours,
            "time_remaining_minutes": self.time_remaining_minutes,
            "time_remaining_seconds": self.time_remaining_seconds,
            "is_connected": self.is_connected,
        }


def parse_status_packet(data: bytes) -> BedjetStatus:
    """Parse a BedJet status notification packet."""
    if len(data) < 18:
        return BedjetStatus()

    return BedjetStatus(
        time_remaining_hours=data[4],
        time_remaining_minutes=data[5],
        time_remaining_seconds=data[6],
        actual_temp_step=data[7],
        target_temp_step=data[8],
        mode=BedjetMode(data[9]) if data[9] <= 6 else BedjetMode.STANDBY,
        fan_step=data[10],
        max_hours=data[11],
        max_minutes=data[12],
        ambient_temp_step=data[17] if len(data) > 17 else 0,
        is_connected=True,
    )


def build_button_command(button: BedjetButton) -> bytes:
    """Build a button press command."""
    return bytes([0x01, BedjetCommand.BUTTON, button])


def build_set_temp_command(temp_f: float) -> bytes:
    """Build a set temperature command from Fahrenheit."""
    step = int(round((temp_f - 32.0) / 0.9))
    step = max(MIN_TEMP_STEP, min(MAX_TEMP_STEP, step))
    return bytes([0x01, BedjetCommand.SET_TEMP, step])


def build_set_fan_command(percent: int) -> bytes:
    """Build a set fan speed command from percentage."""
    step = max(0, min(19, (percent // FAN_STEP_PERCENT) - 1))
    return bytes([0x01, BedjetCommand.SET_FAN, step])


def build_set_runtime_command(hours: int, minutes: int) -> bytes:
    """Build a set runtime command."""
    return bytes([0x02, BedjetCommand.SET_RUNTIME, hours, minutes])

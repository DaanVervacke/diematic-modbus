"""Diematic register bundles grouped by function.

Low registers (1-123) are the Diematic base page. The 427/428 bit words and the
451-472 block are the modular and DPSM condensing-module pages, present on a
Diematic 3 fitted with a DPSM condensing boiler. Addresses and scales are
confirmed against the De Dietrich register sheet and ngraziano/isystem-to-mqtt.
Registers 9, 19, 28, 30, 31 and 33 come from ababilone/Diematic_to_MQTT and were
confirmed live on the test boiler.
"""

from __future__ import annotations

from modbus_connection.model import Component, bit, integer

from .enums import HeatingMode, HotWaterMode
from .faults import MODULENS_FAULTS
from .fields import code_map, fault_code, float10, masked_enum, snap_clamp
from .models import MODEL_CODES

# The register windows the Diematic 3 and 4 regulators answer, copied from the
# polling banks of the Diematic_to_MQTT project and extended to 472 for the DPSM
# instant-power registers. Reads never touch a gap.
HOLDING_WINDOWS = ((1, 63), (64, 127), (384, 447), (448, 472))

_HOT_WATER = snap_clamp(1.0, 10.0, 80.0)
_ZONE = snap_clamp(0.5, 5.0, 30.0)
_SLOPE = snap_clamp(0.1, 0.0, 4.0)
_SUMMER_WINTER = snap_clamp(0.5, 15.0, 30.5)


class DiematicComponent(Component):
    """A Diematic register bundle constrained to the answered windows."""

    register_ranges = HOLDING_WINDOWS


class Sensors(DiematicComponent):
    """Boiler and system sensor readings."""

    outdoor_temp = float10(7, unit="°C")
    outdoor_temp_bus = float10(470, unit="°C")
    boiler_temp = float10(75, unit="°C")
    calc_boiler_temp = float10(462, unit="°C")
    return_temp = float10(453, unit="°C")
    smoke_temp = float10(454, unit="°C")
    water_pressure = float10(456, unit="bar")
    ionization_current = float10(451, unit="µA")
    fan_speed = integer(455, signed=False, nan=0xFFFF, unit="rpm")
    pump_power = integer(463, signed=False, nan=0xFFFF, unit="%")
    instant_power = float10(471, unit="kW")
    average_power = float10(472, unit="kW")
    solar_temp = float10(467, unit="°C")
    solar_tank_temp = float10(468, unit="°C")
    burner_on = bit(427, 3)
    hot_water_pump_on = bit(427, 5)
    alarm = fault_code(465, MODULENS_FAULTS)


class HotWater(DiematicComponent):
    """Domestic hot-water readings and setpoints."""

    temp = float10(62, unit="°C")
    temp_dpsm = float10(459, unit="°C")
    mode = masked_enum(17, 0x50, HotWaterMode)
    day_target = float10(59, writable=_HOT_WATER, force_fc16=True, unit="°C")
    night_target = float10(96, writable=_HOT_WATER, force_fc16=True, unit="°C")


class CircuitA(DiematicComponent):
    """Heating circuit A readings and setpoints."""

    room_temp = float10(18, unit="°C")
    calc_temp = float10(21, unit="°C")
    mode = masked_enum(17, 0x2F, HeatingMode)
    pump_on = bit(427, 4)
    ambient_influence = integer(19, signed=False)
    slope = float10(20, writable=_SLOPE, force_fc16=True, unit="K/K")
    day_target = float10(14, writable=_ZONE, force_fc16=True, unit="°C")
    night_target = float10(15, writable=_ZONE, force_fc16=True, unit="°C")
    antifreeze_target = float10(16, writable=_ZONE, force_fc16=True, unit="°C")


class CircuitB(DiematicComponent):
    """Heating circuit B readings and setpoints."""

    room_temp = float10(27, unit="°C")
    calc_temp = float10(32, unit="°C")
    supply_temp = float10(33, unit="°C")
    mode = masked_enum(26, 0x2F, HeatingMode)
    pump_on = bit(428, 4)
    ambient_influence = integer(28, signed=False)
    min_temp = float10(30, unit="°C")
    max_temp = float10(31, unit="°C")
    slope = float10(29, writable=_SLOPE, force_fc16=True, unit="K/K")
    day_target = float10(23, writable=_ZONE, force_fc16=True, unit="°C")
    night_target = float10(24, writable=_ZONE, force_fc16=True, unit="°C")
    antifreeze_target = float10(25, writable=_ZONE, force_fc16=True, unit="°C")


class Settings(DiematicComponent):
    """Boiler-level configuration, some writable and some read-only."""

    ext_frost_threshold = float10(9, unit="°C")
    summer_winter_temp = float10(8, writable=_SUMMER_WINTER, force_fc16=True, unit="°C")
    boiler_min = float10(70, writable=True, force_fc16=True, unit="°C")
    boiler_max = float10(71, writable=True, force_fc16=True, unit="°C")


class Identity(DiematicComponent):
    """Regulator identity and clock registers."""

    controller = integer(3, signed=False)
    boiler_type = code_map(457, MODEL_CODES)
    hour = integer(4, signed=False)
    minute = integer(5, signed=False)
    weekday = integer(6, signed=False)
    day = integer(108, signed=False)
    month = integer(109, signed=False)
    year = integer(110, signed=False)

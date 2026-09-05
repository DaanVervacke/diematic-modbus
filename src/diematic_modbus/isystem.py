"""The De Dietrich iSystem register layout.

A parallel layout for boilers whose firmware exposes the iSystem registers.
Sensors and setpoints live in the iSystem address page (601 outdoor, 602 boiler
and so on), with circuit C and per-circuit calculated setpoints that the low
layout lacks. Circuit mode is read and written through the low registers 17 and
26, which this boiler also answers, because the iSystem page has no writable
mode register. Addresses and scales come from the iSystem map in
IgnacioHR/diematic_server and are verified live before writes are trusted. The
schedule blocks and program selection registers follow the De Dietrich register
sheet and ngraziano/isystem-to-mqtt, which names each block program P4. Circuit
ambient influence (654, 660), circuit B min and max (662, 663) and circuit B
supply temperature (605) come from ngraziano and were confirmed live against the
matching base page values. The external frost threshold has no iSystem register
and stays base-only. Smoke 604, pressure 610, boiler min and max 677/678, circuit
B slope 661, and the circuit C block 668-671 come from ngraziano-go and
45clouds/diematic2mqtt, confirmed live on the boiler.
"""

from __future__ import annotations

from modbus_connection import ModbusUnit
from modbus_connection.model import Component, bit, integer

from ._base import _MODE_A, _MODE_B, _Regulator
from .enums import DiematicVariant, HeatingMode, HotWaterMode
from .faults import MODULENS_FAULTS
from .fields import (
    WeekSchedule,
    code_map,
    fault_code,
    float10,
    masked_enum,
    schedule_day,
    snap_clamp,
    time_program,
)
from .models import MODEL_CODES

ISYSTEM_WINDOWS = (
    (8, 8),
    (17, 26),
    (231, 233),
    (247, 252),
    (263, 299),
    (305, 360),
    (426, 474),
    (600, 625),
    (644, 644),
    (650, 685),
    (707, 744),
)

SCHEDULE_BASES = {
    "circuit_a_p4": 126,
    "circuit_b_p4": 147,
    "circuit_c_p4": 168,
    "hot_water": 189,
    "auxiliary": 210,
}

_DAY_STRIDE = 3
_DAYS = 7
_DAY_WINDOWS = tuple(
    (day * _DAY_STRIDE, day * _DAY_STRIDE + _DAY_STRIDE - 1) for day in range(_DAYS)
)

_HEATING_MASK = 0x2F
_HOT_WATER_MASK = 0x50
_READ_ONCE = frozenset(f"schedules.{name}" for name in SCHEDULE_BASES) | {"config"}

_ZONE_DAY = snap_clamp(0.5, 10.0, 30.0)
_ZONE_FROST = snap_clamp(0.5, 3.0, 20.0)
_DHW = snap_clamp(1.0, 10.0, 80.0)
_SLOPE = snap_clamp(0.1, 0.0, 4.0)
_SUMMER_WINTER = snap_clamp(0.5, 15.0, 30.5)


class ISystemComponent(Component):
    """A 600 bank register bundle constrained to the answered windows."""

    register_ranges = ISYSTEM_WINDOWS


class Sensors(ISystemComponent):
    """Boiler and system sensor readings in the iSystem layout."""

    outdoor_temp = float10(601, unit="°C")
    boiler_temp = float10(602, unit="°C")
    calc_boiler_temp = float10(620, unit="°C")
    return_temp = float10(607, unit="°C")
    outlet_temp = float10(621, unit="°C")
    ionization_current = float10(608, unit="µA")
    fan_speed = integer(609, signed=False, nan=0xFFFF, unit="rpm")
    smoke_temp = float10(604, unit="°C")
    water_pressure = float10(610, unit="bar")
    burner_on = bit(427, 3)
    hot_water_pump_on = bit(427, 5)
    alarm = fault_code(465, MODULENS_FAULTS)


class HotWater(ISystemComponent):
    """Domestic hot-water readings and setpoints in the iSystem layout."""

    temp = float10(603, unit="°C")
    bottom_temp = float10(623, unit="°C")
    mode = masked_enum(_MODE_A, _HOT_WATER_MASK, HotWaterMode)
    day_target = float10(672, writable=_DHW, force_fc16=True, unit="°C")
    night_target = float10(673, writable=_DHW, force_fc16=True, unit="°C")


class CircuitA(ISystemComponent):
    """Heating circuit A readings and setpoints in the iSystem layout."""

    room_temp = float10(614, unit="°C")
    calc_temp = float10(615, unit="°C")
    mode = masked_enum(_MODE_A, _HEATING_MASK, HeatingMode)
    program = time_program(231)
    pump_on = bit(427, 4)
    ambient_influence = integer(654, signed=False)
    slope = float10(655, writable=_SLOPE, force_fc16=True, unit="K/K")
    day_target = float10(650, writable=_ZONE_DAY, force_fc16=True, unit="°C")
    night_target = float10(651, writable=_ZONE_DAY, force_fc16=True, unit="°C")
    antifreeze_target = float10(652, writable=_ZONE_FROST, force_fc16=True, unit="°C")


class CircuitB(ISystemComponent):
    """Heating circuit B readings and setpoints in the iSystem layout."""

    room_temp = float10(616, unit="°C")
    calc_temp = float10(617, unit="°C")
    supply_temp = float10(605, unit="°C")
    mode = masked_enum(_MODE_B, _HEATING_MASK, HeatingMode)
    program = time_program(232)
    pump_on = bit(428, 4)
    ambient_influence = integer(660, signed=False)
    slope = float10(661, unit="K/K")
    min_temp = float10(662, unit="°C")
    max_temp = float10(663, unit="°C")
    day_target = float10(656, writable=_ZONE_DAY, force_fc16=True, unit="°C")
    night_target = float10(657, writable=_ZONE_DAY, force_fc16=True, unit="°C")
    antifreeze_target = float10(658, writable=_ZONE_FROST, force_fc16=True, unit="°C")


class CircuitC(ISystemComponent):
    """Heating circuit C readings and setpoints, present only in the iSystem layout.

    The low bank has no circuit C, so this circuit exposes no mode register.
    """

    room_temp = float10(618, unit="°C")
    calc_temp = float10(619, unit="°C")
    program = time_program(233)
    ambient_influence = integer(668, signed=False)
    slope = float10(669, unit="K/K")
    min_temp = float10(670, unit="°C")
    max_temp = float10(671, unit="°C")
    day_target = float10(664, writable=_ZONE_DAY, force_fc16=True, unit="°C")
    night_target = float10(665, writable=_ZONE_DAY, force_fc16=True, unit="°C")
    antifreeze_target = float10(666, writable=_ZONE_FROST, force_fc16=True, unit="°C")


class WeekProgram(Component):
    """One weekly comfort program, three registers per day, read a day at a time."""

    register_ranges = _DAY_WINDOWS

    monday = schedule_day(0)
    tuesday = schedule_day(3)
    wednesday = schedule_day(6)
    thursday = schedule_day(9)
    friday = schedule_day(12)
    saturday = schedule_day(15)
    sunday = schedule_day(18)

    @property
    def week(self) -> WeekSchedule:
        """The comfort periods keyed by isoweekday, 1 for Monday."""
        days = (
            self.monday,
            self.tuesday,
            self.wednesday,
            self.thursday,
            self.friday,
            self.saturday,
            self.sunday,
        )
        return {day + 1: periods or [] for day, periods in enumerate(days)}


class Schedules:
    """The weekly comfort programs the boiler exposes over Modbus.

    Each heating circuit exposes only its program P4. Hot water and the auxiliary
    circuit each have a single program.
    """

    def __init__(self, unit: ModbusUnit) -> None:
        """Build one program bundle per exposed schedule block."""
        self.programs = {
            name: WeekProgram(unit, base_offset=base)
            for name, base in SCHEDULE_BASES.items()
        }

    @property
    def circuit_a_p4(self) -> WeekSchedule:
        """Program P4 of heating circuit A."""
        return self.programs["circuit_a_p4"].week

    @property
    def circuit_b_p4(self) -> WeekSchedule:
        """Program P4 of heating circuit B."""
        return self.programs["circuit_b_p4"].week

    @property
    def circuit_c_p4(self) -> WeekSchedule:
        """Program P4 of heating circuit C."""
        return self.programs["circuit_c_p4"].week

    @property
    def hot_water(self) -> WeekSchedule:
        """The hot-water comfort program."""
        return self.programs["hot_water"].week

    @property
    def auxiliary(self) -> WeekSchedule:
        """The auxiliary circuit comfort program."""
        return self.programs["auxiliary"].week


class Settings(ISystemComponent):
    """Boiler-level configuration in the iSystem layout."""

    summer_winter_temp = float10(8, writable=_SUMMER_WINTER, force_fc16=True, unit="°C")
    boiler_min = float10(677, unit="°C")
    boiler_max = float10(678, unit="°C")


class Config(ISystemComponent):
    """Installer tuning parameters in the iSystem layout, read once.

    Addresses and scales come from ngraziano-go and 45clouds/diematic2mqtt,
    confirmed live. Anticipation uses a 101 no-value code and footprint a 150 one.
    """

    autoadapt_a = float10(247)
    autoadapt_b = float10(248)
    autoadapt_c = float10(249)
    language = integer(263, signed=False)
    building_inertia = integer(264, signed=False)
    bandwidth = float10(266)
    three_way_valve_shift = float10(267)
    min_running_time = integer(269, signed=False)
    burner_temporisation = integer(271, signed=False)
    pump_postrun = integer(272, signed=False)
    outside_calibration = float10(274, unit="°C")
    zone_a_calibration = float10(275, unit="°C")
    zone_b_calibration = float10(276, unit="°C")
    zone_c_calibration = float10(277, unit="°C")
    anticipation_a = float10(282, none_values=(101,))
    anticipation_b = float10(283, none_values=(101,))
    anticipation_c = float10(284, none_values=(101,))
    footprint_a_day = float10(289, none_values=(150,))
    footprint_a_night = float10(290, none_values=(150,))
    footprint_b_day = float10(291, none_values=(150,))
    footprint_b_night = float10(292, none_values=(150,))
    footprint_c_day = float10(358, none_values=(150,))
    footprint_c_night = float10(359, none_values=(150,))
    zone_a_type = integer(296, signed=False)
    zone_b_type = integer(297, signed=False)
    zone_c_type = integer(360, signed=False)
    zone_a_min = float10(298, unit="°C")
    zone_a_max = float10(299, unit="°C")
    max_fan_speed = integer(305, signed=False, nan=0xFFFF, unit="rpm")
    three_way_valve_temp_shift = float10(426, unit="°C")
    calc_setpoint = float10(436, unit="°C")
    three_way_valve_bandwidth = float10(438)
    modulated_power = integer(473, signed=False, unit="%")
    output_state = integer(474, signed=False)


class Diagnostics(ISystemComponent):
    """Boiler state and diagnostic registers in the iSystem layout.

    State words are exposed as raw codes. Addresses from ngraziano-go and
    45clouds/diematic2mqtt, confirmed live.
    """

    boiler_active_mode = integer(644, signed=False)
    dhw_priority = integer(674, signed=False)
    pcu_state = integer(710, signed=False)
    pcu_substate = integer(711, signed=False)
    pcu_block = integer(712, signed=False)
    pcu_lock = integer(713, signed=False)
    boiler_state = integer(735, signed=False)
    system_input_state = integer(741, signed=False)
    zone_aux_type = integer(744, signed=False)


class Identity(ISystemComponent):
    """Regulator identity and clock registers in the iSystem layout."""

    software_version = integer(600, signed=False)
    boiler_type = code_map(457, MODEL_CODES)
    hour = integer(679, signed=False)
    minute = integer(680, signed=False)
    weekday = integer(681, signed=False)
    day = integer(682, signed=False)
    month = integer(683, signed=False)
    year = integer(684, signed=False)


class DiematicISystem(_Regulator):
    """A De Dietrich Diematic regulator addressed through the iSystem layout."""

    def __init__(
        self,
        unit: ModbusUnit,
        *,
        variant: DiematicVariant = DiematicVariant.DIEMATIC_3,
        force_circuit_a: bool = False,
        force_circuit_b: bool = False,
        force_circuit_c: bool = False,
    ) -> None:
        """Build the 600 bank regulator over ``unit``."""
        self.variant = variant
        self._force_circuit_a = force_circuit_a
        self._force_circuit_b = force_circuit_b
        self._force_circuit_c = force_circuit_c
        self.sensors = Sensors(unit)
        self.hot_water = HotWater(unit)
        self.circuit_a = CircuitA(unit)
        self.circuit_b = CircuitB(unit)
        self.circuit_c = CircuitC(unit)
        self.schedules = Schedules(unit)
        self.settings = Settings(unit)
        self.config = Config(unit)
        self.diagnostics = Diagnostics(unit)
        self.identity = Identity(unit)
        self._install_engine(
            unit,
            {
                "sensors": self.sensors,
                "hot_water": self.hot_water,
                "circuit_a": self.circuit_a,
                "circuit_b": self.circuit_b,
                "circuit_c": self.circuit_c,
                "settings": self.settings,
                "config": self.config,
                "diagnostics": self.diagnostics,
                "identity": self.identity,
                **{
                    f"schedules.{name}": program
                    for name, program in self.schedules.programs.items()
                },
            },
            _READ_ONCE,
        )

    @property
    def circuit_a_present(self) -> bool:
        """Whether heating circuit A reports a room temperature."""
        return self._force_circuit_a or self.circuit_a.room_temp is not None

    @property
    def circuit_b_present(self) -> bool:
        """Whether heating circuit B reports a room temperature."""
        return self._force_circuit_b or self.circuit_b.room_temp is not None

    @property
    def circuit_c_present(self) -> bool:
        """Whether heating circuit C reports a room temperature."""
        return self._force_circuit_c or self.circuit_c.room_temp is not None

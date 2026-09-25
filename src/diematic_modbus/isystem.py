"""Diematic register bundles and controls for the iSystem layout."""

from __future__ import annotations

from collections.abc import Callable
from typing import ClassVar

from modbus_connection import ModbusUnit
from modbus_connection.model import Component, NumberField, bit, integer

from ._base import _HEATING_MASK, _HOT_WATER_MASK, ClockPolicy, _Regulator
from .enums import (
    ActiveMode,
    AuxiliaryInput,
    AuxiliaryOutputType,
    AuxiliaryType,
    CircuitType,
    DiematicVariant,
    HeatingMode,
    HotWaterMode,
    HotWaterPriority,
    Language,
    LegionellaProtection,
    NightMode,
)
from .faults import MODULENS_FAULTS
from .fields import (
    DaySchedule,
    WeekSchedule,
    boiler_type_field,
    enum_value,
    fault_code,
    float10,
    int_clamp,
    masked_enum,
    multiplied_integer,
    schedule_day,
    snap_clamp,
    time_program,
)

_MODE_A_ISYSTEM = 653
_MODE_B_ISYSTEM = 659
_MODE_C_ISYSTEM = 667

ISYSTEM_WINDOWS = (
    (8, 8),
    (9, 11),
    (61, 61),
    (102, 102),
    (231, 233),
    (247, 252),
    (263, 299),
    (305, 360),
    (426, 474),
    (475, 475),
    (600, 625),
    (637, 644),
    (650, 685),
    (707, 744),
    (745, 746),
)

_SCHEDULE_BASES = {
    "circuit_a_p4": 126,
    "circuit_b_p4": 147,
    "circuit_c_p4": 168,
    "hot_water": 189,
    "auxiliary": 210,
}

_DAY_STRIDE = 3
_DAYS = 7
_WEEKDAY_FIELDS = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)
_DAY_WINDOWS = tuple(
    (day * _DAY_STRIDE, day * _DAY_STRIDE + _DAY_STRIDE - 1) for day in range(_DAYS)
)

_READ_ONCE = frozenset(f"schedules.{name}" for name in _SCHEDULE_BASES) | {"config"}

_ZONE_DAY = snap_clamp(0.5, 10.0, 30.0)
_ZONE_NIGHT = snap_clamp(0.5, 5.0, 30.0)
_ZONE_BC_MIN = snap_clamp(0.5, 10.0, 30.0)
_ZONE_BC_MAX = snap_clamp(0.5, 50.0, 95.0)
_ZONE_FROST = snap_clamp(0.5, 3.0, 20.0)
_DHW = snap_clamp(1.0, 10.0, 80.0)
_SLOPE = snap_clamp(0.1, 0.0, 4.0)
_SUMMER_WINTER = snap_clamp(0.5, 15.0, 30.5)
_ZONE_A_MIN = snap_clamp(0.5, 10.0, 50.0)
_ZONE_A_MAX = snap_clamp(0.5, 20.0, 120.0)
_ANTICIPATION = snap_clamp(0.1, 0.0, 10.0)
_PUMP_DELAY = int_clamp(0, 15)
_INERTIA = int_clamp(0, 10)
_BANDWIDTH = snap_clamp(1.0, 4.0, 16.0)


def _permanent_derogation(raw: int) -> bool | None:
    """Decode verified heating override modes independently of hot-water bits."""
    mode = raw & _HEATING_MASK
    if mode in (HeatingMode.PERM_DAY, HeatingMode.PERM_NIGHT):
        return True
    if mode in (HeatingMode.AUTO, HeatingMode.TEMP_DAY, HeatingMode.TEMP_NIGHT):
        return False
    return None


def _derogation_until_end(raw: int) -> bool | None:
    """Decode the documented timed-override bit for known heating modes."""
    mode = raw & _HEATING_MASK
    if mode in (HeatingMode.PERM_DAY, HeatingMode.PERM_NIGHT):
        return False
    if mode in (HeatingMode.AUTO, HeatingMode.TEMP_DAY, HeatingMode.TEMP_NIGHT):
        return bool(raw & 0x20)
    return None


class ISystemComponent(Component):
    """An iSystem register bundle limited to the supported read windows."""

    register_ranges = ISYSTEM_WINDOWS


class Sensors(ISystemComponent):
    """Boiler and system sensor readings in the iSystem layout."""

    outdoor_temp = float10(601, unit="°C")
    boiler_temp = float10(602, unit="°C")
    calc_boiler_temp = float10(620, unit="°C")
    secondary_calc_temp = float10(734, unit="°C")
    return_temp = float10(607, unit="°C")
    auxiliary_1_temp = float10(622, unit="°C")
    auxiliary_2_temp = float10(623, unit="°C")
    universal_temp = float10(624, unit="°C")
    ionization_current = float10(608, unit="µA")
    fan_speed = integer(609, signed=False, nan=0xFFFF, unit="rpm")
    instant_power = integer(613, signed=False, unit="%")
    smoke_temp = float10(604, unit="°C")
    water_pressure = float10(610, unit="bar")
    mean_outside_temp = float10(102, unit="°C")
    burner_starts = multiplied_integer(251, 4, nan=0xFFFF, unit="starts")
    burner_runtime = integer(252, signed=False, nan=0xFFFF, unit="h")
    burner_on = bit(427, 3)
    hot_water_pump_on = bit(427, 5)
    alarm = fault_code(465, MODULENS_FAULTS)


class HotWater(ISystemComponent):
    """Domestic hot-water readings and setpoints in the iSystem layout."""

    temp = float10(603, unit="°C")
    mode = masked_enum(_MODE_B_ISYSTEM, _HOT_WATER_MASK, HotWaterMode)
    active_mode = masked_enum(640, 0x06, ActiveMode)
    priority = enum_value(674, HotWaterPriority, writable=True, force_fc16=True)
    pump_delay = integer(
        61, signed=False, writable=_PUMP_DELAY, force_fc16=True, unit="min"
    )
    legionella_protection = enum_value(
        268, LegionellaProtection, writable=True, force_fc16=True
    )
    day_target = float10(672, writable=_DHW, force_fc16=True, unit="°C")
    night_target = float10(673, writable=_DHW, force_fc16=True, unit="°C")


class CircuitA(ISystemComponent):
    """Heating circuit A readings and setpoints in the iSystem layout."""

    room_temp = float10(614, unit="°C")
    calc_temp = float10(615, unit="°C")
    supply_temp = float10(621, unit="°C")
    mode = masked_enum(_MODE_A_ISYSTEM, _HEATING_MASK, HeatingMode)
    circuit_type = enum_value(296, CircuitType)
    active_mode = masked_enum(637, 0x06, ActiveMode)
    permanent_derogation = NumberField[bool | None](
        _MODE_A_ISYSTEM, signed=False, convert=_permanent_derogation
    )
    derogation_until_end = NumberField[bool | None](
        _MODE_A_ISYSTEM, signed=False, convert=_derogation_until_end
    )
    program = time_program(231)
    pump_on = bit(427, 4)
    ambient_influence = integer(654, signed=False)
    slope = float10(655, writable=_SLOPE, force_fc16=True, unit="K/K")
    day_target = float10(650, writable=_ZONE_DAY, force_fc16=True, unit="°C")
    night_target = float10(651, writable=_ZONE_NIGHT, force_fc16=True, unit="°C")
    antifreeze_target = float10(652, writable=_ZONE_FROST, force_fc16=True, unit="°C")


class CircuitB(ISystemComponent):
    """Heating circuit B readings and setpoints in the iSystem layout."""

    room_temp = float10(616, unit="°C")
    calc_temp = float10(617, unit="°C")
    supply_temp = float10(605, unit="°C")
    mode = masked_enum(_MODE_B_ISYSTEM, _HEATING_MASK, HeatingMode)
    circuit_type = enum_value(297, CircuitType)
    active_mode = masked_enum(638, 0x06, ActiveMode)
    permanent_derogation = NumberField[bool | None](
        _MODE_B_ISYSTEM, signed=False, convert=_permanent_derogation
    )
    derogation_until_end = NumberField[bool | None](
        _MODE_B_ISYSTEM, signed=False, convert=_derogation_until_end
    )
    all_circuits_derogation = bit(_MODE_B_ISYSTEM, 7)
    program = time_program(232)
    pump_on = bit(428, 4)
    valve_opening = bit(428, 1)
    valve_closing = bit(428, 0)
    ambient_influence = integer(660, signed=False)
    slope = float10(661, writable=_SLOPE, force_fc16=True, unit="K/K")
    min_temp = float10(662, writable=_ZONE_BC_MIN, force_fc16=True, unit="°C")
    max_temp = float10(663, writable=_ZONE_BC_MAX, force_fc16=True, unit="°C")
    day_target = float10(656, writable=_ZONE_DAY, force_fc16=True, unit="°C")
    night_target = float10(657, writable=_ZONE_NIGHT, force_fc16=True, unit="°C")
    antifreeze_target = float10(658, writable=_ZONE_FROST, force_fc16=True, unit="°C")


class CircuitC(ISystemComponent):
    """Heating circuit C readings and setpoints in the iSystem layout."""

    room_temp = float10(618, unit="°C")
    calc_temp = float10(619, unit="°C")
    mode = masked_enum(_MODE_C_ISYSTEM, _HEATING_MASK, HeatingMode)
    circuit_type = enum_value(360, CircuitType)
    active_mode = masked_enum(639, 0x06, ActiveMode)
    program = time_program(233)
    permanent_derogation = NumberField[bool | None](
        _MODE_C_ISYSTEM, signed=False, convert=_permanent_derogation
    )
    derogation_until_end = NumberField[bool | None](
        _MODE_C_ISYSTEM, signed=False, convert=_derogation_until_end
    )
    all_circuits_derogation = bit(_MODE_C_ISYSTEM, 7)
    ambient_influence = integer(668, signed=False)
    slope = float10(669, writable=_SLOPE, force_fc16=True, unit="K/K")
    min_temp = float10(670, writable=_ZONE_BC_MIN, force_fc16=True, unit="°C")
    max_temp = float10(671, writable=_ZONE_BC_MAX, force_fc16=True, unit="°C")
    day_target = float10(664, writable=_ZONE_DAY, force_fc16=True, unit="°C")
    night_target = float10(665, writable=_ZONE_NIGHT, force_fc16=True, unit="°C")
    antifreeze_target = float10(666, writable=_ZONE_FROST, force_fc16=True, unit="°C")


class WeekProgram(Component):
    """One weekly comfort program read as seven separate three-register days."""

    register_ranges = _DAY_WINDOWS
    _on_day_written: Callable[[WeekProgram], None] | None = None

    monday = schedule_day(0, writable=True)
    tuesday = schedule_day(3, writable=True)
    wednesday = schedule_day(6, writable=True)
    thursday = schedule_day(9, writable=True)
    friday = schedule_day(12, writable=True)
    saturday = schedule_day(15, writable=True)
    sunday = schedule_day(18, writable=True)

    @property
    def week(self) -> WeekSchedule:
        """Comfort periods keyed by weekday, from 1 for Monday to 7 for Sunday."""
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

    async def set_day(self, weekday: int, periods: DaySchedule) -> None:
        """Write program P4 comfort periods for one weekday, 1 Monday to 7 Sunday."""
        if not 1 <= weekday <= _DAYS:
            raise ValueError(f"weekday must be 1 to {_DAYS}, got {weekday}")
        await self.write(_WEEKDAY_FIELDS[weekday - 1], periods)
        if self._on_day_written is not None:
            self._on_day_written(self)


class Schedules:
    """Heating P4, hot-water, and auxiliary schedules, writable one day at a time."""

    SCHEDULE_BASES: ClassVar[dict[str, int]] = _SCHEDULE_BASES

    def __init__(self, unit: ModbusUnit) -> None:
        """Build one program bundle per exposed schedule block."""
        self._programs: dict[str, WeekProgram] = {
            name: WeekProgram(unit, base_offset=base)
            for name, base in self.SCHEDULE_BASES.items()
        }

    def _require_schedule(self, schedule: str) -> WeekProgram:
        """Return the program for a known schedule. Raise ValueError on unknown name."""
        if schedule not in self._programs:
            raise ValueError(f"unknown schedule {schedule!r}")
        return self._programs[schedule]

    def bundles(self) -> dict[str, WeekProgram]:
        """Return the schedule-name to WeekProgram map for engine registration."""
        return self._programs

    async def set_day(self, schedule: str, weekday: int, periods: DaySchedule) -> None:
        """Write one weekday of a named schedule."""
        await self._require_schedule(schedule).set_day(weekday, periods)

    async def async_update(self, schedule: str) -> None:
        """Poll one schedule by name."""
        await self._require_schedule(schedule).async_update()

    def get_day(self, schedule: str, weekday: int) -> DaySchedule:
        """Return the comfort periods for one weekday."""
        return self._require_schedule(schedule).week[weekday]

    def get_week(self, schedule: str) -> WeekSchedule:
        """Return the comfort periods for one week."""
        return self._require_schedule(schedule).week


SCHEDULE_BASES = Schedules.SCHEDULE_BASES


class Settings(ISystemComponent):
    """Boiler-level configuration in the iSystem layout."""

    language = enum_value(263, Language)
    summer_winter_temp = float10(8, writable=_SUMMER_WINTER, force_fc16=True, unit="°C")
    outdoor_antifreeze = float10(9, unit="°C")
    night_mode = enum_value(10, NightMode, writable=True, force_fc16=True)
    heating_pump_delay = integer(
        11, signed=False, writable=_PUMP_DELAY, force_fc16=True, unit="min"
    )
    boiler_min = float10(677, unit="°C")
    boiler_max = float10(678, unit="°C")


class Config(ISystemComponent):
    """Installer settings and output values cached after the first successful read."""

    _on_written: Callable[[Config], None] | None = None

    async def write(self, field: str, value: object) -> None:
        """Write a config field and re-arm the cached read so it is reread."""
        await super().write(field, value)
        if self._on_written is not None:
            self._on_written(self)

    autoadapt_a = float10(247)
    autoadapt_b = float10(248)
    autoadapt_c = float10(249)
    building_inertia = integer(264, signed=False, writable=_INERTIA, force_fc16=True)
    bandwidth = float10(266, writable=_BANDWIDTH, force_fc16=True, unit="K")
    three_way_valve_shift = float10(267)
    min_running_time = integer(269, signed=False, unit="s")
    burner_temporisation = integer(271, signed=False)
    pump_postrun = multiplied_integer(272, 2, unit="min")
    outside_calibration = float10(274, unit="°C")
    zone_a_calibration = float10(275, unit="°C")
    zone_b_calibration = float10(276, unit="°C")
    zone_c_calibration = float10(277, unit="°C")
    anticipation_a = float10(
        282, writable=_ANTICIPATION, force_fc16=True, none_values=(101,)
    )
    anticipation_b = float10(
        283, writable=_ANTICIPATION, force_fc16=True, none_values=(101,)
    )
    anticipation_c = float10(
        284, writable=_ANTICIPATION, force_fc16=True, none_values=(101,)
    )
    footprint_a_day = float10(289, none_values=(150,))
    footprint_a_night = float10(290, none_values=(150,))
    footprint_b_day = float10(291, none_values=(150,))
    footprint_b_night = float10(292, none_values=(150,))
    footprint_c_day = float10(358, none_values=(150,))
    footprint_c_night = float10(359, none_values=(150,))
    zone_a_min = float10(298, writable=_ZONE_A_MIN, force_fc16=True, unit="°C")
    zone_a_max = float10(299, writable=_ZONE_A_MAX, force_fc16=True, unit="°C")
    max_fan_speed = integer(305, signed=False, nan=0xFFFF, unit="rpm")
    three_way_valve_temp_shift = float10(426, unit="°C")
    calc_setpoint = float10(436, unit="°C")
    three_way_valve_bandwidth = float10(438)
    modulated_power = integer(473, signed=False, unit="%")


class Outputs(ISystemComponent):
    """Read-only output words and documented secondary output bits."""

    primary = integer(474, signed=False)
    secondary = integer(475, signed=False)
    boiler_state = integer(735, signed=False)
    burner_stage_1_on = bit(474, 0)
    hydraulic_valve_close = bit(474, 3)
    boiler_pump_on = bit(474, 4)
    secondary_pump_on = bit(735, 3)
    dhw_pump_on = bit(475, 0)
    circuit_a_pump_on = bit(475, 1)
    circuit_a_valve_open = bit(475, 2)
    circuit_a_valve_close = bit(475, 3)
    circuit_b_pump_on = bit(475, 4)
    circuit_b_valve_open = bit(475, 5)
    circuit_b_valve_close = bit(475, 6)
    circuit_c_pump_on = bit(475, 7)
    circuit_c_valve_open = bit(475, 8)
    circuit_c_valve_close = bit(475, 9)
    auxiliary_1_pump_on = bit(475, 10)
    auxiliary_2_pump_on = bit(475, 11)
    auxiliary_3_pump_on = bit(475, 12)
    phone_output_on = bit(475, 13)


class Diagnostics(ISystemComponent):
    """Boiler state and diagnostic registers in the iSystem layout."""

    boiler_active_mode = integer(644, signed=False)
    aux_active_mode = masked_enum(641, 0x06, ActiveMode)
    dhw_priority = masked_enum(674, 0xFF, HotWaterPriority)
    pcu_state = integer(710, signed=False)
    pcu_substate = integer(711, signed=False)
    pcu_block = integer(712, signed=False)
    pcu_lock = integer(713, signed=False)
    auxiliary_1_input = enum_value(741, AuxiliaryInput)
    auxiliary_1_type = enum_value(744, AuxiliaryType)
    auxiliary_2_type = enum_value(745, AuxiliaryOutputType)
    auxiliary_3_type = enum_value(746, AuxiliaryOutputType)


class Identity(ISystemComponent):
    """Regulator identity and clock registers in the iSystem layout."""

    software_version = integer(600, signed=False)
    boiler_type = boiler_type_field()
    hour = integer(679, signed=False)
    minute = integer(680, signed=False)
    weekday = integer(681, signed=False)
    day = integer(682, signed=False)
    month = integer(683, signed=False)
    year = integer(684, signed=False)


class DiematicISystem(_Regulator):
    """A De Dietrich Diematic regulator addressed through the iSystem layout."""

    _mode_a_addr = _MODE_A_ISYSTEM
    _mode_b_addr = _MODE_B_ISYSTEM
    _mode_c_addr = _MODE_C_ISYSTEM
    _hot_water_addrs = (_MODE_B_ISYSTEM,)
    _nudges_panel = False
    _clock_policy = ClockPolicy(time_address=679, date_address=None, uses_marker=False)

    def __init__(
        self,
        unit: ModbusUnit,
        *,
        variant: DiematicVariant = DiematicVariant.DIEMATIC_3,
        force_circuit_a: bool = False,
        force_circuit_b: bool = False,
        force_circuit_c: bool = False,
    ) -> None:
        """Build the iSystem regulator over ``unit``."""
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
        self.outputs = Outputs(unit)
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
                "outputs": self.outputs,
                "diagnostics": self.diagnostics,
                "identity": self.identity,
                **{
                    f"schedules.{name}": program
                    for name, program in self.schedules.bundles().items()
                },
            },
            _READ_ONCE,
        )
        self.config._on_written = self._invalidate_read_once
        for program in self.schedules._programs.values():
            program._on_day_written = self._invalidate_read_once

    @property
    def circuit_a_present(self) -> bool:
        """Whether circuit A reports any live sensor reading or is forced present."""
        return (
            self._force_circuit_a
            or self.circuit_a.room_temp is not None
            or self.circuit_a.calc_temp is not None
            or self.circuit_a.supply_temp is not None
        )

    @property
    def circuit_b_present(self) -> bool:
        """Whether circuit B reports any live sensor reading or is forced present."""
        return (
            self._force_circuit_b
            or self.circuit_b.room_temp is not None
            or self.circuit_b.calc_temp is not None
            or self.circuit_b.supply_temp is not None
            or self.circuit_b.min_temp is not None
            or self.circuit_b.max_temp is not None
        )

    @property
    def circuit_c_present(self) -> bool:
        """Whether circuit C reports any live sensor reading or is forced present."""
        return (
            self._force_circuit_c
            or self.circuit_c.room_temp is not None
            or self.circuit_c.calc_temp is not None
        )

    @property
    def hot_water_present(self) -> bool:
        """Whether hot water reports a live temperature sensor reading."""
        return self.hot_water.temp is not None

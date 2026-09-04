"""Custom Diematic register fields and write validators."""

from __future__ import annotations

from datetime import time
from enum import IntEnum
from typing import Any

from modbus_connection.model import NumberField, RegisterField
from modbus_connection.model.fields import WriteValidator

DaySchedule = list[tuple[time, time]]
WeekSchedule = dict[int, DaySchedule]
_SLOTS_PER_REGISTER = 16
_REGISTERS_PER_DAY = 3
_DAYS = 7
_PROGRAMS = 4

_SIGN_BIT = 0x8000
_MAGNITUDE = 0x7FFF
# Raw values De Dietrich returns for an absent sensor: 0xFFFF and 0x8CCC (the
# latter confirmed live on this boiler at both smoke temp 454 and register 604).
_NO_SENSOR = frozenset((0xFFFF, 0x8CCC))


class Float10Field(RegisterField[float]):
    """A register in tenths of a unit with sign-magnitude negatives."""

    def decode(self, words: list[int], scale_exponent: int | None = None) -> Any:
        """Decode a tenths register, mapping absent-sensor sentinels to None."""
        raw = words[0]
        if raw in _NO_SENSOR:
            return None
        return -(raw & _MAGNITUDE) / 10 if raw >= _SIGN_BIT else raw / 10

    def encode(self, value: Any, scale_exponent: int | None = None) -> list[int]:
        """Encode a value in tenths, setting the sign bit for negatives."""
        tenths = round(abs(float(value)) * 10)
        if value < 0:
            tenths |= _SIGN_BIT
        return [tenths]


def float10(
    address: int,
    *,
    writable: bool | WriteValidator = False,
    force_fc16: bool = False,
    unit: str | None = None,
) -> Float10Field:
    """Return a signed tenths register where an absent-sensor sentinel means None."""
    return Float10Field(address, writable=writable, force_fc16=force_fc16, unit=unit)


class _MaskedEnum[E: IntEnum]:
    """Map a masked register value to an enum member."""

    def __init__(self, mask: int, enum_type: type[E]) -> None:
        self.mask = mask
        self.enum_type = enum_type

    def __call__(self, raw: int) -> E:
        return self.enum_type(raw & self.mask)


def masked_enum[E: IntEnum](
    address: int, mask: int, enum_type: type[E]
) -> NumberField[E]:
    """Build a register field holding one enum packed into ``mask`` of its bits."""
    return NumberField(address, signed=False, convert=_MaskedEnum(mask, enum_type))


class _FaultCode:
    """Map a fault code to its label, no-fault to None, unknown to the raw int."""

    def __init__(self, table: dict[int, str], ok: frozenset[int]) -> None:
        self.table = table
        self.ok = ok

    def __call__(self, raw: int) -> str | int | None:
        if raw in self.ok:
            return None
        return self.table.get(raw, raw)


def fault_code(
    address: int, table: dict[int, str], *, ok: tuple[int, ...] = (0xFFFF,)
) -> NumberField[str | int]:
    """Map a fault register to a label, no-fault codes to None, unknown to raw int."""
    return NumberField(address, signed=False, convert=_FaultCode(table, frozenset(ok)))


def code_map(address: int, table: dict[int, str]) -> NumberField[str | int]:
    """Map a register to a label from ``table``, unknown codes to the raw int."""
    return NumberField(address, signed=False, convert=_FaultCode(table, frozenset()))


def _slot_time(slot: int) -> time:
    minutes = slot * 30
    return time(minutes // 60 % 24, minutes % 60)


def _day_intervals(words: list[int]) -> DaySchedule:
    occupied: list[int] = []
    for register in words:
        for k in range(_SLOTS_PER_REGISTER):
            occupied.append(register >> (_SLOTS_PER_REGISTER - 1 - k) & 1)
    intervals: DaySchedule = []
    start: int | None = None
    total = _SLOTS_PER_REGISTER * _REGISTERS_PER_DAY
    for slot in range(total):
        if occupied[slot] and start is None:
            start = slot
        elif not occupied[slot] and start is not None:
            intervals.append((_slot_time(start), _slot_time(slot)))
            start = None
    if start is not None:
        intervals.append((_slot_time(start), _slot_time(total)))
    return intervals


class ScheduleDayField(RegisterField[DaySchedule]):
    """One day of a comfort schedule, 48 half-hour slots over three registers."""

    def decode(self, words: list[int], scale_exponent: int | None = None) -> Any:
        """Decode three registers into comfort periods, a set bit meaning comfort."""
        return _day_intervals(words)


def schedule_day(address: int) -> ScheduleDayField:
    """Return a read-only day of comfort periods spanning three registers."""
    return ScheduleDayField(address, count=_REGISTERS_PER_DAY)


class _TimeProgram:
    """Map a PROG.NUM register to the P1 to P4 program it selects."""

    def __call__(self, raw: int) -> int | None:
        if raw in _NO_SENSOR:
            return None
        return (raw & 0xFF) // _DAYS % _PROGRAMS + 1


def time_program(address: int) -> NumberField[int]:
    """Return the selected time program, 1 to 4, from a PROG.NUM register.

    The low byte is a row into a day table of four programs of seven days per
    circuit, so program = row // 7 % 4. Confirmed on the console for every value.
    """
    return NumberField(address, signed=False, convert=_TimeProgram())


def snap_clamp(step: float, low: float, high: float) -> WriteValidator:
    """Return a validator that snaps to ``step`` and clamps to ``[low, high]``."""

    def validate(value: Any) -> float:
        snapped = round(float(value) / step) * step
        return min(max(snapped, low), high)

    return validate

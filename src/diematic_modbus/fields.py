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
_NO_SENSOR = frozenset((0xFFFF, 0x8CCC))


class Float10Field(RegisterField[float | None]):
    """A value in tenths with a separate sign bit for negative numbers."""

    none_values: tuple[int, ...] = ()

    def decode(self, words: list[int], scale_exponent: int | None = None) -> Any:
        """Convert tenths to a number, returning None for known missing-value codes."""
        raw = words[0]
        if raw in _NO_SENSOR or raw in self.none_values:
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
    none_values: tuple[int, ...] = (),
) -> Float10Field:
    """Build a tenths field, optionally recognising extra missing-value codes."""
    field = Float10Field(address, writable=writable, force_fc16=force_fc16, unit=unit)
    field.none_values = none_values
    return field


class _MaskedEnum[E: IntEnum]:
    """Decode known modes and keep unknown mode bits as an integer."""

    def __init__(self, mask: int, enum_type: type[E]) -> None:
        self.mask = mask
        self.enum_type = enum_type

    def __call__(self, raw: int) -> E | int:
        value = raw & self.mask
        try:
            return self.enum_type(value)
        except ValueError:
            return value


def masked_enum[E: IntEnum](
    address: int, mask: int, enum_type: type[E]
) -> NumberField[E | int]:
    """Read mode bits as a known enum member or an unknown integer code."""
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
) -> NumberField[str | int | None]:
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


def _day_words(intervals: DaySchedule) -> list[int]:
    total = _SLOTS_PER_REGISTER * _REGISTERS_PER_DAY
    words = [0] * _REGISTERS_PER_DAY
    for start, end in intervals:
        low = (start.hour * 60 + start.minute) // 30
        high = total if end == time(0, 0) else (end.hour * 60 + end.minute) // 30
        if not 0 <= low < high <= total:
            raise ValueError(f"invalid comfort period {start}-{end}")
        for slot in range(low, high):
            register, offset = divmod(slot, _SLOTS_PER_REGISTER)
            words[register] |= 1 << (_SLOTS_PER_REGISTER - 1 - offset)
    return words


class ScheduleDayField(RegisterField[DaySchedule]):
    """One day of a comfort schedule, 48 half-hour slots over three registers."""

    def decode(self, words: list[int], scale_exponent: int | None = None) -> Any:
        """Decode three registers into comfort periods, a set bit meaning comfort."""
        return _day_intervals(words)

    def encode(self, value: Any, scale_exponent: int | None = None) -> list[int]:
        """Encode comfort periods into three registers, a set bit meaning comfort."""
        return _day_words(value)


def schedule_day(address: int, *, writable: bool = False) -> ScheduleDayField:
    """Return a day of comfort periods spanning three registers."""
    return ScheduleDayField(
        address, count=_REGISTERS_PER_DAY, writable=writable, force_fc16=writable
    )


class _TimeProgram:
    """Map a PROG.NUM register to the P1 to P4 program it selects."""

    def __call__(self, raw: int) -> int | None:
        if raw in _NO_SENSOR:
            return None
        return (raw & 0xFF) // _DAYS % _PROGRAMS + 1


def time_program(address: int) -> NumberField[int | None]:
    """Read the selected heating program as a number from 1 to 4."""
    return NumberField(address, signed=False, convert=_TimeProgram())


def snap_clamp(step: float, low: float, high: float) -> WriteValidator:
    """Round requests to ``step`` and keep them between ``low`` and ``high``."""

    def validate(value: Any) -> float:
        snapped = round(float(value) / step) * step
        return min(max(snapped, low), high)

    return validate

"""Coded values used across the Diematic register map."""

from __future__ import annotations

from enum import IntEnum


class DiematicVariant(IntEnum):
    """Which Diematic regulator generation is on the bus."""

    DIEMATIC_3 = 3
    DIEMATIC_4 = 4


class HeatingMode(IntEnum):
    """Heating-circuit mode held in the low bits of a mode register."""

    AUTO = 8
    TEMP_DAY = 36
    TEMP_NIGHT = 34
    PERM_DAY = 4
    PERM_NIGHT = 2
    ANTIFREEZE = 1
    HOLIDAY = 33


class HotWaterMode(IntEnum):
    """Hot-water mode held in bits 4 and 6 of a shared heating mode register."""

    AUTO = 0
    TEMP = 80
    PERM = 16


class HotWaterPriority(IntEnum):
    """Hot-water loading priority, decoded from the source parameter table."""

    TOTAL = 0
    SLIDING = 1
    NONE = 2


class CircuitType(IntEnum):
    """Configured heating circuit type."""

    DISABLED = 0
    DIRECT = 1
    THREE_WAY_VALVE = 2
    DIRECT_PLUS = 3
    THREE_WAY_VALVE_PLUS = 4
    SWIMMING_POOL = 5


class Language(IntEnum):
    """Controller language selection."""

    FRENCH = 0
    GERMAN = 1
    ENGLISH = 2
    POLISH = 3
    ITALIAN = 4
    SPANISH = 5
    DUTCH = 6
    RUSSIAN = 7
    TURKISH = 8
    CZECH = 9


class AuxiliaryType(IntEnum):
    """Configured auxiliary output type."""

    PROGRAM = 0
    PRIMARY_PUMP = 1
    THREE_WAY_VALVE_PUMP = 2
    DHW_LOAD = 3
    FAILURE = 4


class ActiveMode(IntEnum):
    """The mode a zone is currently running, from the iSystem active-mode registers."""

    ANTIFREEZE = 0
    NIGHT = 2
    DAY = 4

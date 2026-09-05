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
    RELATIVE = 1
    NON_PRIORITY = 2


class ActiveMode(IntEnum):
    """The mode a zone is currently running, from the iSystem active-mode registers."""

    ANTIFREEZE = 0
    NIGHT = 2
    DAY = 4

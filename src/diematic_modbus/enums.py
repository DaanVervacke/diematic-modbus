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


class HotWaterMode(IntEnum):
    """Hot-water mode held in bits 4 and 6 of the circuit A mode register."""

    AUTO = 0
    TEMP = 80
    PERM = 16


class ActiveMode(IntEnum):
    """The mode a zone is currently running, from the iSystem active-mode registers."""

    ANTIFREEZE = 0
    NIGHT = 2
    DAY = 4


class Alarm(IntEnum):
    """Condensing (DPSM) fault codes at register 465, unverified against hardware.

    The authoritative De Dietrich sheet leaves the DPSM fault table blank and the
    classic table is for non-DPSM boards, so these come from Benoit3's boiler.
    Unknown codes surface as raw integers rather than mapping here.
    """

    OK = 0
    RETURN_SENSOR_FAULT = 10
    LOW_WATER_PRESSURE = 21
    IGNITION_FAULT = 26
    PARASITE_FLAME = 27
    BOILER_STB = 28
    UNIT_RESET = 30
    SMOKE_SENSOR_FAULT = 31

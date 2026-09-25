"""Read and control Diematic regulators through a caller-owned Modbus connection."""

from ._base import UpdateReport
from .components import CircuitA, CircuitB, HotWater, Identity, Sensors, Settings
from .enums import (
    ActiveMode,
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
from .faults import C230_FAULTS, MODULENS_FAULTS
from .isystem import DiematicISystem, Schedules, WeekProgram
from .models import MODEL_CODES
from .probe import (
    DiematicDetection,
    DiematicProbeError,
    ProbeBlock,
    async_detect,
    async_probe,
)
from .regulator import Diematic

__all__ = [
    "C230_FAULTS",
    "MODEL_CODES",
    "MODULENS_FAULTS",
    "ActiveMode",
    "AuxiliaryType",
    "CircuitA",
    "CircuitB",
    "CircuitType",
    "Diematic",
    "DiematicDetection",
    "DiematicISystem",
    "DiematicProbeError",
    "DiematicVariant",
    "HeatingMode",
    "HotWater",
    "HotWaterMode",
    "HotWaterPriority",
    "Identity",
    "Language",
    "LegionellaProtection",
    "NightMode",
    "ProbeBlock",
    "Schedules",
    "Sensors",
    "Settings",
    "UpdateReport",
    "WeekProgram",
    "async_detect",
    "async_probe",
]

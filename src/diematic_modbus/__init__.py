"""Read and control Diematic regulators through a caller-owned Modbus connection."""

from ._base import UpdateReport
from .components import CircuitA, CircuitB, HotWater, Identity, Sensors, Settings
from .enums import (
    ActiveMode,
    DiematicVariant,
    HeatingMode,
    HotWaterMode,
    HotWaterPriority,
)
from .faults import MODULENS_FAULTS
from .isystem import DiematicISystem, Schedules, WeekProgram
from .models import MODEL_CODES
from .probe import DiematicDetection, DiematicProbeError, async_detect, async_probe
from .regulator import Diematic

__all__ = [
    "MODEL_CODES",
    "MODULENS_FAULTS",
    "ActiveMode",
    "CircuitA",
    "CircuitB",
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
    "Schedules",
    "Sensors",
    "Settings",
    "UpdateReport",
    "WeekProgram",
    "async_detect",
    "async_probe",
]

"""The top-level Diematic regulator object."""

from __future__ import annotations

from datetime import datetime

from modbus_connection import ModbusUnit

from ._base import _Regulator
from .components import CircuitA, CircuitB, HotWater, Identity, Sensors, Settings
from .enums import DiematicVariant

_CLOCK_TIME = 4
_CLOCK_DATE = 108
_CLOCK_FLAG = 0xFF00
_READ_ONCE: frozenset[str] = frozenset()


class Diematic(_Regulator):
    """A De Dietrich Diematic heating regulator on a Modbus unit."""

    def __init__(
        self,
        unit: ModbusUnit,
        *,
        variant: DiematicVariant = DiematicVariant.DIEMATIC_3,
        force_circuit_a: bool = False,
        force_circuit_b: bool = False,
    ) -> None:
        """Build the regulator over ``unit``."""
        self.variant = variant
        self._force_circuit_a = force_circuit_a
        self._force_circuit_b = force_circuit_b
        self.sensors = Sensors(unit)
        self.hot_water = HotWater(unit)
        self.circuit_a = CircuitA(unit)
        self.circuit_b = CircuitB(unit)
        self.settings = Settings(unit)
        self.identity = Identity(unit)
        self._install_engine(
            unit,
            {
                "sensors": self.sensors,
                "hot_water": self.hot_water,
                "circuit_a": self.circuit_a,
                "circuit_b": self.circuit_b,
                "settings": self.settings,
                "identity": self.identity,
            },
            _READ_ONCE,
        )

    @property
    def circuit_a_present(self) -> bool:
        """Whether circuit A reports a room temperature or is forced present."""
        return self._force_circuit_a or self.circuit_a.room_temp is not None

    @property
    def circuit_b_present(self) -> bool:
        """Whether circuit B reports a room temperature or is forced present."""
        return self._force_circuit_b or self.circuit_b.room_temp is not None

    async def set_clock(self, moment: datetime) -> None:
        """Set the regulator clock from ``moment``."""
        time_block = [
            _CLOCK_FLAG | (moment.hour & 0xFF),
            _CLOCK_FLAG | (moment.minute & 0xFF),
            _CLOCK_FLAG | (moment.isoweekday() & 0xFF),
        ]
        date_block = [
            _CLOCK_FLAG | (moment.day & 0xFF),
            _CLOCK_FLAG | (moment.month & 0xFF),
            _CLOCK_FLAG | (moment.year % 100 & 0xFF),
        ]
        await self._unit.write_registers(_CLOCK_TIME, time_block)
        await self._unit.write_registers(_CLOCK_DATE, date_block)

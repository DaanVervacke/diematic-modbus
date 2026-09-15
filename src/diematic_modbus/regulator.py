"""The top-level Diematic regulator object."""

from __future__ import annotations

from modbus_connection import ModbusUnit

from ._base import ClockPolicy, _Regulator
from .components import CircuitA, CircuitB, HotWater, Identity, Sensors, Settings
from .enums import DiematicVariant

_READ_ONCE: frozenset[str] = frozenset()


class Diematic(_Regulator):
    """A De Dietrich Diematic heating regulator on a Modbus unit."""

    _clock_policy = ClockPolicy(time_address=4, date_address=108, uses_marker=True)

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
        """Whether circuit A reports any live sensor reading or is forced present."""
        return (
            self._force_circuit_a
            or self.circuit_a.room_temp is not None
            or self.circuit_a.calc_temp is not None
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

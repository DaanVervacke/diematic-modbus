"""Shared polling and mode-write engine for the Diematic regulator layouts."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from modbus_connection import ModbusConnectionError, ModbusError, ModbusUnit
from modbus_connection.model import Component, ComponentGroup

from .enums import DiematicVariant, HeatingMode, HotWaterMode

_MODE_A = 17
_MODE_B = 26
_HEATING_MASK = 0x2F
_HOT_WATER_MASK = 0x50
_ANTIFREEZE_DAYS = 13


@dataclass(frozen=True)
class UpdateReport:
    """The outcome of a poll: which bundles refreshed and which failed."""

    updated: frozenset[str]
    failed: dict[str, ModbusError]

    @property
    def complete(self) -> bool:
        """Whether every bundle refreshed."""
        return not self.failed


class _Regulator:
    """Pooled polling, partial-failure reporting, and mode writes over a unit."""

    variant: DiematicVariant
    _mode_a_addr: int = _MODE_A
    _mode_b_addr: int = _MODE_B
    _hot_water_addr: int = _MODE_A
    _nudges_panel: bool = True
    _unit: ModbusUnit
    _bundles: dict[str, Component]
    _poll: list[Component]
    _poll_group: ComponentGroup
    _names: dict[int, str]
    _pending_once: dict[str, Component]

    def _install_engine(
        self,
        unit: ModbusUnit,
        bundles: dict[str, Component],
        read_once: frozenset[str],
    ) -> None:
        """Wire the bundles into a pooled poll group and a read-once set."""
        self._unit = unit
        self._bundles = bundles
        self._poll = [c for n, c in bundles.items() if n not in read_once]
        self._poll_group = ComponentGroup(unit, self._poll)
        self._names = {id(c): n for n, c in bundles.items()}
        self._pending_once = {n: bundles[n] for n in read_once}

    async def async_update(self) -> UpdateReport:
        """Refresh every bundle, keeping stale values for any that fail."""
        updated: set[str] = set()
        failed: dict[str, ModbusError] = {}
        await self._poll_bundles(updated, failed)
        await self._poll_read_once(updated, failed)
        return UpdateReport(frozenset(updated), failed)

    async def _poll_bundles(
        self, updated: set[str], failed: dict[str, ModbusError]
    ) -> None:
        try:
            await self._poll_group.async_update()
        except ModbusConnectionError:
            raise
        except ModbusError:
            await self._poll_individually(updated, failed)
            return
        updated.update(self._names[id(c)] for c in self._poll)

    async def _poll_individually(
        self, updated: set[str], failed: dict[str, ModbusError]
    ) -> None:
        for component in self._poll:
            name = self._names[id(component)]
            try:
                await component.async_update()
            except ModbusConnectionError:
                raise
            except ModbusError as err:
                failed[name] = err
            else:
                updated.add(name)

    async def _poll_read_once(
        self, updated: set[str], failed: dict[str, ModbusError]
    ) -> None:
        for name, component in list(self._pending_once.items()):
            try:
                await component.async_update()
            except ModbusConnectionError:
                raise
            except ModbusError as err:
                failed[name] = err
            else:
                updated.add(name)
                del self._pending_once[name]

    async def async_read_raw(self) -> dict[str, dict[int, int | bool]]:
        """Read every register this layout serves, undecoded, for diagnostics."""
        group = ComponentGroup(self._unit, list(self._bundles.values()))
        return await group.async_read_raw(notify=False)

    async def set_circuit_a_mode(self, mode: HeatingMode) -> None:
        """Set heating circuit A mode, ignored where circuit A is absent."""
        await self._write_mode(self._mode_a_addr, _HEATING_MASK, int(mode))

    async def set_circuit_b_mode(self, mode: HeatingMode) -> None:
        """Set heating circuit B mode."""
        await self._write_mode(self._mode_b_addr, _HEATING_MASK, int(mode))

    async def set_hot_water_mode(self, mode: HotWaterMode) -> None:
        """Set hot-water mode, ignored where the target register is absent."""
        await self._write_mode(self._hot_water_addr, _HOT_WATER_MASK, int(mode))

    async def _write_mode(self, address: int, mask: int, code: int) -> None:
        (current,) = await self._unit.read_holding_registers(address, 1)
        await self._unit.write_registers(address, [(current & ~mask) | code])
        if self._nudges_panel and self.variant is DiematicVariant.DIEMATIC_4:
            await self._nudge_panel()

    async def _nudge_panel(self) -> None:
        # ponytail: firmware-empirical panel refresh on Diematic 4. The exact
        # per-mode antifreeze-day sequence is not ported, revisit on hardware.
        await self._unit.write_registers(_ANTIFREEZE_DAYS, [1])
        await asyncio.sleep(0.5)
        await self._unit.write_registers(_ANTIFREEZE_DAYS, [0])

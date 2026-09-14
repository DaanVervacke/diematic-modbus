"""Shared polling and mode-write engine for the Diematic regulator layouts."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum
from typing import ClassVar

from modbus_connection import (
    ModbusConnectionError,
    ModbusError,
    ModbusTimeoutError,
    ModbusUnit,
    ServerDeviceBusyError,
)
from modbus_connection.model import Component, ComponentGroup, Raw

from .enums import DiematicVariant, HeatingMode, HotWaterMode

_MESSAGE_SPACING = 0.05
_MODE_A = 17
_MODE_B = 26
_HEATING_MASK = 0x2F
_HOT_WATER_MASK = 0x50
_ANTIFREEZE_DAYS = 13
_CLOCK_FLAG = 0xFF00


@dataclass(frozen=True)
class ClockPolicy:
    """Where and how to write the regulator clock."""

    time_address: int
    date_address: int | None  # None when time and date share one register block.
    uses_marker: bool  # True for Diematic (0xFF00 marker per word).


@dataclass(frozen=True)
class UpdateReport:
    """The outcome of a poll: which bundles refreshed and which failed."""

    updated: frozenset[str]
    failed: dict[str, ModbusError]

    @property
    def complete(self) -> bool:
        """Whether this poll reported no read failures."""
        return not self.failed


class _Regulator:
    """Pooled polling, partial-failure reporting, and mode writes over a unit."""

    variant: DiematicVariant
    _mode_a_addr: int = _MODE_A
    _mode_b_addr: int = _MODE_B
    _mode_c_addr: int | None = None
    _hot_water_addrs: tuple[int, ...] = (_MODE_A, _MODE_B)
    _nudges_panel: bool = True
    _clock_policy: ClassVar[ClockPolicy]
    _unit: ModbusUnit
    _bundles: dict[str, Component]
    _poll: list[Component]
    _poll_group: ComponentGroup
    _names: dict[int, str]
    _read_once: frozenset[str]
    _pending_once: dict[str, Component]
    _write_lock: asyncio.Lock

    def _install_engine(
        self,
        unit: ModbusUnit,
        bundles: dict[str, Component],
        read_once: frozenset[str],
    ) -> None:
        """Group bundles for regular polling or a single successful read."""
        self._unit = unit
        self._bundles = bundles
        unit.set_message_spacing(_MESSAGE_SPACING)
        self._write_lock = asyncio.Lock()
        self._poll = [c for n, c in bundles.items() if n not in read_once]
        self._poll_group = ComponentGroup(unit, self._poll)
        self._names = {id(c): n for n, c in bundles.items()}
        self._read_once = read_once
        self._pending_once = {n: bundles[n] for n in read_once}

    async def async_update(self) -> UpdateReport:
        """Poll bundles, skipping cached bundles and keeping stale values on failure."""
        updated: set[str] = set()
        failed: dict[str, ModbusError] = {}
        await self._poll_bundles(updated, failed)
        await self._poll_read_once(updated, failed)
        return UpdateReport(frozenset(updated), failed)

    async def _poll_bundles(
        self, updated: set[str], failed: dict[str, ModbusError]
    ) -> None:
        for _ in range(2):
            try:
                await self._poll_group.async_update()
                break
            except ModbusConnectionError:
                raise
            except (ModbusTimeoutError, ServerDeviceBusyError):
                continue
            except ModbusError:
                await self._poll_individually(updated, failed)
                return
        else:
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

    async def async_read_raw(self) -> Raw:
        """Read mapped registers raw, refreshing decoded values as a side effect."""
        group = ComponentGroup(self._unit, list(self._bundles.values()))
        return await group.async_read_raw(notify=False)

    def _invalidate_read_once(self, component: Component) -> None:
        """Re-arm a cached read-once bundle so the next update rereads it."""
        name = self._names[id(component)]
        if name in self._read_once:
            self._pending_once[name] = self._bundles[name]

    async def set_circuit_a_mode(self, mode: HeatingMode) -> None:
        """Set heating circuit A mode, rejecting HOLIDAY as panel-only."""
        await self._write_mode((self._mode_a_addr,), _HEATING_MASK, HeatingMode, mode)

    async def set_circuit_b_mode(self, mode: HeatingMode) -> None:
        """Set heating circuit B mode, rejecting HOLIDAY as panel-only."""
        await self._write_mode((self._mode_b_addr,), _HEATING_MASK, HeatingMode, mode)

    async def set_circuit_c_mode(self, mode: HeatingMode) -> None:
        """Set heating circuit C mode. HOLIDAY is rejected as panel-only."""
        if self._mode_c_addr is None:
            raise AttributeError(
                f"{type(self).__name__} has no circuit C; only iSystem does"
            )
        await self._write_mode((self._mode_c_addr,), _HEATING_MASK, HeatingMode, mode)

    async def set_hot_water_mode(self, mode: HotWaterMode) -> None:
        """Set hot-water mode across its layout's registers, preserving heating bits."""
        await self._write_mode(
            self._hot_water_addrs, _HOT_WATER_MASK, HotWaterMode, mode
        )

    async def set_clock(self, moment: datetime) -> None:
        """Set the regulator clock from moment, using the layout's clock policy."""
        async with self._write_lock:
            if self._clock_policy.uses_marker:
                assert self._clock_policy.date_address is not None
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
                await self._unit.write_registers(
                    self._clock_policy.time_address, time_block
                )
                await self._unit.write_registers(
                    self._clock_policy.date_address, date_block
                )
            else:
                block = [
                    moment.hour,
                    moment.minute,
                    moment.isoweekday(),
                    moment.day,
                    moment.month,
                    moment.year % 100,
                ]
                await self._unit.write_registers(self._clock_policy.time_address, block)

    async def _write_mode(
        self, addresses: tuple[int, ...], mask: int, enum: type[IntEnum], mode: int
    ) -> None:
        """Validate a mode, then read every target register and write them together."""
        async with self._write_lock:
            validated = enum(mode)
            if validated is HeatingMode.HOLIDAY:
                raise ValueError(
                    "Holiday mode is read-only. Set it on the control panel."
                )
            code = int(validated)
            currents: list[int] = []
            for address in addresses:
                (current,) = await self._unit.read_holding_registers(address, 1)
                currents.append(current)
            for address, current in zip(addresses, currents, strict=True):
                await self._unit.write_registers(address, [(current & ~mask) | code])
            if self._nudges_panel and self.variant is DiematicVariant.DIEMATIC_4:
                await self._nudge_panel()

    async def _nudge_panel(self) -> None:
        await self._unit.write_registers(_ANTIFREEZE_DAYS, [1])
        await asyncio.sleep(0.5)
        await self._unit.write_registers(_ANTIFREEZE_DAYS, [0])

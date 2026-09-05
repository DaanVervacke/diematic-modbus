#!/usr/bin/env python3
"""Read a Diematic regulator on the wire and print every value.

uv run scripts/read_diematic.py 192.168.1.50 --port 502 --unit 10
uv run scripts/read_diematic.py 192.168.1.254 --port 4196 --unit 10 --layout isystem
uv run scripts/read_diematic.py /dev/ttyUSB0 --transport serial --unit 10 --layout both
uv run scripts/read_diematic.py 192.168.1.50 --debug --probe-write
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import time

from modbus_connection import ModbusError, ModbusUnit
from modbus_connection.cli_helper import (
    add_connection_args,
    connect_from_args,
    print_component,
)

from diematic_modbus import Diematic, DiematicISystem, DiematicVariant
from diematic_modbus.isystem import SCHEDULE_BASES

type Regulator = Diematic | DiematicISystem

_MESSAGE_SPACING = 0.05
_PROBE_FIELD = "day_target"
_MIDNIGHT = time(0, 0)
_WEEKDAYS = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)
_BASE_BUNDLES = (
    "sensors",
    "hot_water",
    "circuit_a",
    "circuit_b",
    "settings",
    "identity",
)
_ISYSTEM_BUNDLES = (
    "sensors",
    "hot_water",
    "circuit_a",
    "circuit_b",
    "circuit_c",
    "settings",
    "config",
    "diagnostics",
    "identity",
)


def _format_range(start: time, end: time) -> str:
    """Format one comfort period, showing a midnight end as 24:00."""
    tail = "24:00" if end == _MIDNIGHT else end.strftime("%H:%M")
    return f"{start.strftime('%H:%M')}-{tail}"


def _print_schedules(boiler: DiematicISystem) -> None:
    """Print the weekly comfort schedules, one line per weekday."""
    for name in SCHEDULE_BASES:
        week = getattr(boiler.schedules, name)
        title = f"schedules.{name}"
        print(f"\n{title}")
        print("-" * len(title))
        for day in range(1, 8):
            ranges = week.get(day, [])
            shown = ", ".join(_format_range(s, e) for s, e in ranges) or "off"
            print(f"  {_WEEKDAYS[day - 1].ljust(9)}  {shown}")


def _build(
    layout: str, unit: ModbusUnit, variant: DiematicVariant
) -> list[tuple[str, Regulator]]:
    """Return the (kind, regulator) pairs to dump for ``layout``."""
    pairs: list[tuple[str, Regulator]] = []
    if layout in ("base", "both"):
        pairs.append(("base", Diematic(unit, variant=variant)))
    if layout in ("isystem", "both"):
        pairs.append(("isystem", DiematicISystem(unit, variant=variant)))
    return pairs


async def _dump(kind: str, regulator: Regulator) -> None:
    """Refresh and print every bundle for one layout."""
    report = await regulator.async_update()
    bundles = _ISYSTEM_BUNDLES if kind == "isystem" else _BASE_BUNDLES
    print(f"\n=== {kind} layout ===")
    if not report.complete:
        print("WARNING: bundles that did not refresh (values below are stale):")
        for name, err in sorted(report.failed.items()):
            print(f"  {name}: {err}")
    for name in bundles:
        print_component(getattr(regulator, name), title=name)
    print(f"\ncircuit_a_present = {regulator.circuit_a_present}")
    print(f"circuit_b_present = {regulator.circuit_b_present}")
    if isinstance(regulator, DiematicISystem):
        print(f"circuit_c_present = {regulator.circuit_c_present}")
        _print_schedules(regulator)


async def _probe_write(regulator: Regulator) -> None:
    """Write the hot-water day setpoint back to its own value."""
    current = regulator.hot_water.day_target
    if current is None:
        print("\nprobe-write skipped: hot-water day setpoint reads no value")
        return
    print(f"\nprobe-write: writing hot-water day setpoint back as {current} °C")
    await regulator.hot_water.write(_PROBE_FIELD, current)
    await regulator.hot_water.async_update()
    readback = regulator.hot_water.day_target
    ok = "ok" if readback == current else f"MISMATCH (read back {readback})"
    print(f"probe-write: {ok}")


async def _main() -> int:
    parser = argparse.ArgumentParser(description="Read a Diematic regulator.")
    add_connection_args(parser, connections=(("tcp", "rtu"), ("serial", "rtu")))
    parser.add_argument("--unit", type=int, default=10)
    parser.add_argument("--variant", type=int, choices=[3, 4], default=3)
    parser.add_argument("--layout", choices=["base", "isystem", "both"], default="base")
    parser.add_argument(
        "--debug", action="store_true", help="log Modbus protocol traffic to stderr"
    )
    parser.add_argument(
        "--probe-write",
        action="store_true",
        help="write the hot-water day setpoint back to its own value (no net change)",
    )
    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
        for name in ("modbus_connection", "tmodbus"):
            logging.getLogger(name).setLevel(logging.DEBUG)

    try:
        conn = await connect_from_args(args, message_spacing=_MESSAGE_SPACING)
    except ModbusError as err:
        print(f"Connect failed: {err}")
        return 1

    unit = conn.for_unit(args.unit)
    regulators = _build(args.layout, unit, DiematicVariant(args.variant))
    try:
        for kind, regulator in regulators:
            await _dump(kind, regulator)
    except ModbusError as err:
        print(f"Read failed: {err}")
        print("Check the wiring, unit id, transport and (for a gateway) that it")
        print("forwards RTU frames. Re-run with --debug to see the raw traffic.")
        await conn.close()
        return 1

    if args.probe_write:
        try:
            await _probe_write(regulators[-1][1])
        except ModbusError as err:
            print(f"probe-write failed: {err}")

    await conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))

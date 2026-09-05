#!/usr/bin/env python3
"""Read boiler values for comparison with the panel, writing only if requested."""

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
_BUNDLE_TITLES = {
    "sensors": "Boiler readings",
    "hot_water": "Hot water",
    "circuit_a": "Heating circuit A",
    "circuit_b": "Heating circuit B",
    "circuit_c": "Heating circuit C",
    "settings": "Temperature settings",
    "config": "Installer values (cached after a successful read)",
    "diagnostics": "Diagnostics (mostly numeric codes)",
    "identity": "Reported type and clock",
}


def _format_range(start: time, end: time) -> str:
    """Format one comfort period, showing a midnight end as 24:00."""
    tail = "24:00" if end == _MIDNIGHT else end.strftime("%H:%M")
    return f"{start.strftime('%H:%M')}-{tail}"


def _print_schedules(boiler: DiematicISystem) -> None:
    """Print the weekly comfort schedules, one line per weekday."""
    for name in SCHEDULE_BASES:
        week = getattr(boiler.schedules, name)
        title = f"{name.replace('_', ' ').title()} schedule (schedules.{name})"
        print(f"\n{title}")
        print("-" * len(title))
        for day in range(1, 8):
            ranges = week.get(day, [])
            shown = (
                ", ".join(_format_range(s, e) for s, e in ranges)
                or "no comfort periods"
            )
            print(f"  {_WEEKDAYS[day - 1].ljust(9)}  {shown}")


def _build(
    layout: str, unit: ModbusUnit, variant: DiematicVariant
) -> list[tuple[str, Regulator]]:
    """Build the requested layouts using the same boiler connection."""
    pairs: list[tuple[str, Regulator]] = []
    if layout in ("base", "both"):
        pairs.append(("base", Diematic(unit, variant=variant)))
    if layout in ("isystem", "both"):
        pairs.append(("isystem", DiematicISystem(unit, variant=variant)))
    return pairs


async def _dump(kind: str, regulator: Regulator) -> bool:
    """Read one layout and print its values, including any failed reads."""
    report = await regulator.async_update()
    bundles = _ISYSTEM_BUNDLES if kind == "isystem" else _BASE_BUNDLES
    print(f"\n=== {'iSystem' if kind == 'isystem' else 'Base'} layout ===")
    if not report.complete:
        print("WARNING: these groups could not be read. Their values may be missing")
        print("or out of date. An empty schedule in a failed group is not reliable.")
        for name, err in sorted(report.failed.items()):
            print(f"  {name}: {err}")
    for name in bundles:
        title = _BUNDLE_TITLES[name]
        print_component(getattr(regulator, name), title=f"{title} ({name})")
    print("\nRoom-temperature readings available (not a hardware inventory):")
    print(f"  circuit_a_present = {regulator.circuit_a_present}")
    print(f"  circuit_b_present = {regulator.circuit_b_present}")
    if isinstance(regulator, DiematicISystem):
        print(f"  circuit_c_present = {regulator.circuit_c_present}")
        print(
            "\nHeating schedules below show P4, not necessarily the selected program."
        )
        _print_schedules(regulator)
    return report.complete


async def _probe_write(regulator: Regulator) -> bool:
    """Write a freshly read target only if validation leaves it unchanged."""
    await regulator.hot_water.async_update()
    current = regulator.hot_water.day_target
    if current is None:
        print("\nWrite check skipped: no hot-water day target was available.")
        return False
    field = type(regulator.hot_water).day_target
    requested = field.writable(current) if callable(field.writable) else current
    if requested != current:
        print(
            f"\nWrite check skipped: write rules would change {current} °C "
            f"to {requested} °C. Nothing was written."
        )
        return False
    print(f"\nWrite check: resubmitting the hot-water day target ({current} °C).")
    print("This is a real write. Check the panel afterwards and restore the")
    print("original setting if it changed. The script has no separate restore step.")
    await regulator.hot_water.write(_PROBE_FIELD, current)
    await regulator.hot_water.async_update()
    readback = regulator.hot_water.day_target
    ok = (
        "the value read back matches."
        if readback == current
        else f"MISMATCH: read back {readback}, expected {current} °C."
    )
    print(f"Write check: {ok}")
    print("A matching value does not prove that a different target would be kept.")
    return readback == current


async def _main() -> int:
    parser = argparse.ArgumentParser(
        description="Read your Diematic boiler once for comparison with its panel.",
        epilog=(
            "Nothing is written unless you add --probe-write. Network gateways must "
            "forward RTU messages unchanged. "
            "See README.md for setup and reporting results."
        ),
    )
    add_connection_args(parser, connections=(("tcp", "rtu"), ("serial", "rtu")))
    parser.add_argument(
        "--unit", type=int, default=10, help="controller's Modbus address (default: 10)"
    )
    parser.add_argument(
        "--variant",
        type=int,
        choices=[3, 4],
        default=3,
        help="mode-write variant, unused by this read/setpoint check (default: 3)",
    )
    parser.add_argument(
        "--layout",
        choices=["base", "isystem", "both"],
        default="base",
        help=(
            "read the Diematic 3/4 base layout, iSystem, or both in that order "
            "(default: base)"
        ),
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="include sent/received messages for troubleshooting",
    )
    parser.add_argument(
        "--probe-write",
        action="store_true",
        help=(
            "write back a freshly read hot-water day target only if write rules "
            "leave it unchanged (real write, uses iSystem when --layout both)"
        ),
    )
    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
        for name in ("modbus_connection", "tmodbus"):
            logging.getLogger(name).setLevel(logging.DEBUG)

    try:
        conn = await connect_from_args(args, message_spacing=_MESSAGE_SPACING)
    except ModbusError as err:
        print(f"Could not connect to the boiler: {err}")
        return 1

    try:
        unit = conn.for_unit(args.unit)
        regulators = _build(args.layout, unit, DiematicVariant(args.variant))
        complete = True
        try:
            for kind, regulator in regulators:
                if not await _dump(kind, regulator):
                    complete = False
        except ModbusError as err:
            print(f"Read failed: {err}")
            print("Check the connection settings and controller address (--unit).")
            print("A network gateway must forward RTU messages unchanged.")
            print("Retry a read-only run after a timeout. Add --debug for details.")
            return 1
        if not complete:
            if args.probe_write:
                print("\nWrite check skipped: not all requested reads succeeded.")
            return 1
        if args.probe_write:
            try:
                if not await _probe_write(regulators[-1][1]):
                    return 1
            except ModbusError as err:
                print(f"Write check failed: {err}")
                print("Check the target on the panel. A failed readback does not prove")
                print("the write was rejected. Restore the original target if needed.")
                return 1
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))

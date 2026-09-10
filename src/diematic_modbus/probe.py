"""Detect the register layout of a Diematic regulator."""

from modbus_connection import (
    IllegalDataAddressError,
    IllegalFunctionError,
    ModbusError,
    ModbusUnit,
)

from .enums import DiematicVariant
from .isystem import DiematicISystem
from .regulator import Diematic

_BASE_IDENTITY_BLOCKS = ((3, 4), (108, 3), (457, 1))
_ISYSTEM_IDENTITY_BLOCKS = ((600, 1), (679, 6))
_BASE_VARIANTS = {
    code: variant
    for code, variant in ((code, DiematicVariant.DIEMATIC_3) for code in (20, 22))
} | {24: DiematicVariant.DIEMATIC_4}


class UnsupportedDiematicError(ModbusError):
    """The regulator reports an unsupported device type."""


async def _async_read_blocks(
    unit: ModbusUnit, blocks: tuple[tuple[int, int], ...]
) -> tuple[dict[int, list[int]], ModbusError | None]:
    values: dict[int, list[int]] = {}
    error: ModbusError | None = None
    for address, count in blocks:
        try:
            values[address] = await unit.read_holding_registers(address, count)
        except (IllegalDataAddressError, IllegalFunctionError) as err:
            error = error or err
    return values, error


async def async_probe(unit: ModbusUnit) -> Diematic | DiematicISystem:
    """Detect the regulator layout and return a configured device."""
    base_values, base_error = await _async_read_blocks(unit, _BASE_IDENTITY_BLOCKS)
    _isystem_values, isystem_error = await _async_read_blocks(
        unit, _ISYSTEM_IDENTITY_BLOCKS
    )

    type_values = base_values.get(457, None)
    if type_values is None:
        type_code = None
        variant = None
    else:
        type_code = type_values[0]
        variant = _BASE_VARIANTS.get(type_code)
    if type_code is not None and variant is None:
        raise UnsupportedDiematicError(f"Unsupported Diematic device type {type_code}")

    if isystem_error is None:
        return DiematicISystem(unit, variant=variant or DiematicVariant.DIEMATIC_3)

    if base_error is None and variant is not None:
        return Diematic(unit, variant=variant)

    if base_error is not None:
        raise base_error
    raise isystem_error

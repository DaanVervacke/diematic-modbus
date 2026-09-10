"""Detect the register layout of a Diematic regulator."""

from dataclasses import dataclass

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
_BASE_VARIANTS = {code: DiematicVariant.DIEMATIC_3 for code in (20, 22)} | {
    24: DiematicVariant.DIEMATIC_4
}


@dataclass(frozen=True)
class ProbeBlock:
    """Record one identity block read."""

    address: int
    count: int
    values: tuple[int, ...] | None
    error: ModbusError | None

    @property
    def outcome(self) -> str:
        """Return the stable outcome name for this block."""
        if self.error is None:
            return "success"
        if isinstance(self.error, (IllegalDataAddressError, IllegalFunctionError)):
            return "unsupported"
        return "error"

    @property
    def error_type(self) -> str | None:
        """Return the exception class name when the block failed."""
        return type(self.error).__name__ if self.error is not None else None

    @property
    def error_message(self) -> str | None:
        """Return the exception text when the block failed."""
        return str(self.error) if self.error is not None else None


@dataclass(frozen=True)
class DiematicDetection:
    """Describe a Diematic detection attempt and its evidence."""

    device: Diematic | DiematicISystem | None
    raw_type_code: int | None
    variant: DiematicVariant | None
    isystem_detected: bool
    base_probe: tuple[ProbeBlock, ...]
    isystem_probe: tuple[ProbeBlock, ...]


class DiematicProbeError(ModbusError):
    """The regulator could not be identified from the probe evidence."""

    def __init__(self, detection: DiematicDetection) -> None:
        """Initialize with the failed detection evidence."""
        self.detection = detection
        super().__init__("Could not identify the Diematic register layout")


async def _async_read_blocks(
    unit: ModbusUnit, blocks: tuple[tuple[int, int], ...]
) -> tuple[ProbeBlock, ...]:
    results: list[ProbeBlock] = []
    for address, count in blocks:
        try:
            values = tuple(await unit.read_holding_registers(address, count))
        except ModbusError as err:
            results.append(ProbeBlock(address, count, None, err))
        else:
            results.append(ProbeBlock(address, count, values, None))
    return tuple(results)


def _block_values(
    blocks: tuple[ProbeBlock, ...], address: int
) -> tuple[int, ...] | None:
    for block in blocks:
        if block.address == address:
            return block.values
    return None


async def async_detect(unit: ModbusUnit) -> DiematicDetection:
    """Detect a layout and retain all identity probe evidence."""
    base_probe = await _async_read_blocks(unit, _BASE_IDENTITY_BLOCKS)
    isystem_probe = await _async_read_blocks(unit, _ISYSTEM_IDENTITY_BLOCKS)
    type_values = _block_values(base_probe, 457)
    type_code = type_values[0] if type_values is not None else None
    variant = _BASE_VARIANTS.get(type_code) if type_code is not None else None
    errors = tuple(
        block for block in (*base_probe, *isystem_probe) if block.outcome == "error"
    )
    isystem_detected = all(block.outcome == "success" for block in isystem_probe)
    base_detected = variant is not None and all(
        block.outcome == "success" for block in base_probe
    )
    if type_code is not None and variant is None:
        raise DiematicProbeError(
            DiematicDetection(
                None,
                type_code,
                variant,
                isystem_detected,
                base_probe,
                isystem_probe,
            )
        )
    if isystem_detected:
        return DiematicDetection(
            DiematicISystem(unit, variant=variant or DiematicVariant.DIEMATIC_3),
            type_code,
            variant,
            True,
            base_probe,
            isystem_probe,
        )
    if base_detected:
        assert variant is not None
        return DiematicDetection(
            Diematic(unit, variant=variant),
            type_code,
            variant,
            False,
            base_probe,
            isystem_probe,
        )
    if errors:
        raise DiematicProbeError(
            DiematicDetection(
                None,
                type_code,
                variant,
                False,
                base_probe,
                isystem_probe,
            )
        )
    raise DiematicProbeError(
        DiematicDetection(
            None,
            type_code,
            variant,
            False,
            base_probe,
            isystem_probe,
        )
    )


async def async_probe(unit: ModbusUnit) -> Diematic | DiematicISystem:
    """Detect the regulator layout and return a configured device."""
    detection = await async_detect(unit)
    assert detection.device is not None
    return detection.device

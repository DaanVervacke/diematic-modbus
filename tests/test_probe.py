import pytest
from modbus_connection import ModbusConnectionError, ModbusTimeoutError
from modbus_connection.exceptions import IllegalDataAddressError

from diematic_modbus import (
    Diematic,
    DiematicISystem,
    DiematicVariant,
    UnsupportedDiematicError,
    async_probe,
)


def _seed_base(unit, type_code: int) -> None:
    unit.holding.update(
        {
            3: 400,
            4: 14,
            5: 30,
            6: 2,
            108: 10,
            109: 9,
            110: 25,
            457: type_code,
        }
    )


def _seed_isystem(unit) -> None:
    unit.holding.update({600: 412, 679: 12, 680: 30, 681: 2, 682: 10, 683: 9, 684: 25})


@pytest.mark.parametrize(
    ("type_code", "variant"),
    [
        pytest.param(20, DiematicVariant.DIEMATIC_3, id="diematic_3"),
        pytest.param(22, DiematicVariant.DIEMATIC_3, id="diematic_m3"),
        pytest.param(24, DiematicVariant.DIEMATIC_4, id="diematic_4"),
    ],
)
async def test_probe_base_layout(mock_modbus_unit, type_code, variant):
    _seed_base(mock_modbus_unit, type_code)
    mock_modbus_unit.fail_read(600, IllegalDataAddressError())

    device = await async_probe(mock_modbus_unit)

    assert isinstance(device, Diematic)
    assert device.variant is variant


@pytest.mark.parametrize("type_code", [20, 24], ids=["diematic_3", "diematic_4"])
async def test_probe_isystem_layout(mock_modbus_unit, type_code):
    _seed_base(mock_modbus_unit, type_code)
    _seed_isystem(mock_modbus_unit)

    device = await async_probe(mock_modbus_unit)

    assert isinstance(device, DiematicISystem)
    assert device.variant is (
        DiematicVariant.DIEMATIC_3 if type_code == 20 else DiematicVariant.DIEMATIC_4
    )


async def test_probe_accepts_isystem_without_base_identity(mock_modbus_unit):
    _seed_isystem(mock_modbus_unit)
    mock_modbus_unit.fail_read(3, IllegalDataAddressError())
    mock_modbus_unit.fail_read(108, IllegalDataAddressError())
    mock_modbus_unit.fail_read(457, IllegalDataAddressError())

    device = await async_probe(mock_modbus_unit)

    assert isinstance(device, DiematicISystem)


async def test_probe_rejects_unknown_type(mock_modbus_unit):
    _seed_base(mock_modbus_unit, 999)
    _seed_isystem(mock_modbus_unit)

    with pytest.raises(UnsupportedDiematicError):
        await async_probe(mock_modbus_unit)


async def test_probe_rejects_when_both_layouts_fail(mock_modbus_unit):
    mock_modbus_unit.fail_read(3, IllegalDataAddressError())
    mock_modbus_unit.fail_read(108, IllegalDataAddressError())
    mock_modbus_unit.fail_read(457, IllegalDataAddressError())
    mock_modbus_unit.fail_read(600, IllegalDataAddressError())
    mock_modbus_unit.fail_read(679, IllegalDataAddressError())

    with pytest.raises(IllegalDataAddressError):
        await async_probe(mock_modbus_unit)


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(ModbusConnectionError("link down"), id="connection"),
        pytest.param(ModbusTimeoutError("timeout"), id="timeout"),
    ],
)
async def test_probe_propagates_transport_errors(mock_modbus_unit, error):
    _seed_isystem(mock_modbus_unit)
    mock_modbus_unit.fail_read(3, error)

    with pytest.raises(type(error)):
        await async_probe(mock_modbus_unit)

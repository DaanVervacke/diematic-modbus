import pytest
from modbus_connection import ModbusConnectionError
from modbus_connection.exceptions import IllegalDataAddressError

from diematic_modbus import Diematic, DiematicISystem


def _seed(unit) -> None:
    unit.holding.update({7: 205, 75: 650, 18: 210, 59: 550, 62: 500})


def _seed_isystem(unit) -> None:
    unit.holding.update({601: 205, 602: 650, 614: 210, 126: 0x0180})


async def test_partial_failure_keeps_stale_and_reports(mock_modbus_unit):
    _seed(mock_modbus_unit)
    diematic = Diematic(mock_modbus_unit)
    first = await diematic.async_update()
    assert first.complete
    assert diematic.sensors.boiler_temp == 65.0

    mock_modbus_unit.fail_read(75, IllegalDataAddressError())
    report = await diematic.async_update()

    assert not report.complete
    assert "sensors" in report.failed
    assert "sensors" not in report.updated
    assert "circuit_a" in report.updated
    assert diematic.sensors.boiler_temp == 65.0


async def test_dead_link_raises(mock_modbus_unit):
    _seed(mock_modbus_unit)
    diematic = Diematic(mock_modbus_unit)
    mock_modbus_unit.fail_requests(ModbusConnectionError("link down"))
    with pytest.raises(ModbusConnectionError):
        await diematic.async_update()


async def test_isystem_schedules_read_once(mock_modbus_unit):
    _seed_isystem(mock_modbus_unit)
    boiler = DiematicISystem(mock_modbus_unit)
    first = await boiler.async_update()
    assert "schedules.circuit_a_p4" in first.updated

    mock_modbus_unit.fail_read(126, IllegalDataAddressError())
    second = await boiler.async_update()
    assert "schedules.circuit_a_p4" not in second.failed
    assert "schedules.circuit_a_p4" not in second.updated


async def test_isystem_read_once_retries_until_success(mock_modbus_unit):
    _seed_isystem(mock_modbus_unit)
    mock_modbus_unit.fail_read(126, IllegalDataAddressError())
    boiler = DiematicISystem(mock_modbus_unit)
    first = await boiler.async_update()
    assert "schedules.circuit_a_p4" in first.failed
    assert "schedules.circuit_a_p4" not in first.updated
    assert "schedules.hot_water" in first.updated

    mock_modbus_unit.fail_read(126, None)
    second = await boiler.async_update()
    assert "schedules.circuit_a_p4" in second.updated


async def test_read_raw_dumps_registers(mock_modbus_unit):
    _seed(mock_modbus_unit)
    diematic = Diematic(mock_modbus_unit)
    raw = await diematic.async_read_raw()
    assert raw["holding"][75] == 650

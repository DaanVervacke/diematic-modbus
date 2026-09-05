import pytest
from modbus_connection import ModbusConnectionError
from modbus_connection.exceptions import IllegalDataAddressError

from diematic_modbus import Diematic, DiematicISystem, HeatingMode, HotWaterMode


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


@pytest.mark.parametrize(
    ("regulator_type", "mode_address", "temp_address"),
    [(Diematic, 17, 75), (DiematicISystem, 653, 602)],
)
async def test_poll_keeps_holiday_and_unknown_modes(
    mock_modbus_unit, regulator_type, mode_address, temp_address
):
    mock_modbus_unit.holding.update({mode_address: 0x71, temp_address: 650})
    boiler = regulator_type(mock_modbus_unit)
    first = await boiler.async_update()
    assert first.complete
    assert boiler.circuit_a.mode is HeatingMode.HOLIDAY
    assert boiler.sensors.boiler_temp == 65.0

    mock_modbus_unit.holding.update({mode_address: 0x57, temp_address: 660})
    second = await boiler.async_update()
    assert second.complete
    assert {"circuit_a", "sensors"} <= second.updated
    assert type(boiler.circuit_a.mode) is int
    assert boiler.circuit_a.mode == 7
    assert boiler.sensors.boiler_temp == 66.0

    mock_modbus_unit.holding[mode_address] = 0x58
    await boiler.async_update()
    assert boiler.circuit_a.mode is HeatingMode.AUTO


async def test_isystem_unknown_hot_water_and_active_modes(mock_modbus_unit):
    mock_modbus_unit.holding.update({659: 0x48, 640: 6, 641: 6})
    boiler = DiematicISystem(mock_modbus_unit)
    report = await boiler.async_update()
    assert report.complete
    assert boiler.circuit_b.mode is HeatingMode.AUTO
    assert boiler.hot_water.mode == 64
    assert boiler.hot_water.active_mode == 6
    assert boiler.diagnostics.aux_active_mode == 6

    mock_modbus_unit.holding[659] = 0x58
    await boiler.async_update()
    assert boiler.hot_water.mode is HotWaterMode.TEMP

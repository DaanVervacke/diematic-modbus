from modbus_connection.mock import MockModbusUnit

from diematic_modbus import Diematic, HeatingMode, HotWaterMode


def _seed(unit: MockModbusUnit) -> None:
    unit.holding.update(
        {
            3: 400,
            4: 14,
            5: 30,
            7: 205,
            14: 550,
            17: 0x58,
            18: 210,
            27: 0xFFFF,
            59: 550,
            62: 500,
            75: 650,
            110: 25,
            427: 0x38,
            453: 0xFFFF,
            455: 3000,
            456: 15,
            457: 3,
            459: 505,
            462: 700,
            463: 42,
            465: 0xFFFF,
            467: 0x8000 | 120,
            470: 195,
            471: 250,
        }
    )


async def test_reads_decode_across_bundles(mock_modbus_unit):
    _seed(mock_modbus_unit)
    diematic = Diematic(mock_modbus_unit)
    await diematic.async_update()

    assert diematic.sensors.outdoor_temp == 20.5
    assert diematic.sensors.boiler_temp == 65.0
    assert diematic.sensors.return_temp is None
    assert diematic.sensors.water_pressure == 1.5
    assert diematic.sensors.fan_speed == 3000
    assert diematic.sensors.pump_power == 42
    assert diematic.sensors.burner_on is True
    assert diematic.sensors.hot_water_pump_on is True
    assert diematic.sensors.alarm is None

    assert diematic.hot_water.temp == 50.0
    assert diematic.hot_water.temp_dpsm == 50.5
    assert diematic.hot_water.mode is HotWaterMode.TEMP
    assert diematic.hot_water.day_target == 55.0

    assert diematic.sensors.calc_boiler_temp == 70.0
    assert diematic.sensors.outdoor_temp_bus == 19.5
    assert diematic.sensors.instant_power == 25.0
    assert diematic.sensors.solar_temp == -12.0

    assert diematic.circuit_a.mode is HeatingMode.AUTO
    assert diematic.circuit_a.room_temp == 21.0
    assert diematic.circuit_a.pump_on is True

    assert diematic.identity.year == 25


async def test_boiler_type_decodes_controller_name(mock_modbus_unit):
    _seed(mock_modbus_unit)
    mock_modbus_unit.holding[457] = 24
    diematic = Diematic(mock_modbus_unit)
    await diematic.async_update()
    assert diematic.identity.boiler_type == "D4"
    mock_modbus_unit.holding[457] = 999
    await diematic.async_update()
    assert diematic.identity.boiler_type == 999


async def test_known_alarm_code_decodes_to_label(mock_modbus_unit):
    _seed(mock_modbus_unit)
    mock_modbus_unit.holding[465] = 0x100D
    diematic = Diematic(mock_modbus_unit)
    await diematic.async_update()
    assert diematic.sensors.alarm == "DEF.ALLUMAGE 14"


async def test_unknown_alarm_code_surfaces_as_raw_int(mock_modbus_unit):
    _seed(mock_modbus_unit)
    mock_modbus_unit.holding[465] = 0x7777
    diematic = Diematic(mock_modbus_unit)
    await diematic.async_update()
    assert diematic.sensors.alarm == 0x7777


async def test_absent_integer_sensors_read_none(mock_modbus_unit):
    _seed(mock_modbus_unit)
    mock_modbus_unit.holding[463] = 0xFFFF
    mock_modbus_unit.holding[455] = 0xFFFF
    diematic = Diematic(mock_modbus_unit)
    await diematic.async_update()
    assert diematic.sensors.pump_power is None
    assert diematic.sensors.fan_speed is None


async def test_smoke_temp_out_of_range_reads_none(mock_modbus_unit):
    _seed(mock_modbus_unit)
    mock_modbus_unit.holding[454] = 0x8CCC
    diematic = Diematic(mock_modbus_unit)
    await diematic.async_update()
    assert diematic.sensors.smoke_temp is None
    mock_modbus_unit.holding[454] = 800
    await diematic.async_update()
    assert diematic.sensors.smoke_temp == 80.0


async def test_circuit_presence_follows_room_temp(mock_modbus_unit):
    _seed(mock_modbus_unit)
    diematic = Diematic(mock_modbus_unit)
    await diematic.async_update()
    assert diematic.circuit_a_present is True
    assert diematic.circuit_b_present is False


async def test_force_circuit_b_overrides_absent_sensor(mock_modbus_unit):
    _seed(mock_modbus_unit)
    diematic = Diematic(mock_modbus_unit, force_circuit_b=True)
    await diematic.async_update()
    assert diematic.circuit_b_present is True

from datetime import time

from modbus_connection.mock import MockModbusUnit

from diematic_modbus import DiematicISystem, HeatingMode, HotWaterMode


def _seed(unit: MockModbusUnit) -> None:
    unit.holding.update(
        {
            8: 190,
            17: 0x58,
            427: 0x38,
            457: 24,
            465: 0xFFFF,
            600: 412,
            601: 205,
            602: 650,
            603: 500,
            607: 0xFFFF,
            609: 3000,
            614: 210,
            616: 0xFFFF,
            618: 225,
            620: 700,
            650: 550,
            672: 550,
            684: 26,
        }
    )


async def test_isystem_reads_decode_across_bundles(mock_modbus_unit):
    _seed(mock_modbus_unit)
    boiler = DiematicISystem(mock_modbus_unit)
    await boiler.async_update()

    assert boiler.sensors.outdoor_temp == 20.5
    assert boiler.sensors.boiler_temp == 65.0
    assert boiler.sensors.return_temp is None
    assert boiler.sensors.fan_speed == 3000
    assert boiler.sensors.burner_on is True
    assert boiler.sensors.hot_water_pump_on is True
    assert boiler.sensors.alarm is None

    assert boiler.hot_water.temp == 50.0
    assert boiler.hot_water.mode is HotWaterMode.TEMP
    assert boiler.hot_water.day_target == 55.0

    assert boiler.circuit_a.mode is HeatingMode.AUTO
    assert boiler.circuit_a.room_temp == 21.0
    assert boiler.circuit_c.room_temp == 22.5

    assert boiler.identity.software_version == 412
    assert boiler.identity.boiler_type == "D4"
    assert boiler.identity.year == 26


async def test_isystem_circuit_presence_follows_room_temp(mock_modbus_unit):
    _seed(mock_modbus_unit)
    boiler = DiematicISystem(mock_modbus_unit)
    await boiler.async_update()
    assert boiler.circuit_a_present is True
    assert boiler.circuit_b_present is False
    assert boiler.circuit_c_present is True


async def test_isystem_mode_writes_through_low_register(mock_modbus_unit):
    mock_modbus_unit.holding[17] = 0x58
    boiler = DiematicISystem(mock_modbus_unit)
    await boiler.set_circuit_a_mode(HeatingMode.TEMP_DAY)
    word = mock_modbus_unit.holding[17]
    assert word & 0x2F == int(HeatingMode.TEMP_DAY)
    assert word & 0x50 == int(HotWaterMode.TEMP)


async def test_isystem_setpoint_snaps_and_writes(mock_modbus_unit):
    boiler = DiematicISystem(mock_modbus_unit)
    await boiler.circuit_a.write("day_target", 20.3)
    assert mock_modbus_unit.holding[650] == 205


async def test_isystem_schedule_decodes_comfort_ranges(mock_modbus_unit):
    mock_modbus_unit.holding.update(
        {
            126: 0x000F,
            127: 0x8000,
            128: 0,
            131: 0x000F,
            147: 0x0003,
            148: 0xFFFF,
            149: 0xFF00,
            189: 0x03FF,
            190: 0xC180,
            191: 0xFFF8,
            210: 0x000F,
            211: 0xFFFF,
            212: 0xFFF0,
        }
    )
    boiler = DiematicISystem(mock_modbus_unit)
    await boiler.async_update()
    week = boiler.schedules.circuit_a_p4
    assert week[1] == [(time(6, 0), time(8, 30))]
    assert week[2] == [(time(22, 0), time(0, 0))]
    assert week[3] == []
    assert boiler.schedules.circuit_b_p4[1] == [(time(7, 0), time(20, 0))]
    assert boiler.schedules.hot_water[1] == [
        (time(3, 0), time(9, 0)),
        (time(11, 30), time(12, 30)),
        (time(16, 0), time(22, 30)),
    ]
    assert boiler.schedules.auxiliary[1] == [(time(6, 0), time(22, 0))]
    assert boiler.schedules.circuit_c_p4[7] == []


async def test_isystem_schedule_reads_one_day_per_request(mock_modbus_unit):
    boiler = DiematicISystem(mock_modbus_unit)
    program = boiler.schedules.programs["circuit_b_p4"]
    plan = program._build_plan()
    assert plan.blocks["holding"] == [(147 + 3 * day, 3) for day in range(7)]


async def test_isystem_decodes_selected_program(mock_modbus_unit):
    mock_modbus_unit.holding.update({231: 0x2000, 232: 0x2023, 233: 0x2038})
    boiler = DiematicISystem(mock_modbus_unit)
    await boiler.async_update()
    assert boiler.circuit_a.program == 1
    assert boiler.circuit_b.program == 2
    assert boiler.circuit_c.program == 1

    mock_modbus_unit.holding.update({231: 0x2015, 232: 0x2007, 233: 0xFFFF})
    await boiler.async_update()
    assert boiler.circuit_a.program == 4
    assert boiler.circuit_b.program == 2
    assert boiler.circuit_c.program is None


async def test_isystem_read_raw_covers_schedule_blocks(mock_modbus_unit):
    mock_modbus_unit.holding.update({126: 0x000F, 168: 0x0003, 231: 0x2000})
    boiler = DiematicISystem(mock_modbus_unit)
    raw = await boiler.async_read_raw()
    assert raw["holding"][126] == 0x000F
    assert raw["holding"][168] == 0x0003
    assert raw["holding"][231] == 0x2000

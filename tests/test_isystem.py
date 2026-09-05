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


async def test_isystem_parity_registers_decode(mock_modbus_unit):
    _seed(mock_modbus_unit)
    mock_modbus_unit.holding.update({605: 247, 654: 3, 660: 3, 662: 100, 663: 420})
    boiler = DiematicISystem(mock_modbus_unit)
    await boiler.async_update()
    assert boiler.circuit_a.ambient_influence == 3
    assert boiler.circuit_b.ambient_influence == 3
    assert boiler.circuit_b.supply_temp == 24.7
    assert boiler.circuit_b.min_temp == 10.0
    assert boiler.circuit_b.max_temp == 42.0


async def test_isystem_research_registers_decode(mock_modbus_unit):
    _seed(mock_modbus_unit)
    mock_modbus_unit.holding.update(
        {
            604: 800,
            610: 8,
            661: 8,
            668: 3,
            669: 7,
            670: 100,
            671: 500,
            677: 200,
            678: 750,
        }
    )
    boiler = DiematicISystem(mock_modbus_unit)
    await boiler.async_update()
    assert boiler.sensors.smoke_temp == 80.0
    assert boiler.sensors.water_pressure == 0.8
    assert boiler.circuit_b.slope == 0.8
    assert boiler.circuit_c.ambient_influence == 3
    assert boiler.circuit_c.slope == 0.7
    assert boiler.circuit_c.min_temp == 10.0
    assert boiler.circuit_c.max_temp == 50.0
    assert boiler.settings.boiler_min == 20.0
    assert boiler.settings.boiler_max == 75.0


async def test_isystem_config_and_diagnostics_decode(mock_modbus_unit):
    _seed(mock_modbus_unit)
    mock_modbus_unit.holding.update(
        {
            263: 5,
            266: 120,
            276: 0x8010,
            289: 350,
            291: 150,
            296: 1,
            298: 300,
            305: 5200,
            473: 1,
            644: 5,
            712: 255,
            744: 3,
        }
    )
    boiler = DiematicISystem(mock_modbus_unit)
    await boiler.async_update()
    assert boiler.config.language == 5
    assert boiler.config.bandwidth == 12.0
    assert boiler.config.zone_b_calibration == -1.6
    assert boiler.config.footprint_a_day == 35.0
    assert boiler.config.footprint_b_day is None
    assert boiler.config.zone_a_type == 1
    assert boiler.config.zone_a_min == 30.0
    assert boiler.config.max_fan_speed == 5200
    assert boiler.config.modulated_power == 1
    assert boiler.diagnostics.boiler_active_mode == 5
    assert boiler.diagnostics.pcu_block == 255
    assert boiler.diagnostics.zone_aux_type == 3


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

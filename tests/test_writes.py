from datetime import datetime

import pytest

from diematic_modbus import (
    Diematic,
    DiematicISystem,
    DiematicVariant,
    HeatingMode,
    HotWaterMode,
)


async def test_hot_water_setpoint_snaps_and_writes(mock_modbus_unit):
    diematic = Diematic(mock_modbus_unit)
    await diematic.hot_water.write("day_target", 53.4)
    assert mock_modbus_unit.holding[59] == 530


async def test_settings_boiler_max_writes(mock_modbus_unit):
    diematic = Diematic(mock_modbus_unit)
    await diematic.settings.write("boiler_max", 75)
    assert mock_modbus_unit.holding[71] == 750


async def test_circuit_slope_writes(mock_modbus_unit):
    diematic = Diematic(mock_modbus_unit)
    await diematic.circuit_a.write("slope", 1.5)
    assert mock_modbus_unit.holding[20] == 15


async def test_circuit_slope_clamps_high(mock_modbus_unit):
    diematic = Diematic(mock_modbus_unit)
    await diematic.circuit_a.write("slope", 5)
    assert mock_modbus_unit.holding[20] == 40


async def test_summer_winter_snaps_and_clamps(mock_modbus_unit):
    diematic = Diematic(mock_modbus_unit)
    await diematic.settings.write("summer_winter_temp", 22.3)
    assert mock_modbus_unit.holding[8] == 225
    await diematic.settings.write("summer_winter_temp", 40)
    assert mock_modbus_unit.holding[8] == 305


async def test_set_clock_writes_blocks_with_marker(mock_modbus_unit):
    diematic = Diematic(mock_modbus_unit)
    await diematic.set_clock(datetime(2026, 9, 4, 14, 5))
    assert mock_modbus_unit.holding[4] == 0xFF00 | 14
    assert mock_modbus_unit.holding[5] == 0xFF00 | 5
    assert mock_modbus_unit.holding[6] == 0xFF00 | 5
    assert mock_modbus_unit.holding[108] == 0xFF00 | 4
    assert mock_modbus_unit.holding[109] == 0xFF00 | 9
    assert mock_modbus_unit.holding[110] == 0xFF00 | 26


async def test_hot_water_setpoint_clamps_high(mock_modbus_unit):
    diematic = Diematic(mock_modbus_unit)
    await diematic.hot_water.write("day_target", 200)
    assert mock_modbus_unit.holding[59] == 800


async def test_zone_setpoint_half_degree_step(mock_modbus_unit):
    diematic = Diematic(mock_modbus_unit)
    await diematic.circuit_a.write("day_target", 20.3)
    assert mock_modbus_unit.holding[14] == 205


async def test_setting_heating_mode_preserves_hot_water_bits(mock_modbus_unit):
    mock_modbus_unit.holding[17] = 0x58
    diematic = Diematic(mock_modbus_unit)
    await diematic.set_circuit_a_mode(HeatingMode.TEMP_DAY)
    word = mock_modbus_unit.holding[17]
    assert word & 0x2F == int(HeatingMode.TEMP_DAY)
    assert word & 0x50 == int(HotWaterMode.TEMP)


async def test_setting_hot_water_mode_preserves_heating_bits(mock_modbus_unit):
    mock_modbus_unit.holding[17] = 0x58
    diematic = Diematic(mock_modbus_unit)
    await diematic.set_hot_water_mode(HotWaterMode.PERM)
    word = mock_modbus_unit.holding[17]
    assert word & 0x50 == int(HotWaterMode.PERM)
    assert word & 0x2F == int(HeatingMode.AUTO)


async def test_diematic3_does_not_nudge_panel(mock_modbus_unit):
    diematic = Diematic(mock_modbus_unit, variant=DiematicVariant.DIEMATIC_3)
    await diematic.set_circuit_a_mode(HeatingMode.AUTO)
    assert 13 not in mock_modbus_unit.holding


async def test_diematic4_nudges_panel(mock_modbus_unit, monkeypatch):
    async def _no_sleep(_seconds):
        return None

    monkeypatch.setattr("diematic_modbus._base.asyncio.sleep", _no_sleep)
    diematic = Diematic(mock_modbus_unit, variant=DiematicVariant.DIEMATIC_4)
    await diematic.set_circuit_a_mode(HeatingMode.AUTO)
    assert mock_modbus_unit.holding[13] == 0


@pytest.mark.parametrize("field", ["outdoor_temp"])
async def test_reading_field_is_not_writable(mock_modbus_unit, field):
    diematic = Diematic(mock_modbus_unit)
    with pytest.raises(AttributeError):
        await diematic.sensors.write(field, 10)


@pytest.mark.parametrize(
    ("regulator_type", "method"),
    [
        (Diematic, "set_circuit_a_mode"),
        (Diematic, "set_circuit_b_mode"),
        (DiematicISystem, "set_circuit_a_mode"),
        (DiematicISystem, "set_circuit_b_mode"),
        (DiematicISystem, "set_circuit_c_mode"),
    ],
)
@pytest.mark.parametrize("mode", [HeatingMode.HOLIDAY, 33, 7, 0x58])
async def test_unsupported_heating_mode_rejected_before_io(
    mock_modbus_unit, regulator_type, method, mode
):
    boiler = regulator_type(mock_modbus_unit, variant=DiematicVariant.DIEMATIC_4)
    writes = []
    mock_modbus_unit.on_write(writes.append)
    with pytest.raises(ValueError):
        await getattr(boiler, method)(mode)
    assert mock_modbus_unit.read_events == []
    assert writes == []


@pytest.mark.parametrize("regulator_type", [Diematic, DiematicISystem])
async def test_unknown_hot_water_mode_rejected_before_io(
    mock_modbus_unit, regulator_type
):
    boiler = regulator_type(mock_modbus_unit, variant=DiematicVariant.DIEMATIC_4)
    writes = []
    mock_modbus_unit.on_write(writes.append)
    with pytest.raises(ValueError):
        await boiler.set_hot_water_mode(64)
    assert mock_modbus_unit.read_events == []
    assert writes == []


@pytest.mark.parametrize(
    ("regulator_type", "address"), [(Diematic, 17), (DiematicISystem, 659)]
)
@pytest.mark.parametrize("mode", list(HotWaterMode))
async def test_hot_water_write_preserves_holiday(
    mock_modbus_unit, regulator_type, address, mode
):
    mock_modbus_unit.holding[address] = 0xA1
    boiler = regulator_type(mock_modbus_unit)
    await boiler.set_hot_water_mode(mode)
    assert mock_modbus_unit.holding[address] == 0xA1 | int(mode)


@pytest.mark.parametrize(
    "mode", [mode for mode in HeatingMode if mode is not HeatingMode.HOLIDAY]
)
async def test_known_heating_modes_preserve_unknown_hot_water_bits(
    mock_modbus_unit, mode
):
    mock_modbus_unit.holding[659] = 0xC8
    boiler = DiematicISystem(mock_modbus_unit)
    await boiler.set_circuit_b_mode(mode)
    assert mock_modbus_unit.holding[659] == 0xC0 | int(mode)

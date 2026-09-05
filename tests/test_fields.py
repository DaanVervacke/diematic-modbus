import pytest

from diematic_modbus.enums import ActiveMode, HeatingMode, HotWaterMode
from diematic_modbus.fields import Float10Field, masked_enum, snap_clamp


def test_float10_decodes_positive_tenths():
    assert Float10Field(0).decode([205]) == 20.5


def test_float10_decodes_sign_magnitude_negative():
    assert Float10Field(0).decode([0x8000 | 50]) == -5.0


def test_float10_absent_sensor_is_none():
    assert Float10Field(0).decode([0xFFFF]) is None


def test_float10_encodes_positive():
    assert Float10Field(0).encode(20.5) == [205]


def test_float10_encodes_negative_with_sign_bit():
    assert Float10Field(0).encode(-5.0) == [0x8000 | 50]


def test_snap_clamp_snaps_and_clamps_hot_water():
    validate = snap_clamp(5.0, 10.0, 80.0)
    assert validate(53) == 55.0
    assert validate(5) == 10.0
    assert validate(200) == 80.0


def test_snap_clamp_zone_half_degree_step():
    validate = snap_clamp(0.5, 5.0, 30.0)
    assert validate(20.3) == 20.5


def test_masked_enum_splits_shared_register():
    heating = masked_enum(17, 0x2F, HeatingMode)
    hot_water = masked_enum(17, 0x50, HotWaterMode)
    assert heating.decode([0x58]) is HeatingMode.AUTO
    assert hot_water.decode([0x58]) is HotWaterMode.TEMP


@pytest.mark.parametrize(
    ("enum_type", "mask", "raw", "expected"),
    [
        (HeatingMode, 0x2F, 0x57, 7),
        (HotWaterMode, 0x50, 0x48, 64),
        (ActiveMode, 0x06, 0x86, 6),
    ],
)
def test_unrecognised_modes_remain_readable(enum_type, mask, raw, expected):
    field = masked_enum(0, mask, enum_type)
    value = field.decode([raw])
    assert type(value) is int
    assert value == expected


def test_holiday_mode_preserves_hot_water_mode():
    heating = masked_enum(0, 0x2F, HeatingMode)
    hot_water = masked_enum(0, 0x50, HotWaterMode)
    assert heating.decode([0x71]) is HeatingMode.HOLIDAY
    assert hot_water.decode([0x71]) is HotWaterMode.TEMP

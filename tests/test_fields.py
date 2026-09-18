from datetime import time

import pytest

from diematic_modbus.enums import ActiveMode, HeatingMode, HotWaterMode
from diematic_modbus.fields import (
    Float10Field,
    ScheduleDayField,
    _day_intervals,
    boiler_type_field,
    masked_enum,
    snap_clamp,
)


def test_float10_decodes_positive_tenths():
    assert Float10Field(0).decode([205]) == 20.5


def test_float10_decodes_sign_magnitude_negative():
    assert Float10Field(0).decode([0x8000 | 50]) == -5.0


def test_float10_matches_official_negative_tenth_example():
    assert Float10Field(0).decode([0x8001]) == -0.1


@pytest.mark.parametrize("raw", [0xFFFF, 0x8CCC])
def test_float10_absent_sensor_values_are_none(raw):
    assert Float10Field(0).decode([raw]) is None


@pytest.mark.parametrize("raw", [101, 150])
def test_float10_custom_absent_values_are_none(raw):
    field = Float10Field(0)
    field.none_values = (raw,)
    assert field.decode([raw]) is None


def test_float10_encodes_positive():
    assert Float10Field(0).encode(20.5) == [205]


def test_float10_encodes_negative_with_sign_bit():
    assert Float10Field(0).encode(-5.0) == [0x8000 | 50]


def test_float10_encodes_negative_tenth_example():
    assert Float10Field(0).encode(-0.1) == [0x8001]


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


@pytest.mark.parametrize(
    "periods",
    [
        [(time(9, 15), time(10, 45))],
        [(time(9, 0), time(10, 45))],
        [(time(9, 15), time(10, 0))],
    ],
)
def test_schedule_day_encode_rejects_non_half_hour_minutes(periods):
    with pytest.raises(ValueError, match="multiple of 30"):
        ScheduleDayField(0).encode(periods)


def test_schedule_day_encode_accepts_half_hour_aligned_minutes():
    periods = [(time(9, 0), time(10, 30)), (time(16, 30), time(0, 0))]
    assert _day_intervals(ScheduleDayField(0).encode(periods)) == periods


def test_boiler_type_field_decodes_known_and_unknown_codes():
    """boiler_type_field maps register 457 via MODEL_CODES, unknowns as raw ints."""
    field = boiler_type_field()
    assert field.address == 457
    assert field.convert(24) == "D4"
    assert field.convert(0) == "3-25LP"
    assert field.convert(999) == 999

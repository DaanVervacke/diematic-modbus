# diematic-modbus

Read temperatures, check what your heating is doing, and change supported
settings on a De Dietrich Diematic boiler from Python.

This is a library for building your own tools, not a heating-control app or
an installable Home Assistant integration. It also includes a test script:
you can help check compatibility with your boiler without writing Python.

> [!WARNING]
> This project is still experimental. Hardware testing has focused on one
> Diematic iSystem installation, which reports the type code `D4`. Other
> Diematic 3 and 4 installations need testing. A feature being implemented
> does not mean it has been verified on your boiler. Start with a read-only
> test before trying any changes.

## What it does

| Feature | Read | Change |
| --- | --- | --- |
| Boiler operation | Temperatures, water pressure, fan speed, burner and pump status, experimental fault codes | No direct burner or pump control |
| Room heating | Room temperatures, temperature targets, heating modes and heating-curve settings | Day, night and frost-protection targets, heating mode, selected heating curves |
| Hot water | Tank temperature, day/night targets and operating mode | Day/night targets and automatic or comfort mode |
| Weekly schedules | On iSystem: heating program P4, hot-water and auxiliary schedules, and which heating program is selected | No schedule editing or program selection |
| Seasonal settings | Summer/winter changeover temperature and boiler temperature limits | Changeover temperature, and boiler limits through the base layout |
| Installer information | On iSystem: calibration, tuning parameters and additional diagnostic codes | Read-only |
| Identity and clock | Reported type code, controller/software code, date and time | iSystem clock setting verified on the test boiler. Base-layout clock setting is implemented but untested on a base-layout boiler |

Availability depends on the control panel and fitted equipment. A *heating
circuit* is one of the separately controlled parts of the heating system,
labelled A, B or C on the panel. A *target* is the temperature you ask for,
not a temperature measured by a sensor. Day/comfort and night/reduced refer
to the panel's temperature settings, not necessarily the time of day.

**Choose your next step:**

- [Test your boiler](#test-your-boiler): run the script, compare its output
  with the panel, and share what works or looks wrong.
- [Use the Python library](#use-the-python-library): connect from your own
  application, read values, and make supported changes.
- [Full feature reference](#full-feature-reference): check individual
  readings, controls, and differences between layouts.
- [Hardware testing so far](#hardware-testing-so-far): see what has actually
  been tried, rather than just implemented.

## Which systems are covered?

The library implements two ways of addressing the boiler's data. These are
called *register layouts*: a register is a numbered place where the
controller exposes a reading or setting.

| Control panel / data layout | Python class | Test-script option | Coverage |
| --- | --- | --- | --- |
| Diematic 3 or 4, base layout | `Diematic` | `--layout base` | Circuits A/B and boiler controls, including readings from the optional DPSM condensing-boiler module |
| Diematic iSystem | `DiematicISystem` | `--layout isystem` | Circuits A/B/C, current operating states, weekly schedules, installer settings and diagnostics |

The test iSystem boiler answers both layouts. They overlap, but neither
contains everything the other does. For example, the base layout includes
solar temperatures and power readings that the iSystem class does not.
There is no automatic panel detection, and Diematic Delta is not supported.

The reported type code, such as `D4`, does not reliably identify the physical
boiler model. Use the boiler's label and the panel name when reporting your
installation.

## Test your boiler

The main way to contribute is to run `scripts/read_diematic.py` and compare
its readings with your control panel. Successful results from another
installation are useful too. You do not need to understand register numbers
or write a program.

### Before you start

You need Python 3.12 or newer, [uv](https://docs.astral.sh/uv/), a copy of this
repository, and a working connection to the controller's Modbus port.

The script supports a serial adapter or a network gateway that forwards
Modbus RTU messages unchanged. That last detail matters: a gateway configured
to translate to ordinary Modbus TCP is not the connection mode this script
uses. You need its IP address and port, or your serial adapter's device path,
plus the controller's Modbus address.

Download and extract this repository, or clone it:

```shell
git clone https://github.com/DaanVervacke/diematic-modbus.git
cd diematic-modbus
```

Run the following commands from that repository folder. `uv run --extra cli`
installs the project's dependencies and the Modbus backend needed by the
script. You do not need to install this package globally.

### Run a read-only test

For an iSystem panel through a network gateway:

```shell
uv run --extra cli scripts/read_diematic.py 192.168.1.50 --port 502 --unit 10 --layout isystem
```

Replace `192.168.1.50` and `502` with your gateway's address and port. Replace
`10` if your controller uses a different Modbus address. These are examples,
not values the script can discover for you.

Use `--layout base` for the Diematic 3/4 base layout. On an iSystem, use
`--layout both` to compare both sets of readings. The script reads the base
layout first, then iSystem. This does not switch anything on the boiler.

For a serial adapter, replace `/dev/ttyUSB0` with its device path:

```shell
uv run --extra cli scripts/read_diematic.py /dev/ttyUSB0 --transport serial --unit 10 --layout isystem
```

Serial defaults are 9600 baud, 8 data bits, no parity, and 1 stop bit. Match
them to your installation using `--baudrate`, `--bytesize`, `--parity`, and
`--stopbits` when necessary. To see all options:

```shell
uv run --extra cli scripts/read_diematic.py --help
```

`--variant 3` or `--variant 4` affects only the library's base-layout heating
and hot-water mode changes. It does not select the layout and has no effect
on this read-only test. The script defaults to variant 3 and layout `base`.

### Compare with the panel

The script reads once, prints tables, and exits. It writes nothing unless
you explicitly add `--probe-write`.

1. Check for warnings or errors before trusting the values. A failed group
   can show missing or older values, including an empty schedule.
2. Compare outdoor, boiler, room and hot-water temperatures with the panel.
   Compare measured temperatures with measurements, and targets with targets.
3. Check the day/night targets and modes for the circuits you actually have.
   The `circuit_*_present` flags only mean that a room-temperature reading is
   available. `False` does not prove the heating circuit is absent.
4. On iSystem, compare the displayed heating schedules with **P4**, even if
   the panel currently runs P1, P2 or P3. Check the hot-water schedule too.
   The script displays the end of a day as `24:00`.
5. Rerun the script after a panel change if you want a new comparison.
   Schedules and installer settings are saved after their first successful
   read within each library instance, rather than refreshed on every poll.

A missing value is not automatically a bug: some sensors or modules may not
be fitted. An empty comfort schedule does not mean the boiler is powered
off. Installer and diagnostic numbers without a clear label or unit should
be reported as shown, not interpreted as a temperature or an error.

### If a read fails

Check the address, port, controller address and connection settings. A busy
RS485 bus can cause timeouts, so rerun the read-only command before concluding
that a value is unsupported. `--timeout 20` allows 20 seconds per request
instead of the default 10. Neither option fixes incorrect wiring or framing.

For troubleshooting, add `--debug` to the same command. It prints the sent
and received Modbus messages as well as the normal output. For example,
this saves both in a text file:

```shell
uv run --extra cli scripts/read_diematic.py 192.168.1.50 --port 502 --unit 10 --layout isystem --debug > diematic-read.txt 2>&1
```

The script exits with status 0 when all requested reads and any requested
write check succeed. It returns 1 for connection or read failures, partial
reads, or a write check that fails, mismatches, or is skipped. Invalid command
arguments return 2. Partial reads still print the available values.

A successful read does not prove every value is understood or every sensor
is fitted. If a mode appears as a number rather than a name, include it and
the panel's displayed mode in your report. The library keeps unknown mode
codes for investigation.

### Share your results

Open an issue in this repository with:

- The boiler model from its label, panel name, and reported type/software
  codes. A photo of the panel can help identify the controller.
- Which circuits and optional modules are fitted, and which have room sensors.
- Your adapter or gateway model, its connection settings, and the command
  used. Replace private addresses or device paths if you prefer.
- The script output, with `--debug` output and any traceback when a read fails.
- A few specific comparisons, such as “circuit B night target: panel 17 °C,
  script 17.0 °C,” plus any differences. Say what you could not check.
- The code version you ran. `git rev-parse HEAD` gives the commit if you
  cloned the repository. For a downloaded archive, give its branch/tag and date.

Review logs and photos before posting. Remove personal details, serial
numbers, and network information you do not want to publish. Do not clear
faults or change installer settings just to collect evidence.

### Optional: check whether a write is accepted

Only after a successful read and panel comparison, you can add
`--probe-write` to your command. All requested layouts must read successfully
before the check proceeds. It refreshes the hot-water data immediately before
writing, resubmits the current day target, then reads it back. With
`--layout both`, the write check uses iSystem only, but a partial read in
either layout prevents the write.

This is a **real write**, not a simulation or a test of every control. The
normal write rules round the request to whole degrees and limit it to
10 to 80 °C. If those rules would change the target, or the target is missing,
the script skips the write and returns status 1. A failed refresh also prevents
the write. Even a matching readback does not prove that a different target
would be accepted and kept.
Avoid changing the target on the panel while it runs. Check the panel
afterwards and restore the original setting if it changed. The script has
no separate restore step, and a panel change between the final read and write
can still race with the probe. Include its result in your report if you
choose to run it.

## Use the Python library

The package requires Python 3.12+. From a local checkout, install it in your
application's virtual environment:

```shell
pip install -e ".[cli]"
```

The `cli` extra includes the `tmodbus` backend used below. If your application
already provides a Modbus connection, `pip install -e .` installs the library
without choosing a backend.

The library is built on
[modbus-connection](https://github.com/home-assistant-libs/modbus-connection).
Your application creates and closes the connection, then passes a
`ModbusUnit` to the regulator. The regulator does not own the connection or
start background polling. It has no Home Assistant dependency.

### Read values

This example reads an iSystem through a gateway that forwards RTU messages.
Replace the example connection settings before running it. It does not
change settings:

```python
import asyncio

from modbus_connection import ModbusTcpParams
from modbus_connection.tmodbus import ModbusConnection

from diematic_modbus import DiematicISystem


async def main() -> None:
    params = ModbusTcpParams(host="192.168.1.50", port=502, framer="rtu")
    conn = ModbusConnection(params, message_spacing=0.05)
    try:
        boiler = DiematicISystem(conn.for_unit(10))
        report = await boiler.async_update()
        if report.complete:
            print("Outdoor temperature:", boiler.sensors.outdoor_temp)
            print("Hot-water temperature:", boiler.hot_water.temp)
        else:
            print("Could not refresh:", report.failed)
    finally:
        await conn.close()


asyncio.run(main())
```

For the base layout, use `Diematic(unit, variant=DiematicVariant.DIEMATIC_3)`
or `DIEMATIC_4`, importing both names from `diematic_modbus`. Direct serial
connections can use `ModbusSerialParams` instead of `ModbusTcpParams`.

Read values through `sensors`, `hot_water`, `circuit_a`, `circuit_b`,
`settings`, and `identity`. iSystem also has `circuit_c`, `schedules`,
`config`, and `diagnostics`. The feature reference below lists their field
names. A known absent-sensor value becomes `None`. Faults return a known
label, an unknown numeric code, or `None` for no fault.

Known modes return enum members. The observed holiday code `33` returns
`HeatingMode.HOLIDAY`. Other unknown heating, hot-water and current-state
codes return integers containing only that mode's bits, not the entire
shared register. They remain readable and do not count as a failed read.
Use `async_read_raw()` if you need the full register value.

### Refreshing and handling failures

Call `async_update()` whenever you need a new reading. If a combined read is
refused, the library retries the groups individually. A group that still
fails keeps its previous values and appears in `report.failed`. Successfully
refreshed groups appear in `report.updated`. A connection failure raises
`ModbusConnectionError` rather than returning a report.

On iSystem, `config` and each of the five schedules are read until they
succeed, then cached for the lifetime of the regulator object. They are
omitted from later reports. `report.complete` means no reported read failures
in that call, not that every value is new. Create a new regulator object
over the same unit to reread cached settings and schedules after panel edits.

The `circuit_*_present` properties check for a room-temperature reading.
Constructor options such as `force_circuit_b=True` override that flag only.
They do not add hardware support or change which registers are read or written.

For debugging, `async_read_raw()` reads the registers mapped by the library
without decoding them or updating the saved field values. It includes cached
groups but is not a scan of every address the boiler might support.

### Change settings

The following calls belong inside an async function with an existing
`boiler` object. They send real changes. Read and record the original
settings first, use values appropriate for your installation, then reread
and check the panel. Restore the originals when testing.

```python
from diematic_modbus import HeatingMode, HotWaterMode

await boiler.circuit_b.write("day_target", 20.0)
await boiler.hot_water.write("day_target", 55.0)
await boiler.set_circuit_b_mode(HeatingMode.AUTO)
await boiler.set_hot_water_mode(HotWaterMode.AUTO)
```

Use `write()` for writable numeric fields and `set_*_mode()` for modes.
Heating and hot-water modes share storage, so the mode methods preserve
the other setting's bits. Make mode changes sequentially, not concurrently.
The setters still attempt a write if a circuit's presence flag is false,
and a boiler can reject a write or fail to retain it.

Holiday mode is read-only: set it on the panel. Passing `HeatingMode.HOLIDAY`
or an unknown mode code to a mode setter raises `ValueError` before any
Modbus request. Reading a code does not make it a supported write value.

Most numeric controls round to a supported step and clamp to the library's
limits, listed below. Base-layout boiler minimum/maximum limits have no
such range validator. These are not safety guarantees or recommendations
for your installation.

### Work with schedules

On iSystem, `boiler.schedules.circuit_b_p4` returns a dictionary keyed by
weekday, 1 for Monday through 7 for Sunday. Each day contains pairs of
`datetime.time` values for its comfort periods, in half-hour steps.
For example, Monday might contain `[(time(6, 0), time(8, 0))]`.

An interval ending at `time(0, 0)` runs to the end of that day. An all-day
period is `(time(0, 0), time(0, 0))`. An empty list means no comfort periods
only after a successful read. Before then, missing days also appear empty.
Check the initial update report before interpreting a schedule.

The other properties are `circuit_a_p4`, `circuit_c_p4`, `hot_water`, and
`auxiliary`. Each schedule is reported separately, for example as
`schedules.circuit_b_p4` in `report.updated` or `report.failed`.
`boiler.circuit_b.program` separately reports the selected program, 1 to 4.
Reading the P4 schedule does not mean P4 is selected.

## Full feature reference

These tables describe the implementation, not a promise that each reading
or write works on every installation. **Both** means the base and iSystem
classes expose the feature. Field names are included to help match script
output to Python usage. Unless listed as a control, a value is read-only.

### Temperatures and boiler operation

| Reading | Layout | Python field(s) |
| --- | --- | --- |
| Outdoor, boiler, return-water and flue-gas temperatures | Both | `sensors.outdoor_temp`, `boiler_temp`, `return_temp`, `smoke_temp` |
| Boiler's calculated temperature target | Both | `sensors.calc_boiler_temp` |
| Reading labelled outlet temperature, sensor location unverified | iSystem | `sensors.outlet_temp` |
| Additional outdoor reading from the boiler bus | Base | `sensors.outdoor_temp_bus` |
| Water pressure (bar), fan speed (rpm), flame-sensing current (µA) | Both | `sensors.water_pressure`, `fan_speed`, `ionization_current` |
| Burner and hot-water pump status | Both | `sensors.burner_on`, `hot_water_pump_on` |
| Reported pump output (%) | Base | `sensors.pump_power` |
| Instantaneous and average power (kW) | Base | `sensors.instant_power`, `average_power` |
| Solar and solar-tank temperatures | Base | `sensors.solar_temp`, `solar_tank_temp` |
| Fault label or unknown fault number | Both | `sensors.alarm` |

Fault readings are not reliable on the test iSystem installation: register
465 can return data left over from a previous reply, producing either a
false fault or an apparent no-fault value. Do not use `sensors.alarm` alone
for fault notifications or assume that `None` confirms a healthy boiler.
Check the control panel instead.

Temperatures are in °C. The averaging period for power is not defined by the
library. Pump and burner status are controller-reported states, not
independent proof of water flow or combustion. There is no energy-total,
fuel-consumption, or direct pump/burner control API.

### Heating and hot water

Circuit fields below belong to `circuit_a`, `circuit_b`, or `circuit_c`.
The base layout has A/B only, while iSystem has A/B/C.

| Reading | Availability | Field(s) |
| --- | --- | --- |
| Room temperature and calculated circuit temperature target | Every exposed circuit | `room_temp`, `calc_temp` |
| Day, night and frost-protection targets | Every exposed circuit | `day_target`, `night_target`, `antifreeze_target` |
| Requested heating mode | Every exposed circuit | `mode` |
| Current day, night or frost-protection state | iSystem A/B/C | `active_mode` |
| Selected heating program, P1 to P4 | iSystem A/B/C | `program` |
| Heating pump status | A/B on both layouts, not C | `pump_on` |
| Water supply temperature | B on both layouts | `supply_temp` |
| Heating-curve slope and room-sensor influence setting | Every exposed circuit | `slope`, `ambient_influence` |
| Circuit minimum/maximum temperatures | Base B, iSystem B/C | `min_temp`, `max_temp` |
| Circuit A minimum/maximum temperatures | iSystem, cached | `config.zone_a_min`, `config.zone_a_max` |
| Hot-water temperature, requested mode and day/night targets | Both | `hot_water.temp`, `mode`, `day_target`, `night_target` |
| Additional hot-water temperature from the DPSM module | Base | `hot_water.temp_dpsm` |
| Reading labelled bottom-of-tank temperature, meaning unverified | iSystem | `hot_water.bottom_temp` |
| Current hot-water operating state | iSystem | `hot_water.active_mode` |

The heating curve describes how the controller adjusts heating temperature
as outdoor temperature changes. Room-sensor influence is returned as a
number, without a percentage interpretation. Requested `mode` and current
`active_mode` are different: automatic mode can currently be running either
the day or night setting.

### Controls and accepted values

Limits here are enforced by the library. The boiler may impose additional
restrictions. Writable values can also be read.

| Control | Base layout | iSystem | Field or method |
| --- | --- | --- | --- |
| Heating day/night target | A/B: 5 to 30 °C, 0.5 °C steps | A/B/C: 10 to 30 °C, 0.5 °C steps | `circuit_*.write("day_target", value)` or `"night_target"` |
| Heating frost-protection target | A/B: 5 to 30 °C, 0.5 °C steps | A/B/C: 3 to 20 °C, 0.5 °C steps | `circuit_*.write("antifreeze_target", value)` |
| Heating-curve slope | A/B: 0 to 4, 0.1 steps | A only: 0 to 4, 0.1 steps. B/C read-only | `circuit_*.write("slope", value)` |
| Heating mode | A/B | A/B/C | `set_circuit_a_mode()`, `set_circuit_b_mode()`, `set_circuit_c_mode()` |
| Hot-water day/night target | 10 to 80 °C, 1 °C steps | Same | `hot_water.write("day_target", value)` or `"night_target"` |
| Hot-water mode | Yes | Yes | `set_hot_water_mode()` |
| Summer/winter changeover temperature | 15 to 30.5 °C, 0.5 °C steps | Same | `settings.write("summer_winter_temp", value)` |
| Boiler minimum/maximum temperature | Writable, no library range limit | Read-only | `settings.boiler_min`, `boiler_max` |
| Date and time | `set_clock(datetime)`, untested on a base-layout boiler | `set_clock(datetime)`, verified on the iSystem test boiler | `set_clock()` |

`circuit_*` in this table means the appropriate circuit name, not literal
Python syntax. Both layouts also read the clock and reported type code from
`identity`. The base layout reads `identity.controller`, while iSystem reads
`identity.software_version`. Clock fields are `hour`, `minute`, `weekday`,
`day`, `month`, and `year`, returned as integers rather than a combined
datetime. A reported year of `26` stays `26`.
The external frost-protection threshold is available only as the read-only
`settings.ext_frost_threshold` on the base layout.

Supported mode values:

| Purpose | Python enum values |
| --- | --- |
| Heating follows its schedule | `HeatingMode.AUTO` |
| Temporary day or night override | `HeatingMode.TEMP_DAY`, `TEMP_NIGHT` |
| Persistent day or night override | `HeatingMode.PERM_DAY`, `PERM_NIGHT` |
| Heating frost protection | `HeatingMode.ANTIFREEZE` |
| Reported holiday state, read-only | `HeatingMode.HOLIDAY` |
| Hot water follows its schedule | `HotWaterMode.AUTO` |
| Temporary or persistent hot-water comfort override | `HotWaterMode.TEMP`, `PERM` |
| Reported current operating state, iSystem only | `ActiveMode.DAY`, `NIGHT`, `ANTIFREEZE` |

Temporary overrides have no duration argument. The library cannot set their
end time. These modes are not a general power on/off switch, and not every
enum value has been checked on hardware.

### Schedules

| Schedule reading | Availability | Python property |
| --- | --- | --- |
| Heating program P4, Monday to Sunday | iSystem A/B/C | `schedules.circuit_a_p4`, `circuit_b_p4`, `circuit_c_p4` |
| Hot-water comfort periods, Monday to Sunday | iSystem | `schedules.hot_water` |
| Auxiliary comfort periods, Monday to Sunday | iSystem | `schedules.auxiliary` |

All five are read-only and cached after a successful read. Heating programs
P1, P2 and P3 cannot be read as weekly schedules through this library.
Selecting a program or writing a schedule is not implemented.

### Installer settings and diagnostics

These additional iSystem readings help compare installations and investigate
the remaining register meanings. They are not installer controls.

All fields in the following table belong to **`config` and are cached**,
including the power and output values. Names follow the source register maps.
Where units or meanings have not been established, the library leaves them
as numbers rather than inventing an explanation.

| Information | Fields within `config` |
| --- | --- |
| Automatic adjustment values for A/B/C | `autoadapt_a`, `autoadapt_b`, `autoadapt_c` |
| Language code and building-inertia setting | `language`, `building_inertia` |
| Control bandwidth and mixing-valve adjustment | `bandwidth`, `three_way_valve_shift` |
| Minimum running time, burner delay and pump run-on settings, without defined time units | `min_running_time`, `burner_temporisation`, `pump_postrun` |
| Outdoor and A/B/C room-temperature calibration (°C) | `outside_calibration`, `zone_a_calibration`, `zone_b_calibration`, `zone_c_calibration` |
| A/B/C anticipation settings, without defined units | `anticipation_a`, `anticipation_b`, `anticipation_c` |
| Day/night values labelled “footprint” in the source maps, meaning not yet verified | `footprint_a_day`, `footprint_a_night`, `footprint_b_day`, `footprint_b_night`, `footprint_c_day`, `footprint_c_night` |
| A/B/C circuit type codes | `zone_a_type`, `zone_b_type`, `zone_c_type` |
| Circuit A minimum/maximum temperatures (°C) and maximum fan speed (rpm) | `zone_a_min`, `zone_a_max`, `max_fan_speed` |
| Mixing-valve temperature adjustment (°C) and bandwidth | `three_way_valve_temp_shift`, `three_way_valve_bandwidth` |
| Calculated target (°C), reported modulated power (%) and output-state code | `calc_setpoint`, `modulated_power`, `output_state` |

The following **`diagnostics` fields refresh on each update**. Except for
`aux_active_mode`, they are raw numbers, not decoded explanations or Boolean
fault flags.

| Information | Fields within `diagnostics` |
| --- | --- |
| Boiler operating-mode code and hot-water priority code | `boiler_active_mode`, `dhw_priority` |
| Auxiliary current operating state, decoded as `ActiveMode` | `aux_active_mode` |
| PCU controller state, substate, blocking and lockout codes | `pcu_state`, `pcu_substate`, `pcu_block`, `pcu_lock` |
| Boiler state, system input state and auxiliary type codes | `boiler_state`, `system_input_state`, `zone_aux_type` |

## Hardware testing so far

The recorded test installation is a Diematic iSystem reporting `D4`,
connected through a Waveshare RS485-to-network gateway. It has no circuit A.
The following are observations from that installation, not a compatibility
claim for every boiler with a similar panel.

| Check | Recorded result |
| --- | --- |
| Boiler, hot-water and heating readings | Reads worked through both layouts. This does not verify every optional sensor |
| Temperature targets, heating-curve slope and summer/winter threshold writes | Successful tests were recorded, with original values restored. There is no complete per-field, per-layout test matrix yet |
| iSystem circuit B/C heating modes | Writes to 659/667 worked and the panel followed without a refresh command |
| iSystem hot-water automatic/comfort modes | Both directions worked through 659. Choosing an override end time remains panel-only |
| Base-layout hot-water mode writes | Did not persist through register 17 on this installation. Use the iSystem result above as the tested path |
| Circuit A mode writes | Did not work on the installation without circuit A. Testing on an installation with A is still needed |
| Circuit B P4 and hot-water schedules | Compared with the panel. Editing B's P4 changed the matching data without changing A/C |
| Selected heating program | Circuit A's reported P1/P4/P2/P3 selections matched the panel |
| Auxiliary schedule | Readable, but no panel page was available to compare it with |
| Program-selection writes | Attempts on the test boiler were rejected. The library keeps this read-only |
| Fault readings | Register 465 reproduced words from the previous response during read-only tests. Neither a fault label nor the apparent no-fault value is reliable on this installation. Individual descriptions remain unverified |
| Clock writes | iSystem `set_clock()` verified on 2026-09-05: wrote a gross-wrong time and read it back, then restored the correct time. The clock is one register set mirrored at base 4-6/108-110 and iSystem 679-684, writing one moves the other. Plain integer writes are accepted, the base-layout `0xFF00` marker is not needed on the iSystem |

### Known limits

- Fault register 465 can contain leftover response data on the test iSystem.
  The library still exposes its decoded value, but cannot tell whether it is
  a real fault. This has not been checked on other controller types.
- Holiday mode can be read, but cannot be requested through the library.
  Holiday dates and durations remain panel-only. The decoded value `33`
  comes from an observation on the test iSystem installation, not a new
  hardware test of every panel type.
- Solar and exchanger readings were not added to the iSystem class because
  the test installation's solar module reported a fault and the readings
  were unreliable. Base-layout solar fields remain available, not verified.
- Reading an installer or diagnostic number successfully does not confirm
  its physical meaning, scale, or unit. Panel comparisons are still needed.
- There is no fault-reset command, schedule editor, or automatic discovery
  of fitted circuits and modules.

### Notes for register-map contributors

The test boiler accepts writes using Modbus function code 16, including
single-value writes. Function code 6 timed out. Numeric writable fields use
`force_fc16=True` for that reason.

Mode changes preserve shared heating/hot-water bits. The base layout uses
17 for A and hot water, and 26 for B. iSystem uses 653/659/667 for A/B/C, with
hot water controlled through 659. Register 640 reports the current hot-water
state, not its requested mode. Only base-layout Diematic 4 requests a panel
refresh. Never read refresh register 13 back: on the test boiler it returned
the first word of the previous response.

Read-only checks on 2026-09-05 found similar behavior at alarm register 465:
reading 70-110 followed by 427-465 returned `5` as the alarm, matching register
108 (day of month) at offset 38 in the preceding response. Reading 650-673
followed by 451-472 returned `200`, matching register 664 at offset 14.
Both sequences repeated twice. A single-register read of 465 likewise
returned `220` after register 8 and `24` after register 457. These were
comparisons between raw replies, not confirmations of panel faults.
Do not treat a different request range as a fix or filter those particular
numbers out: they may be legitimate fault codes on other controllers.

Keep schedule reads to one day, three registers per request. Longer reads
returned a different internal format on the test boiler. Program selection
uses registers 231 to 233. The circuit A panel comparison produced `0x2000`,
`0x2015`, `0x2007`, and `0x200E` for P1, P4, P2, and P3 respectively.

When proposing a register or decoder, cite the source and include the raw
value, script output, and panel value if available. For write tests, choose
a safe setpoint, record the original, write, read back, compare with the
panel, and restore the original every time. Do not probe unknown addresses
with writes.

For code contributions, the tests use a mock Modbus device and need no
boiler. Run these checks from the repository root:

```shell
uv run pytest
uv run ruff check
uv run ruff format --check
uv run mypy
```

## Credits

The register knowledge comes from other people's reverse engineering and
the De Dietrich register sheet, with further checks on the test boiler:

- Base register mapping, decoding and polling ranges:
  [Benoit3/Diematic_to_MQTT](https://github.com/Benoit3/Diematic_to_MQTT).
- Fault descriptions, DPSM mapping and P4 schedule names:
  [ngraziano/isystem-to-mqtt](https://github.com/ngraziano/isystem-to-mqtt).
- iSystem register mapping and reported type labels:
  [IgnacioHR/diematic_server](https://github.com/IgnacioHR/diematic_server),
  built on [gmasse/diematic](https://github.com/gmasse/diematic).
- Additional iSystem readings, installer settings and diagnostics:
  [ngraziano/isystem-mqtt-go](https://github.com/ngraziano/isystem-mqtt-go)
  and [45clouds/diematic2mqtt](https://github.com/45clouds/diematic2mqtt).
- Additional base-layout fields and the De Dietrich register spreadsheet
  ([modbus-registers-dedietrich.xlsx](https://github.com/ababilone/diematic-to-mqtt/blob/master/datasheets/modbus-registers-dedietrich.xlsx),
  sheets P1 to P7 with tables T1 to T3, the source for the paged addressing and
  the schedule and program-selection encodings):
  [ababilone/diematic-to-mqtt](https://github.com/ababilone/diematic-to-mqtt).
- Further cross-checks of the iSystem map:
  [piwai/diematic](https://github.com/piwai/diematic) and
  [gsternagl/python-diematic](https://github.com/gsternagl/python-diematic).
- Connection handling, register modelling and test-script helpers:
  [modbus-connection](https://github.com/home-assistant-libs/modbus-connection).

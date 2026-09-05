# diematic-modbus

Read and control a De Dietrich Diematic heating boiler over Modbus.

Built on [modbus-connection](https://github.com/home-assistant-libs/modbus-connection).
The library never opens a connection of its own. You hand it a `ModbusUnit`
and keep ownership of the socket. It has no Home Assistant imports.

> [!WARNING]
> Alpha. The register map comes from other people's reverse engineering,
> cross-checked against the De Dietrich register sheet, and was tested on
> the maintainer's own boiler, a Diematic iSystem that reports type code
> `D4`. On that boiler reads, setpoint writes and circuit B mode writes
> work. Circuit A and hot water mode writes are rejected because that
> boiler has no circuit A, so they are unproven on a boiler that has one.
> The clock write has never run against real hardware. See "Verified on
> hardware". Use at your own risk.

Two console layouts, two classes:

- `Diematic`: the base register page, for a Diematic 3 or Diematic 4 console,
  with or without a DPSM condensing module.
- `DiematicISystem`: the iSystem register page, which adds a third heating
  circuit, the selected time program per circuit, and read-only weekly
  schedules.

An iSystem console answers both pages on the same wire, so you can read the
same boiler through either class. You pick the class yourself, there is no
auto-detection. Diematic Delta only listens on the bus and never answers a
request, according to the projects this library builds on, so it has no
class here.

## What's available

| Bundle | `Diematic` | `DiematicISystem` | Reads | Writes |
| --- | --- | --- | --- | --- |
| `sensors` | yes | yes | outdoor, boiler, return and calculated boiler temperature, smoke temperature, water pressure, ionization current, fan speed, burner and hot water pump state, fault code. `Diematic` adds pump power, instant and average power, solar temperatures | no |
| `hot_water` | yes | yes | temperature, mode, current active mode on `DiematicISystem` | day and night target |
| `circuit_a` | yes | yes | room and calculated temperature, mode, pump state, ambient sensor influence, plus selected program and current active mode on `DiematicISystem` | day, night and frost target, slope |
| `circuit_b` | yes | yes | same as circuit A, plus supply temperature, slope, and circuit min and max temperature | day, night and frost target, plus slope on `Diematic` |
| `circuit_c` | no | yes | room and calculated temperature, selected program, ambient sensor influence, slope, and circuit min and max temperature. No mode register exists for circuit C | day, night and frost target |
| `settings` | yes | yes | external frost threshold on `Diematic`, boiler min and max on `DiematicISystem` | summer to winter threshold, plus boiler min and max on `Diematic` |
| `config` | no | yes | installer tuning parameters (heating curve calibration, footprints, anticipation, zone types, bandwidth, timings, language). Read once, then cached | no |
| `diagnostics` | no | yes | boiler active mode, PCU state, boiler state word, system input and auxiliary type, all as raw codes | no |
| `identity` | yes | yes | boiler type code, controller or software version, clock | no |
| `schedules` | no | yes | program P4 of each heating circuit, the hot water program, the auxiliary program. Read once, then cached | no |

| Method | `Diematic` | `DiematicISystem` | Does |
| --- | --- | --- | --- |
| `async_update()` | yes | yes | refresh every bundle, return an `UpdateReport` |
| `async_read_raw()` | yes | yes | dump every register the layout serves, undecoded |
| `bundle.write(field, value)` | yes | yes | write one setpoint, snapped to the step the boiler accepts |
| `set_circuit_a_mode(mode)` | yes | yes | write heating mode on register 17, no effect without circuit A |
| `set_circuit_b_mode(mode)` | yes | yes | write heating mode on register 26 |
| `set_hot_water_mode(mode)` | yes | yes | write hot water mode on register 17, no effect without circuit A |
| `set_clock(moment)` | yes | no | write the regulator clock, never run against real hardware |

## Install

Not yet on PyPI:

```bash
pip install -e .            # library only, you choose the Modbus backend
pip install -e ".[cli]"     # also the read_diematic.py script and its tmodbus backend
```

## Use

```python
import asyncio

from modbus_connection import ModbusTcpParams
from modbus_connection.tmodbus import ModbusConnection

from diematic_modbus import Diematic, DiematicVariant, HeatingMode


async def main() -> None:
    params = ModbusTcpParams(host="192.168.1.50", port=502, framer="rtu")
    conn = ModbusConnection(params, message_spacing=0.05)
    try:
        diematic = Diematic(conn.for_unit(10), variant=DiematicVariant.DIEMATIC_3)
        await diematic.async_update()

        print(diematic.sensors.outdoor_temp, diematic.hot_water.temp)
        if diematic.circuit_a_present:
            print(diematic.circuit_a.room_temp, diematic.circuit_a.mode)

        await diematic.hot_water.write("day_target", 55)
        await diematic.set_circuit_a_mode(HeatingMode.AUTO)
    finally:
        await conn.close()


asyncio.run(main())
```

A Diematic behind an RS485-to-TCP gateway needs `framer="rtu"`. A small
`message_spacing` gives the boiler time between requests on the shared bus.
For a direct serial link use `ModbusSerialParams(device="/dev/ttyUSB0")`.
Inside Home Assistant, pass a `ModbusUnit` from the connection Home Assistant
already manages. Diematic consoles usually answer on unit id 10.

`circuit_a_present`, `circuit_b_present` and `circuit_c_present` report which
circuits have a room sensor. Pass `force_circuit_a=True` and friends to
override that detection.

Setpoints write by field name and snap to the step the boiler accepts. Modes
go through `set_*_mode` instead of a field write because each mode register
also holds a second setting the library has to preserve. Circuit A mode and
hot water mode share register 17, so a boiler without circuit A ignores
writes to both.

A value the boiler reports as absent decodes to `None`. A fault code the
library does not know is returned as its raw integer so a fault is never
hidden.

`async_update()` returns an `UpdateReport`. A refused register range only
fails the bundles that depend on it, which keep their last value. Everything
else still comes back fresh. A dead link raises `ModbusConnectionError`
instead.

```python
report = await diematic.async_update()
if not report.complete:
    print("stale bundles:", report.failed)
```

## iSystem schedules

`schedules.circuit_a_p4`, `circuit_b_p4`, `circuit_c_p4`, `hot_water` and
`auxiliary` each map isoweekday (1 is Monday) to that day's comfort periods
as `datetime.time` pairs. A period that runs to the end of the day ends at
`time(0, 0)`:

```python
{1: [(time(6, 0), time(8, 0)), (time(16, 0), time(22, 0))], 2: [...], ...}
```

`circuit_a.program`, `circuit_b.program` and `circuit_c.program` report which
program, 1 to 4, each circuit runs. Each heating circuit has four programs on
the console but only P4 is on the Modbus map. P1 is fixed at 06:00 to 22:00
according to the iSystem manual. P2 and P3 can be edited on the console but
no register anywhere in 1 to 1400 changes when you do.

Schedules are read once and then cached, since a weekly program does not
change between polls. Each one is its own bundle in the `UpdateReport`,
named `schedules.circuit_a_p4` and so on. Schedules and program selection
are read-only.

## Testing your boiler

The `cli` extra installs a script that connects, reads everything the chosen
layout serves, and prints it. Reading is safe. The script writes nothing
unless you pass `--probe-write`.

```bash
uv run scripts/read_diematic.py 192.168.1.50 --port 502 --unit 10 --variant 3 --layout both
```

- The first argument is the gateway IP, or the serial device with
  `--transport serial /dev/ttyUSB0`.
- `--unit` is the Modbus address of the console, 10 unless you changed it.
- `--variant 3` or `--variant 4` only affects mode writes (a Diematic 4 needs
  a panel refresh afterwards). It does not matter for a read-only run.
- `--layout both` dumps the base page and then the iSystem page. If you know
  your console is not an iSystem, use `--layout base`. Only an iSystem has
  been tested, so what a Diematic 3 or 4 prints for the iSystem page is
  unknown. Please report it.

A healthy run prints one table per bundle with decoded values, the three
`circuit_*_present` flags and, on the iSystem layout, one line per weekday
for each schedule. Compare the temperatures and the schedules with your
console. If `identity.boiler_type` prints a code you do not recognize, or a
value looks wrong, open an issue with the output of `--debug`, which logs the
raw Modbus traffic.

If the script prints "Read failed", check the wiring, the unit id and, for a
gateway, that it forwards RTU frames unchanged. A timeout on a single
register is normal on a busy RS485 bus, retry once before concluding
anything.

`--probe-write` writes the hot water day setpoint back to its current value,
then reads it back. It changes nothing on the boiler and tells you whether
writes get through.

## Verified on hardware

Everything below was checked against the maintainer's own boiler, a
Diematic iSystem reporting type `D4`, and every write was restored to its
original value afterwards. Treat anything not in this table as unverified.

| Feature | Status |
| --- | --- |
| Reading sensors, hot water, and circuit values | Works, on both layouts |
| Setpoint writes (day, night, frost targets, slope, summer to winter threshold) | Works |
| Circuit B mode write | Works |
| Circuit A mode write, hot water mode write | Rejected on the maintainer's boiler, which has no circuit A. Untested on a boiler that has circuit A |
| Weekly schedules and the active program (reading) | Works, matches the console |
| Program selection (choosing a different program) | Not possible, the maintainer's boiler rejects every write tried |
| Setting the clock | Implemented, but never run against a real boiler |
| Writing the weekly schedule | Not implemented |
| Solar and exchanger readings, iSystem layout | Left out, the maintainer's boiler has a solar module reporting a fault and the raw readings looked unreliable |
| Fault codes | The table matches "no fault", individual fault codes are unconfirmed until a real one occurs |

<details>
<summary>Technical detail behind the table above</summary>

- The boiler only accepts function code 16 for writes, function code 6
  times out.
- Circuit B mode writes go through register 26. Circuit A and hot water
  mode share register 17, and on the maintainer's boiler, which has no
  circuit A, a write there reverts on the next read regardless of the
  Diematic 4 panel refresh.
- Editing program P4 of circuit B on the console changed the matching
  registers within seconds and left circuits A and C alone. The hot water
  program matched too. The auxiliary program has no console page to
  compare against.
- Switching circuit A through P1, P4, P2 and P3 on the console produced
  0x2000, 0x2015, 0x2007 and 0x200E in register 231, consistent with the
  low byte being 7 times (4 times circuit index plus program index).
  Writing registers 231 to 233 was rejected in every encoding tried.
- A schedule read must stay to one day, three registers, per request. A
  longer read returns the boiler's internal week, five words per day,
  starting at the day the read began and wrapping inside that program.
- Register 13, the Diematic 4 panel refresh target, returns the first word
  of the previous response when read, so the library never reads it back.

</details>

## Credits

- Register maps and decoding rules:
  [Diematic_to_MQTT](https://github.com/Benoit3/Diematic_to_MQTT) (Benoit3)
- Fault table, DPSM confirmation, and the naming of the schedule blocks as
  program P4:
  [isystem-to-mqtt](https://github.com/ngraziano/isystem-to-mqtt) (ngraziano)
- iSystem register map and type code table:
  [diematic_server](https://github.com/IgnacioHR/diematic_server) (Ignacio
  Hernandez-Ros), built on [gmasse/diematic](https://github.com/gmasse/diematic)
- Register spreadsheet:
  [diematic-to-mqtt](https://github.com/ababilone/diematic-to-mqtt) (ababilone)
- Further cross-check:
  [python-diematic](https://github.com/gsternagl/python-diematic) (gsternagl)
- Built on
  [modbus-connection](https://github.com/home-assistant-libs/modbus-connection)

All of the above, except modbus-connection, are MIT licensed.

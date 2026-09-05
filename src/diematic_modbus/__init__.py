"""Read and control a De Dietrich Diematic heating regulator over Modbus.

Hand a :class:`~modbus_connection.ModbusUnit` to :class:`Diematic`. The caller
owns the connection and its lifecycle::

    from modbus_connection import ModbusTcpParams
    from modbus_connection.tmodbus import ModbusConnection

    params = ModbusTcpParams(host="192.168.1.50", port=502, framer="rtu")
    conn = ModbusConnection(params)
    diematic = Diematic(conn.for_unit(10))
    await diematic.async_update()
    print(diematic.sensors.outdoor_temp, diematic.hot_water.temp)
    await conn.close()
"""

from ._base import UpdateReport
from .components import CircuitA, CircuitB, HotWater, Identity, Sensors, Settings
from .enums import ActiveMode, DiematicVariant, HeatingMode, HotWaterMode
from .faults import MODULENS_FAULTS
from .isystem import DiematicISystem, Schedules, WeekProgram
from .models import MODEL_CODES
from .regulator import Diematic

__all__ = [
    "MODEL_CODES",
    "MODULENS_FAULTS",
    "ActiveMode",
    "CircuitA",
    "CircuitB",
    "Diematic",
    "DiematicISystem",
    "DiematicVariant",
    "HeatingMode",
    "HotWater",
    "HotWaterMode",
    "Identity",
    "Schedules",
    "Sensors",
    "Settings",
    "UpdateReport",
    "WeekProgram",
]

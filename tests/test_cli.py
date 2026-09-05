import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from modbus_connection import ModbusConnectionError, ModbusError
from modbus_connection.exceptions import IllegalDataAddressError


@pytest.fixture
def script(monkeypatch, mock_modbus_unit):
    path = Path(__file__).resolve().parents[1] / "scripts" / "read_diematic.py"
    spec = importlib.util.spec_from_file_location("read_diematic", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    connection = SimpleNamespace(
        for_unit=Mock(return_value=mock_modbus_unit), close=AsyncMock()
    )
    monkeypatch.setattr(module, "connect_from_args", AsyncMock(return_value=connection))
    mock_modbus_unit.holding.update(
        {17: 8, 26: 8, 653: 8, 659: 8, 667: 8, 59: 550, 672: 550}
    )
    return module


@pytest.mark.parametrize("layout", ["base", "isystem", "both"])
@pytest.mark.parametrize("probe", [False, True])
async def test_successful_run(script, mock_modbus_unit, monkeypatch, layout, probe):
    args = ["read_diematic.py", "mock", "--layout", layout]
    if probe:
        args.append("--probe-write")
    monkeypatch.setattr("sys.argv", args)
    writes = []
    mock_modbus_unit.on_write(writes.append)
    assert await script._main() == 0
    assert len(writes) == int(probe)
    if probe:
        assert writes[0].address == (59 if layout == "base" else 672)
        assert writes[0].values == [550]
        assert writes[0].function_code == 16
    script.connect_from_args.return_value.close.assert_awaited_once()


@pytest.mark.parametrize("address", [75, 602, 672, 126])
@pytest.mark.parametrize("probe", [False, True])
async def test_partial_read_fails_without_writes(
    script, mock_modbus_unit, monkeypatch, capsys, address, probe
):
    args = ["read_diematic.py", "mock", "--layout", "both"]
    if probe:
        args.append("--probe-write")
    monkeypatch.setattr("sys.argv", args)
    mock_modbus_unit.fail_read(address, IllegalDataAddressError())
    writes = []
    mock_modbus_unit.on_write(writes.append)
    assert await script._main() == 1
    assert writes == []
    output = capsys.readouterr().out
    assert "=== Base layout ===" in output
    assert "=== iSystem layout ===" in output
    assert "WARNING" in output
    if probe:
        assert "Write check skipped" in output
    script.connect_from_args.return_value.close.assert_awaited_once()


@pytest.mark.parametrize("layout", ["base", "isystem"])
@pytest.mark.parametrize("raw", [534, 90, 810, 0xFFFF])
async def test_probe_skips_missing_or_changed_target(
    script, mock_modbus_unit, monkeypatch, capsys, layout, raw
):
    monkeypatch.setattr(
        "sys.argv", ["read_diematic.py", "mock", "--layout", layout, "--probe-write"]
    )
    mock_modbus_unit.holding[59 if layout == "base" else 672] = raw
    writes = []
    mock_modbus_unit.on_write(writes.append)
    assert await script._main() == 1
    assert writes == []
    assert "Write check skipped" in capsys.readouterr().out
    script.connect_from_args.return_value.close.assert_awaited_once()


@pytest.mark.parametrize("failure", ["write", "readback", "mismatch", "refresh"])
async def test_probe_failure_returns_failure(
    script, mock_modbus_unit, monkeypatch, capsys, failure
):
    monkeypatch.setattr(
        "sys.argv", ["read_diematic.py", "mock", "--layout", "isystem", "--probe-write"]
    )
    writes = []
    mock_modbus_unit.on_write(writes.append)
    if failure == "write":
        mock_modbus_unit.fail_write(672, ModbusError("write rejected"))
    elif failure == "readback":
        mock_modbus_unit.on_write(
            lambda event: mock_modbus_unit.fail_read(
                672, ModbusError("readback failed")
            )
        )
    elif failure == "mismatch":
        mock_modbus_unit.on_write(
            lambda event: mock_modbus_unit.holding.update({672: 540})
        )
    else:
        original_dump = script._dump

        async def fail_after_dump(*args):
            result = await original_dump(*args)
            mock_modbus_unit.fail_read(672, ModbusError("refresh failed"))
            return result

        monkeypatch.setattr(script, "_dump", fail_after_dump)
    assert await script._main() == 1
    if failure == "refresh":
        assert writes == []
    output = capsys.readouterr().out
    assert (
        "MISMATCH" in output
        if failure == "mismatch"
        else "Write check failed" in output
    )
    script.connect_from_args.return_value.close.assert_awaited_once()


@pytest.mark.parametrize("fresh_raw", [560, 534, 0xFFFF])
async def test_probe_uses_fresh_target(
    script, mock_modbus_unit, monkeypatch, fresh_raw
):
    monkeypatch.setattr(
        "sys.argv", ["read_diematic.py", "mock", "--layout", "isystem", "--probe-write"]
    )
    original_dump = script._dump

    async def change_after_dump(*args):
        result = await original_dump(*args)
        mock_modbus_unit.holding[672] = fresh_raw
        return result

    monkeypatch.setattr(script, "_dump", change_after_dump)
    writes = []
    mock_modbus_unit.on_write(writes.append)
    assert await script._main() == (0 if fresh_raw == 560 else 1)
    if fresh_raw == 560:
        assert len(writes) == 1
        assert writes[0].values == [560]
    else:
        assert writes == []
    script.connect_from_args.return_value.close.assert_awaited_once()


@pytest.mark.parametrize("failure", ["connect", "read", "unexpected"])
async def test_connection_failures_and_cleanup(
    script, mock_modbus_unit, monkeypatch, failure
):
    monkeypatch.setattr("sys.argv", ["read_diematic.py", "mock", "--probe-write"])
    close = script.connect_from_args.return_value.close
    if failure == "connect":
        script.connect_from_args.side_effect = ModbusConnectionError("offline")
    elif failure == "read":
        mock_modbus_unit.fail_requests(ModbusConnectionError("offline"))
    else:
        monkeypatch.setattr(script, "_dump", AsyncMock(side_effect=RuntimeError("bug")))
    writes = []
    mock_modbus_unit.on_write(writes.append)
    if failure == "unexpected":
        with pytest.raises(RuntimeError, match="bug"):
            await script._main()
    else:
        assert await script._main() == 1
    assert writes == []
    if failure == "connect":
        close.assert_not_awaited()
    else:
        close.assert_awaited_once()

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

pytest.importorskip("pwn")

from tiny_dec.cli import main as cli_main


def test_cli_info_prints_binary_metadata(
    fixture_binary: Callable[[str], Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    binary = fixture_binary("fixture_basic_O0_nopie")

    exit_code = cli_main(["info", str(binary)])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "entrypoint:" in output
    assert "entry_points:" in output
    assert "main:" in output
    assert "sections:" in output
    assert "symbols:" in output
    assert "external_functions:" in output


def test_cli_info_reports_missing_binary_cleanly(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = cli_main(["info", "/workspace/does_not_exist.elf"])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert captured.out == ""
    assert "info_error:" in captured.err
    assert "does_not_exist.elf" in captured.err


def test_cli_decompile_stage_loader_outputs_snapshot(
    fixture_binary: Callable[[str], Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    binary = fixture_binary("fixture_basic_O0_nopie")

    exit_code = cli_main(["decompile", str(binary), "--stage", "loader"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "stage: loader" in output
    assert "loader:" in output
    assert "sections:" in output


def test_cli_decompile_reports_missing_binary_cleanly(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = cli_main(["decompile", "/workspace/does_not_exist.elf"])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert captured.out == ""
    assert "decompile_error:" in captured.err
    assert "does_not_exist.elf" in captured.err

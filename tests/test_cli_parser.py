from __future__ import annotations

import builtins

import pytest

from tiny_dec.cli import STAGE_DETAILS, main as cli_main


def test_cli_root_help_lists_commands_and_examples(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli_main(["--help"])

    captured = capsys.readouterr()

    assert excinfo.value.code == 0
    assert "Inspect a binary or decompile it through the tiny-dec pipeline." in captured.out
    assert "commands:" in captured.out
    assert "decompile" in captured.out
    assert "info" in captured.out
    assert "Examples:" in captured.out
    assert "tiny-dec decompile ./prog.elf --func main --stage ssa" in captured.out


def test_cli_decompile_help_lists_stage_guide_and_examples(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli_main(["decompile", "--help"])

    captured = capsys.readouterr()

    assert excinfo.value.code == 0
    assert "Run the tiny-dec pipeline for one function" in captured.out
    assert "--stage STAGE" in captured.out
    assert "The default stage is `c`, which renders final C." in captured.out
    assert "tiny-dec decompile ./prog.elf --func 0x110d0 --stage c_lowering" in captured.out
    for stage, description in STAGE_DETAILS:
        assert f"  {stage:<16} {description}" in captured.out


def test_cli_info_help_lists_metadata_examples_and_scan_size(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli_main(["info", "--help"])

    captured = capsys.readouterr()

    assert excinfo.value.code == 0
    assert "Inspect binary metadata without running the decompiler pipeline." in captured.out
    assert "--scan-size SCAN_SIZE" in captured.out
    assert "tiny-dec info ./prog.elf --scan-size 1024" in captured.out


def test_cli_help_does_not_import_loader_runtime_dependencies(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    real_import = builtins.__import__

    def guarded_import(
        name: str,
        globals: dict[str, object] | None = None,
        locals: dict[str, object] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> object:
        if name == "pwn" or name.startswith("pwn."):
            raise AssertionError("help path should not import pwn")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)

    with pytest.raises(SystemExit) as excinfo:
        cli_main(["--help"])

    captured = capsys.readouterr()

    assert excinfo.value.code == 0
    assert "usage: tiny-dec" in captured.out


def test_cli_requires_a_command(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli_main([])

    captured = capsys.readouterr()

    assert excinfo.value.code == 2
    assert "the following arguments are required: command" in captured.err


def test_cli_decompile_requires_binary(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli_main(["decompile"])

    captured = capsys.readouterr()

    assert excinfo.value.code == 2
    assert "the following arguments are required: binary" in captured.err


def test_cli_info_requires_binary(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli_main(["info"])

    captured = capsys.readouterr()

    assert excinfo.value.code == 2
    assert "the following arguments are required: binary" in captured.err


def test_cli_decompile_rejects_invalid_stage_choice(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli_main(["decompile", "./prog.elf", "--stage", "not_a_stage"])

    captured = capsys.readouterr()

    assert excinfo.value.code == 2
    assert "invalid choice: 'not_a_stage'" in captured.err

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("pwn")

from tiny_dec.analysis.calls import build_program_call_facts, format_program_call_facts
from tiny_dec.loader import ProgramView


def _resolve_main_address(view: ProgramView) -> int:
    main_resolution = view.find_main()
    if main_resolution.address is not None:
        return main_resolution.address
    return view.entrypoint


def render_calls_fixture_snapshots(fixture_bin_dir: Path) -> str:
    rendered: list[str] = []

    for binary in sorted(fixture_bin_dir.glob("*.elf")):
        view = ProgramView(binary)
        start = _resolve_main_address(view)
        rendered.extend(
            [
                f"binary: {binary.name}",
                f"start: {start:#x}",
                "calls:",
            ]
        )
        snapshot = format_program_call_facts(build_program_call_facts(view, start))
        rendered.extend(f"  {line}" for line in snapshot.splitlines())
        rendered.append("")

    return "\n".join(rendered).rstrip()


def _fixture_section(rendered: str, fixture_name: str) -> str:
    return rendered.split(f"binary: {fixture_name}", 1)[1].split("\nbinary: ", 1)[0]


def test_calls_e2e_harness_renders_all_fixture_binaries(
    fixture_bin_dir: Path,
) -> None:
    binaries = sorted(fixture_bin_dir.glob("*.elf"))
    assert binaries, "expected at least one compiled fixture binary"

    combined = render_calls_fixture_snapshots(fixture_bin_dir)
    combined_again = render_calls_fixture_snapshots(fixture_bin_dir)

    assert combined == combined_again
    assert f"binary: {binaries[0].name}" in combined
    assert "\ncalls:\n" in combined
    assert "mem=[" in combined
    assert "sig=malloc" in combined
    stack_args_section = _fixture_section(combined, "fixture_stack_args_O0_nopie.elf")
    assert "stack_args=[stack+0=" in stack_args_section
    assert "stack+4=" in stack_args_section
    assert "stack+8=" not in stack_args_section
    assert "stack+12=" not in stack_args_section
    indirect_const_section = _fixture_section(combined, "fixture_indirect_const_O0_nopie.elf")
    assert "target_value=x11_1:4" in indirect_const_section
    assert "x11=x11_1:4" not in indirect_const_section
    indirect_select_section = _fixture_section(combined, "fixture_indirect_select_O0_nopie.elf")
    assert "target_value=x12_2:4" in indirect_select_section
    assert "x12=x12_2:4" not in indirect_select_section

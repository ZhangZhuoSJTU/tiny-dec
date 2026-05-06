"""Deterministic text formatting helpers for loader-stage debugging."""

from __future__ import annotations

from collections.abc import Iterable

from tiny_dec.loader.program_view import ProgramView

def _append_section(lines: list[str], header: str, items) -> None:
    lines.append("")
    lines.append(header)
    if items:
        lines.extend(f"  {item.to_pretty_line()}" for item in items)
    else:
        lines.append("  <none>")


def format_loader_snapshot(
    view: ProgramView,
    *,
    section_names: Iterable[str] | None = None,
    show_externals: bool = False,
    scan_size: int = 512,
) -> str:
    main_resolution = view.find_main(scan_size=scan_size)
    lines = [
        f"binary: {view.path}",
        f"arch: {view.arch} ({view.bits}-bit, {view.endian}-endian)",
        f"entrypoint: {view.entrypoint:#x}",
        f"main: {main_resolution.address:#x}"
        if main_resolution.address is not None
        else "main: <unresolved>",
        f"main_source: {main_resolution.source}",
        "",
        "sections:",
    ]

    sections = view.sections(section_names)
    lines.extend(f"  {section.to_pretty_line()}" for section in sections)

    if show_externals:
        _append_section(lines, "external_functions:", view.external_functions())

    return "\n".join(lines)


def format_binary_info(
    view: ProgramView,
    *,
    scan_size: int = 512,
) -> str:
    main_resolution = view.find_main(scan_size=scan_size)
    entry_points = ", ".join(f"{address:#x}" for address in view.entry_points)

    lines = [
        f"binary: {view.path}",
        f"arch: {view.arch} ({view.bits}-bit, {view.endian}-endian)",
        f"entrypoint: {view.entrypoint:#x}",
        f"entry_points: {entry_points}",
        f"main: {main_resolution.address:#x}"
        if main_resolution.address is not None
        else "main: <unresolved>",
        f"main_source: {main_resolution.source}",
        "",
        "sections:",
    ]

    sections = view.all_sections()
    if sections:
        lines.extend(f"  {section.to_pretty_line()}" for section in sections)
    else:
        lines.append("  <none>")

    _append_section(lines, "symbols:", view.symbols())
    _append_section(lines, "external_functions:", view.external_functions())

    return "\n".join(lines)

"""Deterministic text formatting helpers for loader-stage debugging."""

from __future__ import annotations

from collections.abc import Iterable

from tiny_dec.loader.program_view import ProgramView


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
        lines.append("")
        lines.append("external_functions:")
        lines.extend(f"  {fn.to_pretty_line()}" for fn in view.external_functions())

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

    lines.append("")
    lines.append("symbols:")
    symbols = view.symbols()
    if symbols:
        lines.extend(f"  {symbol.to_pretty_line()}" for symbol in symbols)
    else:
        lines.append("  <none>")

    lines.append("")
    lines.append("external_functions:")
    externals = view.external_functions()
    if externals:
        lines.extend(f"  {fn.to_pretty_line()}" for fn in externals)
    else:
        lines.append("  <none>")

    return "\n".join(lines)

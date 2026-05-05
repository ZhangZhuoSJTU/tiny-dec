from __future__ import annotations

import argparse
import sys

STAGE_CHOICES = (
    "loader",
    "decode",
    "pcode",
    "disasm",
    "ir",
    "simplify",
    "dataflow",
    "ssa",
    "calls",
    "stack",
    "memory",
    "scalar_types",
    "aggregate_types",
    "variables",
    "range",
    "interproc",
    "structuring",
    "c_lowering",
    "c",
)

STAGE_DETAILS = (
    ("loader", "post_00  ELF metadata, symbols, sections, and main discovery"),
    ("decode", "post_01  RV32I instruction decoding"),
    ("pcode", "post_02  semantic p-code lift per instruction"),
    ("disasm", "post_03  recursive function disassembly"),
    ("ir", "post_04  low-level function and program IR containers"),
    ("simplify", "post_05  canonical low-level IR cleanup"),
    ("dataflow", "post_06  intraprocedural fact propagation"),
    ("ssa", "post_07  low-level SSA form"),
    ("calls", "post_08  call target, ABI, and stack-arg facts"),
    ("stack", "post_09  frame layout and stack-slot recovery"),
    ("memory", "post_10  memory partitions and address facts"),
    ("scalar_types", "post_11  scalar type recovery"),
    ("aggregate_types", "post_12  aggregate and field typing"),
    ("variables", "post_13  high-level variable grouping"),
    ("range", "post_14  predicate and range refinement"),
    ("interproc", "post_15  summaries and prototype refinement"),
    ("structuring", "post_16  control-structure recovery"),
    ("c_lowering", "post_17  C-like IR before final rendering"),
    ("c", "post_18  rendered C output (default)"),
)


class _HelpFormatter(
    argparse.ArgumentDefaultsHelpFormatter,
    argparse.RawDescriptionHelpFormatter,
):
    """Preserve multi-line examples while still showing defaults."""


def _stage_guide() -> str:
    lines = ["Stages:"]
    for stage, description in STAGE_DETAILS:
        lines.append(f"  {stage:<16} {description}")
    return "\n".join(lines)


ROOT_EPILOG = """Examples:
  tiny-dec info ./prog.elf
  tiny-dec decompile ./prog.elf
  tiny-dec decompile ./prog.elf --func main --stage ssa
"""

DECOMPILE_EPILOG = f"""Examples:
  tiny-dec decompile ./prog.elf
  tiny-dec decompile ./prog.elf --func main --stage calls
  tiny-dec decompile ./prog.elf --func 0x110d0 --stage c_lowering

The default stage is `c`, which renders final C.

{_stage_guide()}
"""

INFO_EPILOG = """Examples:
  tiny-dec info ./prog.elf
  tiny-dec info ./prog.elf --scan-size 1024
"""


def _cmd_decompile(args: argparse.Namespace) -> int:
    from tiny_dec.decode import DecodeError
    from tiny_dec.loader import ProgramView, TinyDecLoaderError
    from tiny_dec.pipeline import decompile_function, resolve_function_address

    try:
        view = ProgramView(args.binary)
        if args.strict_func and resolve_function_address(view, args.func) is None:
            print(
                f"decompile_error: unresolved function selector '{args.func}'",
                file=sys.stderr,
            )
            return 2
        output = decompile_function(view, func=args.func, stage=args.stage)
    except (DecodeError, OSError, TinyDecLoaderError, ValueError) as exc:
        print(f"decompile_error: {exc}", file=sys.stderr)
        return 2

    print(output)
    return 0


def _cmd_info(args: argparse.Namespace) -> int:
    from tiny_dec.loader import ProgramView, TinyDecLoaderError, format_binary_info

    try:
        view = ProgramView(args.binary)
        print(format_binary_info(view, scan_size=args.scan_size))
    except (OSError, TinyDecLoaderError) as exc:
        print(f"info_error: {exc}", file=sys.stderr)
        return 2
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tiny-dec",
        formatter_class=_HelpFormatter,
        description=(
            "Inspect a binary or decompile it through the tiny-dec pipeline.\n\n"
            "Use `tiny-dec info` for loader-visible binary metadata and "
            "`tiny-dec decompile` for either final C output or an "
            "intermediate debug stage."
        ),
        epilog=ROOT_EPILOG,
    )
    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
        title="commands",
    )

    decompile_parser = subparsers.add_parser(
        "decompile",
        formatter_class=_HelpFormatter,
        help="Decompile a binary or stop at an intermediate pipeline stage",
        description=(
            "Run the tiny-dec pipeline for one function and print either the "
            "final rendered C or the selected intermediate stage."
        ),
        epilog=DECOMPILE_EPILOG,
    )
    decompile_parser.add_argument("binary", help="Path to ELF binary")
    decompile_parser.add_argument(
        "--func",
        default="main",
        help="Function selector: symbol name, decimal address, or hex address",
    )
    decompile_parser.add_argument(
        "--stage",
        choices=STAGE_CHOICES,
        metavar="STAGE",
        default="c",
        help="Pipeline stage at which to stop instead of rendering past it",
    )
    decompile_parser.add_argument(
        "--strict-func",
        action="store_true",
        help="Return non-zero when the function selector cannot be resolved",
    )
    decompile_parser.set_defaults(handler=_cmd_decompile)

    info_parser = subparsers.add_parser(
        "info",
        formatter_class=_HelpFormatter,
        help="Print loader-visible binary metadata",
        description=(
            "Inspect binary metadata without running the decompiler pipeline. "
            "This surfaces the loader view: architecture, entrypoints, "
            "sections, symbols, and named externals."
        ),
        epilog=INFO_EPILOG,
    )
    info_parser.add_argument("binary", help="Path to ELF binary")
    info_parser.add_argument(
        "--scan-size",
        type=int,
        default=512,
        help="Bytes to scan from the entrypoint while resolving main",
    )
    info_parser.set_defaults(handler=_cmd_info)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return args.handler(args)

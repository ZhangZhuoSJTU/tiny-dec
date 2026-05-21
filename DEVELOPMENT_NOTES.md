# tiny-dec

Educational tiny decompiler repository for RV32I Linux ELF binaries.

Start with:
- [implementation.md](implementation.md) for the current architecture and implemented surfaces
- [development.md](development.md) for the active development workflow

## Current status

Implemented stages (19-stage pipeline from ELF loading through rendered C):

| Post | Stage | Owner |
|------|-------|-------|
| 00 | Loader | `tiny_dec/loader/` |
| 01 | Decode | `tiny_dec/decode/` |
| 02 | Semantic p-code lift | `tiny_dec/ir/` |
| 03 | Recursive disassembly | `tiny_dec/disasm/` |
| 04 | IR containers | `tiny_dec/ir/` |
| 05 | Canonical simplification | `tiny_dec/analysis/simplify/` |
| 06 | Intraprocedural dataflow | `tiny_dec/analysis/dataflow/` |
| 07 | Low-level SSA | `tiny_dec/analysis/ssa/` |
| 08 | Call modeling | `tiny_dec/analysis/calls/` |
| 09 | Stack and frame recovery | `tiny_dec/analysis/stack/` |
| 10 | Memory modeling | `tiny_dec/analysis/memory/` |
| 11 | Scalar type recovery | `tiny_dec/analysis/types/` |
| 12 | Aggregate type recovery | `tiny_dec/analysis/types/` |
| 13 | Variable recovery | `tiny_dec/analysis/highvars/` |
| 14 | Range and predicate refinement | `tiny_dec/analysis/range/` |
| 15 | Interprocedural summaries | `tiny_dec/analysis/interproc/` |
| 16 | Control-structure recovery | `tiny_dec/structuring/` |
| 17 | C-like IR lowering | `tiny_dec/c_emit/` |
| 18 | Rendered C and pipeline driver | `tiny_dec/c_emit/`, `tiny_dec/pipeline/` |

For package ownership, stable artifacts, and CLI/debug surfaces, see
[implementation.md](implementation.md).

## Development commands

Run the current stage harness:
```bash
poetry run pytest -q tests/posts/post_18_c_printer_pipeline/test_c_printer_pipeline_e2e_harness.py
```

Run all staged tests:
```bash
poetry run pytest -q tests/posts
```

Run Ruff:
```bash
poetry run ruff check tiny_dec tests/posts
```

Run MyPy:
```bash
poetry run mypy tiny_dec tests/posts/post_00_loader tests/posts/post_01_decode tests/posts/post_02_lift_pcode tests/posts/post_03_disasm tests/posts/post_04_ir_containers tests/posts/post_05_simplify tests/posts/post_06_dataflow tests/posts/post_07_ssa tests/posts/post_08_calls tests/posts/post_09_stack tests/posts/post_10_memory tests/posts/post_11_scalar_types tests/posts/post_12_aggregate_types tests/posts/post_13_variables tests/posts/post_14_range tests/posts/post_15_interproc tests/posts/post_16_structuring tests/posts/post_17_c_lowering tests/posts/post_18_c_printer_pipeline
```

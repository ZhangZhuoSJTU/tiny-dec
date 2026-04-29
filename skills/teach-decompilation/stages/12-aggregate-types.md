# Stage 12: Aggregate Types

## What It Does
This stage recovers **struct and array layouts** from patterns of pointer arithmetic and field accesses. When the code accesses `ptr + 0` and `ptr + 4` with different values, this stage infers a struct with two 4-byte fields. When accesses use `ptr + i*8`, it infers an array of 8-byte elements.

**Analogy:** Imagine watching someone reach into the same box at regular intervals, grabbing things at the same offsets each time. You can deduce the box contains a grid of compartments — that's struct/array recovery.

## Key Concepts
- **Field access patterns**: Consistent accesses at fixed offsets from a base pointer indicate struct fields. `ptr->field_0` is at offset 0, `ptr->field_4` at offset 4.
- **Stride patterns**: Accesses at `base + i * stride` indicate arrays. The stride is the element size.
- **Nested aggregates**: A struct field might itself be a pointer to another struct, or an array element might be a struct.

## Source Files
- `tiny_dec/analysis/types/aggregate_transform.py` — `analyze_program_aggregate_types()` recovers aggregate layouts.

Read how the analysis collects access patterns and infers struct definitions. Pay attention to how stride detection works.

## CLI Demonstration

```bash
# This is the best fixture for structs
tiny-dec decompile tests/fixtures/bin/fixture_struct_O0_nopie.elf --stage aggregate_types --func parse_record
```

Look for struct type definitions. The original C has `Record` with `id` and `value` fields. Compare the recovered layout with the source in `tests/fixtures/src/fixture_struct.c`.

## Quiz

**Q1:** The code accesses memory at `x10 + 0`, `x10 + 4`, `x10 + 8`, and `x10 + 12`, always in pairs of (offset, offset+4). What aggregate type does this suggest?

<details>
<summary>Answer</summary>
An array of 2-element structs: each struct is 8 bytes with two 4-byte fields. The pairs (0,4) and (8,12) access elements at index 0 and 1 respectively, with stride 8. The decompiler would recover something like `struct { int32_t field_0; int32_t field_4; }[]`.
</details>

**Q2:** Why is aggregate type recovery done after scalar types (stage 11) and not before?

<details>
<summary>Answer</summary>
Aggregate recovery needs to know which values are pointers (from scalar types) to identify base addresses for struct/array accesses. It also needs to know field sizes (from scalar type widths) to compute struct layouts correctly. Without scalar types, the analysis can't distinguish pointer arithmetic (struct access) from regular integer arithmetic.
</details>

## Dynamic Exercise

Compare the aggregate analysis at different optimization levels:
```bash
tiny-dec decompile tests/fixtures/bin/fixture_struct_O0_nopie.elf --stage aggregate_types --func parse_record
tiny-dec decompile tests/fixtures/bin/fixture_struct_O2_nopie.elf --stage aggregate_types --func parse_record
```
"Does the optimizer change the struct access pattern? Does -O2 still produce the same struct layout, or does register allocation make it harder to recover?"

## Advanced Exercise (Modification)

```bash
git checkout -b learn/stage-12-aggregates
```
Open `tiny_dec/analysis/types/aggregate_transform.py`. Find where stride patterns are detected. What's the minimum number of array accesses needed to infer a stride? Try changing this threshold and see how it affects struct recovery on `fixture_struct_O0_nopie.elf`.

When done: `git checkout main`

# Stage 11: Scalar Types

## What It Does
This stage infers the **type** of each SSA value: is it a `bool`, a signed `int32_t`, an unsigned `uint32_t`, a `pointer`, or just a raw machine `word`? It does this by looking at how values are used — comparisons, arithmetic, memory access patterns all provide type evidence.

**Analogy:** If someone hands you a mystery box, you figure out what's inside by how people interact with it. If they compare it with `< 0`, it's probably a signed integer. If they use it as a memory address, it's probably a pointer.

## Key Concepts
- **Type evidence**: Each operation constrains its operands' types. `blt` (branch if less than, signed) implies signed operands. A LOAD address operand is a pointer. A conditional branch result is a boolean.
- **Type lattice**: Types are ordered: `word` (most general) → `int`/`uint`/`pointer` → `bool`. The analysis narrows types from `word` toward more specific types as it gathers evidence.
- **Constraint propagation**: Types flow through operations. If `x + y` is used as a pointer, then `x` or `y` is likely a pointer and the other is an offset.

## Source Files
- `tiny_dec/analysis/types/transform.py` — `analyze_program_scalar_types()` runs type inference.

Look at how each p-code operation generates type constraints, and how constraints are solved.

## CLI Demonstration

```bash
# Before type inference
tiny-dec decompile tests/fixtures/bin/fixture_loop_O0_nopie.elf --stage memory --func sum_to_n

# After type inference
tiny-dec decompile tests/fixtures/bin/fixture_loop_O0_nopie.elf --stage scalar_types --func sum_to_n
```

Look for type annotations on SSA values (e.g., `int32_t`, `uint32_t`, `bool`).

## Quiz

**Q1:** The instruction `blt x10, x11, <target>` (branch if less than, signed) tells you what about the types of x10 and x11?

<details>
<summary>Answer</summary>
Both x10 and x11 are signed integers. The "signed less than" comparison only makes sense for signed values — for unsigned values, the compiler would use `bltu` (branch if less than unsigned). This single instruction provides type evidence for two values.
</details>

**Q2:** Why can't the decompiler just assign `int32_t` to everything and call it done?

<details>
<summary>Answer</summary>
Incorrect types produce incorrect decompiled C. If a value is actually a pointer and you call it int32_t, pointer arithmetic and dereferences become nonsensical integer operations. If a value is unsigned and you call it signed, comparisons decompile incorrectly (`<` vs `< unsigned`). Type accuracy directly affects output readability and correctness.
</details>

## Dynamic Exercise

Run scalar types on the switch fixture:
```bash
tiny-dec decompile tests/fixtures/bin/fixture_switch_O0_nopie.elf --stage scalar_types --func dispatch
```
"What types does the analysis assign to the function parameters? Are the switch comparison values signed or unsigned? Check the C source to verify."

## Advanced Exercise (Modification)

```bash
git checkout -b learn/stage-11-types
```
Open `tiny_dec/analysis/types/transform.py`. Find `_add_additive_evidence()` (around line 398) — it generates type constraints from `INT_ADD` operations. Currently, there is no evidence generated from `INT_AND` with a small constant mask (e.g., `x & 0xFF`). Add a new rule: when you see `INT_AND` where one input is a constant like `0xFF`, `0xFFFF`, or `0xFFFFFF`, generate evidence that the other input is **unsigned** (since masking implies treating the value as a bag of bits, not a signed integer). Run on a fixture and check if your evidence appears in the type output.

**Why this matters:** Bitwise masks are a strong signal that a value is unsigned. Real decompilers use this heuristic extensively.

**Test idea:** Construct an `INT_AND` op with a `0xFF` mask and assert that the type inference marks the input as unsigned.

When done: `git checkout main`

# Stage 05: Simplify

## What It Does
The simplifier cleans up the raw IR by applying algebraic rules: constant folding (compute `3 + 4` → `7`), identity elimination (remove `x + 0` → `x`), and temporary forwarding (inline short-lived temporaries). This reduces noise so later stages work on cleaner input.

**Analogy:** This is like proofreading a rough draft — you're not changing the meaning, just removing redundancy and simplifying phrasing so the important structure stands out.

## Key Concepts
- **Constant folding**: Evaluate operations whose inputs are all constants at analysis time. Handles binary ops (INT_ADD, INT_SUB, etc.), comparisons (INT_EQUAL, INT_LESS, etc.), and unary ops (BOOL_NEGATE, INT_ZEXT, INT_SEXT, SUBPIECE).
- **Identity elimination**: Remove operations that don't change their input (`x + 0`, `x - 0`, `x | 0`, `x ^ 0`, `x << 0`, `x >> 0`, `x & 0xFF..FF`). Both operand orders are handled (e.g., `0 + x` too).
- **Temporary forwarding**: If a UNIQUE temporary is defined once and used once (as a COPY source), replace the use with the definition and remove the temporary.
- **Temporary renumbering**: After forwarding eliminates some temporaries, the remaining UNIQUE offsets are renumbered densely in first-appearance order for deterministic output.

## Source Files
- `tiny_dec/analysis/simplify/transform.py` — `canonicalize_program_ir()` applies all simplification rules.

Read through the transform function and find each category of simplification rule. Notice how they're applied iteratively until no more changes occur (fixed-point).

## CLI Demonstration

```bash
# Before simplification
$ poetry run tiny-dec decompile tests/fixtures/bin/fixture_basic_O0_nopie.elf --stage ir --func main

# After simplification
$ poetry run tiny-dec decompile tests/fixtures/bin/fixture_basic_O0_nopie.elf --stage simplify --func main
```

Look for operations that disappeared or were replaced with constants. The IR gets noticeably shorter.

## Quiz

**Q1:** Why is constant folding done in the decompiler rather than relying on the compiler having already done it?

<details>
<summary>Answer</summary>
The lifting process (stages 01-02) introduces new constants that weren't in the original code. For example, stack pointer arithmetic (`sp - 32`) and address calculations produce constant expressions that the compiler never emitted — the decompiler's lifter created them. The decompiler must fold these to recover clean high-level operations.
</details>

**Q2:** What is a "fixed-point" in the context of simplification, and why is it needed?

<details>
<summary>Answer</summary>
A fixed-point is when running the simplification rules again produces no changes. It's needed because one simplification can enable another: folding a constant might create a new identity operation, which when eliminated might enable another forwarding. Running to fixed-point ensures all cascading simplifications are applied.
</details>

## Dynamic Exercise

Compare simplification at -O0 vs -O2:
```bash
$ poetry run tiny-dec decompile tests/fixtures/bin/fixture_loop_O0_nopie.elf --stage simplify --func main
$ poetry run tiny-dec decompile tests/fixtures/bin/fixture_loop_O2_nopie.elf --stage simplify --func main
```
**Predict before running:** -O0 code has many redundant stack operations the compiler didn't bother to optimize. Which version has more simplification opportunities? After running, count the operations — why does -O0 produce so much more redundancy for the simplifier to clean up?

## Advanced Exercise (Modification)

```bash
$ git checkout -b learn/stage-05-simplify
```
Open `tiny_dec/analysis/simplify/transform.py`. Find the `_fold_identity_op()` function (around line 246). It already handles `x + 0`, `x - 0`, `x | 0`, `x ^ 0`, and `x & 0xFF..FF`. But it does NOT handle **self-cancellation**: `x XOR x → 0` or `x SUB x → 0`. Add a rule: when both inputs to `INT_XOR` or `INT_SUB` are the **same varnode**, replace the output with a constant zero. Run on a fixture and check if your rule triggers.

**Why this matters:** Compilers sometimes emit `xor reg, reg` to zero a register. Catching this early simplifies all downstream stages.

**Test idea:** Construct a p-code `INT_XOR` op where both inputs are the same varnode. Assert that the simplifier replaces it with a COPY of constant 0.

When done: `git checkout main`

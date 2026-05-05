# Stage 07: SSA

## What It Does
**Static Single Assignment (SSA)** form gives every definition of a register a unique version number. Instead of `x10` being overwritten multiple times, you get `x10_0`, `x10_1`, `x10_2` — each assigned exactly once. At merge points, **phi nodes** (φ) select which version to use based on which CFG path was taken.

**Analogy:** SSA is like giving every variable a unique name tag so you always know which version you're looking at. Instead of "the variable x" (which could mean different things at different points), you have "x at line 3" and "x at line 7" — unambiguous.

## Key Concepts
- **Single assignment**: Every variable version is defined exactly once. This makes dataflow analysis trivial — you can find the definition of any use by following one pointer.
- **Phi nodes (φ)**: Placed at merge points in the CFG. `x10_3 = φ(x10_1, x10_2)` means "use x10_1 if we came from block A, x10_2 if we came from block B."
- **Dominance frontier**: The algorithm for placing phi nodes. A block's dominance frontier is where its dominance "ends" — exactly where phi nodes are needed.
- **Memory versioning**: Not just registers — tiny-dec also versions memory locations in SSA.

## Source Files
- `tiny_dec/analysis/ssa/transform.py` — `construct_program_ssa()` builds SSA form using dominance frontiers.

This is one of the most important stages. Read `construct_program_ssa()` carefully — trace the phi-node insertion algorithm and the renaming pass.

## CLI Demonstration

```bash
# Before SSA (plain dataflow)
tiny-dec decompile tests/fixtures/bin/fixture_loop_O0_nopie.elf --stage dataflow --func sum_to_n

# After SSA
tiny-dec decompile tests/fixtures/bin/fixture_loop_O0_nopie.elf --stage ssa --func sum_to_n
```

Look for phi nodes at the top of loop header blocks. Each phi has exactly as many inputs as the block has predecessor edges.

## Quiz

**Q1:** What problem does SSA solve that plain variable tracking doesn't?

<details>
<summary>Answer</summary>
Without SSA, a single register name (x10) may hold completely different values at different program points — you can't tell which definition reaches which use without running a separate reaching-definitions analysis every time. SSA makes this explicit: each definition is a unique name, so every use points directly to its definition. This simplifies virtually every subsequent analysis.
</details>

**Q2:** A loop header block has a phi node `total_2 = φ(total_0, total_1)`. What do the two inputs represent?

<details>
<summary>Answer</summary>
`total_0` is the initial value when entering the loop for the first time (from outside the loop). `total_1` is the updated value from the previous loop iteration (from the loop body's back-edge). The phi node selects which one based on whether we're entering the loop or continuing it.
</details>

## Dynamic Exercise

Run SSA on the struct fixture:
```bash
tiny-dec decompile tests/fixtures/bin/fixture_struct_O0_nopie.elf --stage ssa --func parse_record
```
"How many phi nodes does `parse_record` have? Can you match each phi to a C variable in the original source code (`tests/fixtures/src/fixture_struct.c`)? Hint: the loop has an index variable and an accumulator."

## Advanced Exercise (Modification)

```bash
git checkout -b learn/stage-07-ssa
```
Open `tiny_dec/analysis/ssa/transform.py`. Find where phi nodes are inserted. What happens if you skip the dominance frontier calculation and place phi nodes at every merge point? Run it on `fixture_loop_O0_nopie.elf` — does the output change? Are there unnecessary phi nodes now?

When done: `git checkout main`

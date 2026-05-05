# Stage 06: Dataflow

## What It Does
This stage performs **forward intraprocedural constant propagation** — it tracks which registers and memory locations hold known constant values and propagates those values forward through the CFG. When a register is loaded with a constant and used later without being modified, the use is replaced with the constant.

**Analogy:** Imagine reading a recipe where ingredient amounts are defined at the top. Constant propagation is like mentally substituting "2 cups flour" every time you see "flour" later — you're carrying known values forward through the instructions.

## Key Concepts
- **Constant propagation**: If `x10 = 42` and x10 isn't modified before a use, replace the use with 42.
- **Forward analysis**: Facts flow forward along CFG edges — from definition sites toward use sites.
- **Intraprocedural**: Only within a single function. Cross-function propagation comes later (stage 15).
- **Meet operator**: At merge points (where two CFG paths join), if x10 is 42 on one path and 99 on the other, the result is "unknown" — we can't propagate a constant.

## Source Files
- `tiny_dec/analysis/dataflow/transform.py` — `analyze_program_dataflow()` runs the propagation.

Look at how the analysis iterates over blocks in CFG order, maintaining a fact set per block.

## CLI Demonstration

```bash
# Before dataflow
tiny-dec decompile tests/fixtures/bin/fixture_basic_O0_nopie.elf --stage simplify --func main

# After dataflow
tiny-dec decompile tests/fixtures/bin/fixture_basic_O0_nopie.elf --stage dataflow --func main
```

Look for register uses that got replaced with concrete values.

## Quiz

**Q1:** At a CFG merge point (where an if-else rejoins), register x10 holds 5 on the "then" path and 10 on the "else" path. What value does constant propagation assign to x10 after the merge?

<details>
<summary>Answer</summary>
"Top" or "unknown" — the analysis cannot determine which path was taken at runtime, so it conservatively says x10 is not a known constant after the merge. This is the correct conservative choice; guessing wrong would produce incorrect decompiled code.
</details>

**Q2:** Why is this analysis only intraprocedural? What would go wrong with a naive interprocedural version?

<details>
<summary>Answer</summary>
Interprocedural constant propagation requires knowing what values a called function reads and modifies (its "summary"). At this stage, we don't have function summaries yet — that comes in stage 15 (Interproc). Attempting it here would either miss propagation across calls or require analyzing the whole program at once, which is expensive and complicated.
</details>

## Dynamic Exercise

Run dataflow on the calls fixture:
```bash
tiny-dec decompile tests/fixtures/bin/fixture_calls_O0_nopie.elf --stage dataflow --func main
```
**Before looking at the output, predict:** this is an *intraprocedural* analysis — it only looks inside one function. If `main` calls `helper(7)`, will the constant `7` be visible inside `helper`'s analysis? Now check the output — find a CALL operation. Does the analysis propagate constants through it? Why or why not?

## Advanced Exercise (Modification)

```bash
git checkout -b learn/stage-06-dataflow
```
Open `tiny_dec/analysis/dataflow/transform.py`. Find the meet operator logic where two paths join. What happens if you change the meet to always pick the left path's value instead of "unknown"? Run it on `fixture_loop_O0_nopie.elf` — does the output change? Is it still correct?

When done: `git checkout main`

# Stage 13: Variables

## What It Does
This stage groups SSA values and memory slots into **named high-level variables**. Multiple SSA versions of the same logical variable (e.g., `total_0`, `total_1`, `total_2`) get merged into a single variable `local_20_4` (or similar). Stack slots get names too.

**Analogy:** SSA gave every instance a unique ID badge. Now we're grouping people by their real identity — "these five badges all belong to the same person" — and assigning a readable name.

## Key Concepts
- **Variable grouping**: SSA values connected by phi nodes or simple copies are likely the same source-level variable. They get merged into one high-level variable.
- **Stack variable naming**: Stack slots become named locals based on their frame offset and size (e.g., `local_12_4` for a 4-byte variable at offset -12).
- **Register variables**: Some variables live entirely in registers and never touch the stack (especially at -O2). These still get names.

## Source Files
- `tiny_dec/analysis/highvars/transform.py` — `analyze_program_variables()` groups SSA values into variables.

Read how phi-connected components are identified and merged.

## CLI Demonstration

```bash
# Before variable recovery (SSA versions everywhere)
tiny-dec decompile tests/fixtures/bin/fixture_loop_O0_nopie.elf --stage aggregate_types --func sum_to_n

# After variable recovery
tiny-dec decompile tests/fixtures/bin/fixture_loop_O0_nopie.elf --stage variables --func sum_to_n
```

Notice how SSA subscripts disappear and meaningful variable names appear.

## Quiz

**Q1:** SSA values `x10_0`, `x10_1`, and `x10_2` are connected through phi nodes in a loop. Why should the decompiler merge them into one variable?

<details>
<summary>Answer</summary>
In the original C code, they were all the same variable (like `total`). SSA split it into three versions for analysis precision, but the programmer wrote and thinks about one variable. Merging them back recovers the original intent and produces readable output: `total = total + x` instead of `total_2 = total_1 + x`.
</details>

**Q2:** When should two SSA values NOT be merged even if they're in the same register?

<details>
<summary>Answer</summary>
When the register is reused for an unrelated purpose. For example, x10 might hold function argument `n` at entry, then later get reused for the loop counter `i`. These are different source-level variables that happen to share a register due to register allocation. The analysis must distinguish genuine phi-connected components (same variable) from register reuse (different variables).
</details>

## Dynamic Exercise

Run variables on the struct fixture:
```bash
tiny-dec decompile tests/fixtures/bin/fixture_struct_O0_nopie.elf --stage variables --func parse_record
```
"Match each recovered variable name to the original C source. Can you identify which variable is `total`, which is `i`, and which is the `records` pointer?"

## Advanced Exercise (Modification)

```bash
git checkout -b learn/stage-13-variables
```
Open `tiny_dec/analysis/highvars/transform.py`. Find `_recover_aggregate_variable()` (line 242) — this is step 1 of variable recovery, which groups SSA values that access the same aggregate (struct) layout into a single variable. What happens if you skip this step entirely (make it return `None` always)? Run on `fixture_struct_O0_nopie.elf --stage variables --func parse_record` — do struct fields appear as individual unrelated variables instead of being grouped under one struct? Compare the output with and without your change.

**Why this matters:** Variable recovery decides how readable the final C output is. Grouping struct accesses under one variable is what lets the output say `arg->field_0` instead of scattered memory loads.

**Test idea:** Write a test that runs the variables stage on `fixture_struct_O0_nopie.elf` and asserts that at least one variable has an aggregate type.

When done: `git checkout main`

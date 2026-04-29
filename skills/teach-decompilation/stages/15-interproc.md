# Stage 15: Interproc

## What It Does
This stage performs **interprocedural analysis** — it looks across function boundaries to infer function prototypes (parameter types and count, return type) and build summaries of each function's effects. This information feeds back into the callers to improve their analysis.

**Analogy:** Stages 05-14 analyzed each room of a building independently. Now we're walking the hallways (function calls) to figure out what goes in and out of each room — the inputs (parameters) and outputs (return values) of each function.

## Key Concepts
- **Prototype inference**: Determine how many parameters a function takes, their types, and the return type — all from the binary without debug info.
- **Function summaries**: A compact description of what a function does to its inputs. Used by callers to understand the effect of calling it without re-analyzing the callee.
- **Fixed-point iteration**: Functions may call each other (or themselves recursively). The analysis iterates until prototypes stabilize.

## Source Files
- `tiny_dec/analysis/interproc/transform.py` — `analyze_program_interproc()` builds prototypes and summaries.

Read how prototypes are inferred from call sites and how information propagates across the call graph.

## CLI Demonstration

```bash
# Interprocedural analysis on a multi-function program
tiny-dec decompile tests/fixtures/bin/fixture_basic_O0_nopie.elf --stage interproc --func main

# Also check the callee
tiny-dec decompile tests/fixtures/bin/fixture_basic_O0_nopie.elf --stage interproc --func helper
```

Look at the inferred prototype for `helper`. Compare with the C source: does it get the right number and type of parameters?

## Quiz

**Q1:** How does the decompiler figure out that a function takes exactly 2 arguments without debug information?

<details>
<summary>Answer</summary>
By analyzing all call sites: if every caller puts values in a0 and a1 before calling the function, and the function reads a0 and a1 but never a2, the evidence points to 2 parameters. The callee's body confirms this — it uses a0 and a1 as inputs. Cross-referencing call-site evidence with callee body analysis produces the prototype.
</details>

**Q2:** Why is interprocedural analysis done last in the analysis phase, after all the intraprocedural passes?

<details>
<summary>Answer</summary>
Interprocedural analysis builds on the results of every previous stage. It needs: SSA (to track values), types (to infer parameter types), stack analysis (to find stack-passed arguments), memory partitioning (to understand pointer parameters), and call site information (from stage 08). Running it last means it has the richest information available to make accurate prototype inferences.
</details>

## Dynamic Exercise

Run interproc on the chain fixture (multiple levels of function calls):
```bash
tiny-dec decompile tests/fixtures/bin/fixture_chain_O0_nopie.elf --stage interproc --func main
```
**Before looking at the output, predict:** `fixture_chain.c` has a chain `main → bump → mix → fold`. Each takes one `int` argument. Will the analysis infer all prototypes correctly? Now check the output — trace the call chain. Does each function's inferred prototype match the C source? Is there a function where the prototype is surprising?

## Advanced Exercise (Modification)

```bash
git checkout -b learn/stage-15-interproc
```
Open `tiny_dec/analysis/interproc/transform.py`. Find the prototype inference logic. What happens if you force all functions to have 0 arguments? Run the full pipeline to `c` stage on `fixture_basic_O0_nopie.elf` — how does the C output change?

When done: `git checkout main`

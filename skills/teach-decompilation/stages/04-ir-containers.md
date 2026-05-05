# Stage 04: IR Containers

## What It Does
This stage wraps the raw disassembly output into typed, durable containers — `FunctionIR` and `ProgramIR`. These containers bundle together the CFG, p-code blocks, metadata, and entry points into a single object that all subsequent analysis stages operate on.

**Analogy:** Stages 00-03 gathered ingredients. This stage puts them in labeled containers in the fridge — now every recipe (analysis pass) can grab exactly what it needs without re-reading the binary.

## Key Concepts
- **FunctionIR**: Contains one function's CFG, blocks, p-code operations, and metadata (name, address, parameters).
- **ProgramIR**: Contains all functions' FunctionIRs plus program-level metadata (architecture, globals, symbols).
- **Immutability principle**: Once built, the container structure doesn't change — analysis stages annotate and transform the contents.

## Source Files
- `tiny_dec/ir/containers.py` — `build_function_ir()` and `build_program_ir()` constructors.
- `tiny_dec/ir/function_ir.py` — `FunctionIR` dataclass.
- `tiny_dec/ir/program_ir.py` — `ProgramIR` dataclass.

Skim `containers.py` to see how disassembly results get packaged. Then look at `FunctionIR` fields to understand what's available to later stages.

## CLI Demonstration

```bash
# See the full IR container output
tiny-dec decompile tests/fixtures/bin/fixture_basic_O0_nopie.elf --stage ir --func main
```

Compare with the disasm output — the content is the same, but now it's in a structured form with clear function boundaries and metadata.

## Quiz

**Q1:** Why does the pipeline need explicit container objects instead of just passing the CFG directly between stages?

<details>
<summary>Answer</summary>
Containers provide a stable interface: every analysis stage knows exactly what fields are available (blocks, edges, metadata, annotations) without coupling to how earlier stages produced them. They also carry accumulated results — when stage 7 adds SSA information, it's attached to the same FunctionIR that stage 5's simplification already modified.
</details>

**Q2:** If you wanted to add a new analysis pass that computes the cyclomatic complexity of a function, which fields of `FunctionIR` would you need to read?

<details>
<summary>Answer</summary>
You'd need the CFG edges (to count edges), the basic blocks (to count nodes), and the connected components. Cyclomatic complexity = edges - nodes + 2. The `FunctionIR` dataclass stores the block map and edge lists, giving you everything needed. This is exactly the kind of derived metric that a well-designed container makes easy to compute.
</details>

## Dynamic Exercise

This stage is your **first real look at how the codebase is organized** as a software project. Open `tiny_dec/ir/function_ir.py` and study the `FunctionIR` dataclass. Then run:
```bash
tiny-dec decompile tests/fixtures/bin/fixture_calls_O0_nopie.elf --stage ir --func main
```
**After reading the dataclass, predict:** which field stores the basic blocks? Which stores the edges? Now look at the output — can you map each section back to its `FunctionIR` field? This is the structure that every analysis stage from here on will read and write to.

## Advanced Exercise (Modification)

```bash
git checkout -b learn/stage-04-ir
```
Open `tiny_dec/ir/function_ir.py`. Add a new field `instruction_count: int = 0` to the `FunctionIR` dataclass (use a default value so existing call sites don't break). Then open `containers.py` and populate it in `build_function_ir()` by counting p-code operations across all blocks. Finally, open `pretty_containers.py` and add a line to print the count in the text output. Run `tiny-dec decompile tests/fixtures/bin/fixture_basic_O0_nopie.elf --stage ir --func main` and verify your count appears.

**Test idea:** Write a test that builds a `FunctionIR` from a fixture and asserts `instruction_count > 0`.

When done: `git checkout main`

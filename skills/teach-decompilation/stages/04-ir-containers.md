# Stage 04: IR Containers

## What It Does
This stage wraps the raw disassembly output into typed containers — `FunctionIR` and `ProgramIR`. These containers bundle together the CFG, p-code blocks, metadata, call graph, and entry points into a single object that subsequent analysis stages read from.

**Analogy:** Stages 00-03 gathered ingredients. This stage puts them in labeled containers in the fridge — now every recipe (analysis pass) can grab exactly what it needs without re-reading the binary.

## Key Concepts
- **FunctionIR**: Contains one function's disassembly (`DisasmFunction`), an instruction index, callsite list, return blocks, and direct callees.
- **ProgramIR**: Contains all discovered `FunctionIR` objects plus program-level metadata: call graph edges, external functions, and discovery order.
- **Snapshot architecture**: Each pipeline stage creates a NEW container type with additional information — Stage 5 creates `CanonicalProgramIR`, Stage 7 creates `SSAProgramIR`, etc. The original `ProgramIR` from this stage is not modified by later stages; it serves as the base snapshot.
- **Call graph construction**: `build_program_ir()` uses a worklist to discover all functions reachable from `main`, classifying calls as INTERNAL, EXTERNAL, or UNRESOLVED.

## Source Files
- `tiny_dec/ir/containers.py` — `build_function_ir()` and `build_program_ir()` constructors.
- `tiny_dec/ir/function_ir.py` — `FunctionIR` dataclass with fields: `entry`, `name`, `disasm`, `instruction_index`, `callsites`, `return_blocks`, `direct_callees`.
- `tiny_dec/ir/program_ir.py` — `ProgramIR` dataclass with fields: `root_entry`, `functions`, `discovery_order`, `externals`, `call_graph`, `pending_entries`, `invalidated_entries`.

Skim `containers.py` to see how disassembly results get packaged. Then look at `FunctionIR` fields to understand what's available to later stages.

## CLI Demonstration

```bash
# See the full IR container output
$ poetry run tiny-dec decompile tests/fixtures/bin/fixture_basic_O0_nopie.elf --stage ir --func main
```

Compare with the disasm output — the IR stage adds callsite analysis, call graph edges, and function-level metadata on top of the CFG structure.

## Quiz

**Q1:** Why does the pipeline need explicit container objects instead of just passing the CFG directly between stages?

<details>
<summary>Answer</summary>
Containers provide a stable, typed interface: every analysis stage knows exactly what fields are available (blocks, callsites, return blocks, call graph) without coupling to how earlier stages produced them. They also enable interprocedural analysis — ProgramIR holds all functions together with their call relationships, which a bare CFG cannot express.
</details>

**Q2:** If you wanted to add a new analysis pass that computes the cyclomatic complexity of a function, which fields of `FunctionIR` would you need to read?

<details>
<summary>Answer</summary>
You'd need the CFG edges (to count edges E) and the basic blocks (to count nodes N). Cyclomatic complexity = E - N + 2. Access the blocks via `func_ir.disasm.blocks` (a dict of address → BasicBlock), and count edges by summing `len(block.successors)` across all blocks. The `FunctionIR` wraps the `DisasmFunction` which stores both.
</details>

## Dynamic Exercise

This stage is your **first real look at how the codebase is organized** as a software project. Open `tiny_dec/ir/function_ir.py` and study the `FunctionIR` dataclass. Then run:
```bash
$ poetry run tiny-dec decompile tests/fixtures/bin/fixture_calls_O0_nopie.elf --stage ir --func main
```
**After reading the dataclass, predict:** which field stores the basic blocks? Which stores the call targets? Now look at the output — can you map each section back to its `FunctionIR` field? Notice how callsites are classified as direct vs. indirect.

## Advanced Exercise (Modification)

```bash
$ git checkout -b learn/stage-04-ir
```
Open `tiny_dec/ir/function_ir.py`. Add a new field `instruction_count: int = 0` to the `FunctionIR` dataclass (use a default value so existing call sites don't break). Then open `containers.py` and populate it in `build_function_ir()` by counting p-code operations across all blocks. Finally, open `pretty_containers.py` and add a line to print the count in the text output. Run `tiny-dec decompile tests/fixtures/bin/fixture_basic_O0_nopie.elf --stage ir --func main` and verify your count appears.

**Test idea:** Write a test that builds a `FunctionIR` from a fixture and asserts `instruction_count > 0`.

When done: `git checkout main`

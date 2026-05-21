# Stage 03: Disassembly

## What It Does
The disassembler takes the flat sequence of p-code operations and organizes them into **basic blocks** connected by a **control flow graph (CFG)**. A basic block is a straight-line sequence of operations with one entry and one exit. The CFG shows how blocks connect via branches and jumps.

**Analogy:** If p-code is a long scroll of text, disassembly is cutting it into paragraphs (basic blocks) and drawing arrows between them (control flow). The arrows show all possible paths through the function.

## Key Concepts
- **Basic block**: A maximal sequence of instructions with no branches in the middle. Execution enters at the top and leaves at the bottom. Each block has a **terminator** type that describes how it ends:
  - `LINEAR` — falls through to the next block (no branch)
  - `BRANCH` — conditional branch (two successors: taken and fallthrough)
  - `JUMP` — unconditional jump (one successor)
  - `INDIRECT_JUMP` — jump to a computed address (target unknown statically)
  - `RETURN` — function exit
  - `STOP` — unreachable endpoint
- **Control flow graph**: A directed graph where nodes are basic blocks and edges are branches/jumps. Every `if`, `while`, and `switch` in the original C creates branching in the CFG. Three edge types exist:
  - `FALLTHROUGH` — control reaches this block when a conditional branch is NOT taken
  - `BRANCH_TAKEN` — control reaches this block when a conditional branch IS taken
  - `JUMP` — control always reaches this block (unconditional)
- **Recursive traversal vs. linear sweep**: A linear sweep decodes instructions sequentially from the start, never following branch targets — it misses code that's only reachable via jumps. Recursive traversal starts from the function entry and follows every branch target, discovering all reachable blocks even if they appear out-of-order in memory.

## Source Files
- `tiny_dec/disasm/builder.py` — `disassemble_function()` builds the CFG via recursive traversal using a worklist.
- `tiny_dec/disasm/models.py` — `BasicBlock`, `BlockEdge`, `BlockEdgeKind`, `BlockTerminator`, `DisasmFunction` data models.

Focus on `disassemble_function()` — trace how it discovers blocks by following branches. Notice that it uses a worklist (depth-first) and records discovery order for deterministic output.

## CLI Demonstration

```bash
# See the CFG for a loop
$ poetry run tiny-dec decompile tests/fixtures/bin/fixture_loop_O0_nopie.elf --stage disasm --func sum_to_n
```

You'll see basic blocks labeled with addresses, each containing p-code operations, with edges showing where control flows. Look for `term=branch` blocks (conditional) and notice the back-edge (an edge pointing to an earlier block — that's the loop).

```bash
# Compare: a function with no branches (single block, term=return)
$ poetry run tiny-dec decompile tests/fixtures/bin/fixture_basic_O0_nopie.elf --stage disasm --func helper
```

## Quiz

**Q1:** A function has an `if-else` statement. How many basic blocks does this create at minimum, and what are the edges between them?

<details>
<summary>Answer</summary>
At minimum 4 blocks: (1) the condition check (term=branch), (2) the "then" body, (3) the "else" body, (4) the merge point after both branches. The condition block has two outgoing edges — BRANCH_TAKEN to "then" and FALLTHROUGH to "else". Both "then" and "else" have JUMP edges to the merge block.
</details>

**Q2:** What is a "back-edge" in a CFG, and what does it tell the decompiler?

<details>
<summary>Answer</summary>
A back-edge is an edge whose target appears earlier in discovery order than its source — it points "backward" in the graph. Back-edges indicate loops: the source block is the loop body's last block jumping back to the loop header. The structuring stage (stage 16) uses back-edges to recover `while`/`for` loops from the CFG.
</details>

## Dynamic Exercise

Compare the CFG for the switch fixture:
```bash
$ poetry run tiny-dec decompile tests/fixtures/bin/fixture_switch_O0_nopie.elf --stage disasm --func dispatch
```
Count the basic blocks. How many outgoing edges does the first block have? Look at the edge types — are they BRANCH_TAKEN/FALLTHROUGH pairs (nested if-else pattern) or something else?

**Predict before running:** A switch with 4 cases compiled at -O0 typically becomes a chain of if-else comparisons. How many `term=branch` blocks would you expect?

## Advanced Exercise (Modification)

```bash
$ git checkout -b learn/stage-03-disasm
```
Open `tiny_dec/disasm/builder.py`. Find where the disassembler handles branch instructions to discover new blocks. What happens if you skip the fallthrough edge (the FALLTHROUGH path when the branch is NOT taken)? Re-run on `fixture_loop_O0_nopie.elf` and see how the CFG changes — which blocks disappear?

When done: `git checkout main`

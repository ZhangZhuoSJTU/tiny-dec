# Stage 03: Disassembly

## What It Does
The disassembler takes the flat sequence of p-code operations and organizes them into **basic blocks** connected by a **control flow graph (CFG)**. A basic block is a straight-line sequence of operations with one entry and one exit. The CFG shows how blocks connect via branches and jumps.

**Analogy:** If p-code is a long scroll of text, disassembly is cutting it into paragraphs (basic blocks) and drawing arrows between them (control flow). The arrows show all possible paths through the function.

## Key Concepts
- **Basic block**: A maximal sequence of instructions with no branches in the middle. Execution enters at the top and leaves at the bottom.
- **Control flow graph**: A directed graph where nodes are basic blocks and edges are branches/jumps. Every `if`, `while`, and `switch` in the original C creates branching in the CFG.
- **Recursive traversal**: Starting from the function entry, the disassembler follows all branch targets to discover blocks. It's "recursive" because each discovered branch may reveal new blocks.

## Source Files
- `tiny_dec/disasm/builder.py` — `disassemble_function()` builds the CFG via recursive traversal.
- `tiny_dec/disasm/` — Block splitting logic, edge classification.

Focus on `disassemble_function()` — trace how it discovers blocks by following branches.

## CLI Demonstration

```bash
# See the CFG for a loop
tiny-dec decompile tests/fixtures/bin/fixture_loop_O0_nopie.elf --stage disasm --func sum_to_n
```

You'll see basic blocks labeled with addresses, each containing p-code operations, with edges showing where control flows. The loop creates a back-edge (an edge pointing to an earlier block).

```bash
# Compare: a function with no branches
tiny-dec decompile tests/fixtures/bin/fixture_basic_O0_nopie.elf --stage disasm --func helper
```

## Quiz

**Q1:** A function has an `if-else` statement. How many basic blocks does this create at minimum, and what are the edges between them?

<details>
<summary>Answer</summary>
At minimum 4 blocks: (1) the condition check, (2) the "then" branch, (3) the "else" branch, (4) the merge point after both branches. The condition block has two outgoing edges — one to "then", one to "else". Both "then" and "else" have edges to the merge block.
</details>

**Q2:** What is a "back-edge" in a CFG, and what does it tell the decompiler?

<details>
<summary>Answer</summary>
A back-edge points from a block to an earlier block (one that dominates it). Back-edges indicate loops — a block that jumps back to a previously visited block is the bottom of a loop body jumping back to the loop header. The structuring stage (stage 16) uses back-edges to recover while/for loops.
</details>

## Dynamic Exercise

Compare the CFG for the switch fixture:
```bash
tiny-dec decompile tests/fixtures/bin/fixture_switch_O0_nopie.elf --stage disasm --func dispatch
```
"Count the basic blocks. How many outgoing edges does the first block have? Why does a switch statement produce a different CFG shape than nested if-else?"

## Advanced Exercise (Modification)

```bash
git checkout -b learn/stage-03-disasm
```
Open `tiny_dec/disasm/builder.py`. Find where the disassembler handles branch instructions to discover new blocks. What happens if you skip the fallthrough edge (the path when the branch is NOT taken)? Re-run on `fixture_loop_O0_nopie.elf` and see how the CFG changes.

When done: `git checkout main`

export interface WalkthroughStep {
  type: "popup" | "callout";
  title?: string;
  text: string;
  target?: {
    kind: "block" | "instruction" | "element" | "text-line";
    address?: string;
    lineIndex?: number;
    selector?: string;
    side?: "left" | "right";
    yOffset?: number;
    /** For kind="block": highlight a specific IR line within the block (substring match) */
    highlightLine?: string;
    /** Which function to show in the CFG panel for this callout */
    fn?: "main" | "parse_record";
  };
  color?: string;
}

export interface StageWalkthrough {
  description: string;
  steps: WalkthroughStep[];
}

const WALKTHROUGHS: Record<string, StageWalkthrough> = {
  raw: {
    description: "The entire compiled ELF binary, including headers, code, debug info, and metadata.",
    steps: [
      {
        type: "popup",
        title: "Raw Bytes",
        text: `Every program your computer runs is ultimately just a file full of bytes. What you see here is a **hex dump** of a 2,848-byte ELF binary compiled for the RISC-V architecture.

Most of these bytes are not code. The file contains headers that describe how to load the program, debug information the compiler embedded, a symbol table with function names, and section metadata. The actual executable instructions are only **232 bytes** hidden in the middle.

Our decompiler's job is to take these bytes and reconstruct the original C source code. By the end of this pipeline, that's exactly what we'll have.`,
      },
      {
        type: "callout",
        text: "The file starts with **\`7f 45 4c 46\`**, the ELF magic number. Every Linux executable begins with these four bytes so the OS knows how to load it.",
        target: { kind: "element", selector: ".code-surface", side: "right" },
        color: "var(--phase-fe)",
      },
      {
        type: "callout",
        text: "The highlighted **\`.text\` section** (offsets \`0xe4\`-\`0x1cb\`) contains all the executable machine code. Just 232 bytes of instructions in a 2,848-byte file. Everything else is headers, debug info, and metadata.",
        target: { kind: "element", selector: "[data-section='text']", side: "right" },
        color: "var(--accent)",
      },
    ],
  },

  loader: {
    description: "Reads the ELF binary header and identifies architecture, entry point, and code sections.",
    steps: [
      {
        type: "popup",
        title: "Binary Loader",
        text: `Before analyzing any code, the decompiler needs to understand the file format. It reads the **ELF header** (Executable and Linkable Format), the standard format for Linux executables.

The header tells us three critical things: what processor architecture the code was compiled for, where execution starts (the entry point), and how the binary is divided into sections. Think of it like reading the table of contents before diving into a book.

The loader also searches the **symbol table** for function names. That's how we know \`main\` lives at address \`0x110e4\` without having to guess.

**Note:** In tiny-dec, the loader is intentionally kept simple since binary loading is not our focus. Production decompilers like Ghidra and IDA spend much more effort here, handling dozens of binary formats, relocations, and dynamic linking.`,
      },
      {
        type: "callout",
        text: "This is a **32-bit RISC-V** binary with little-endian byte order. The architecture determines how we decode each instruction later.",
        target: { kind: "element", selector: "[data-kv='arch']", side: "right" },
        color: "var(--phase-fe)",
      },
      {
        type: "callout",
        text: "The **entry point** \`0x110e4\` is the address of \`main()\`. The loader found this by looking up \"main\" in the ELF symbol table, which maps names to addresses.",
        target: { kind: "element", selector: "[data-kv='entrypoint']", side: "right" },
        color: "var(--accent)",
      },
      {
        type: "callout",
        text: "The **\`.text\` section** holds all executable code: 232 bytes (\`0xe8\` in hex). This is the portion of the binary we'll decode into instructions.",
        target: { kind: "element", selector: "[data-kv='.text']", side: "right" },
        color: "var(--phase-an)",
      },
      {
        type: "callout",
        text: "The **\`.rodata\` section** stores read-only data (constants, string literals). Our program has 16 bytes of read-only data at \`0x100d4\`.",
        target: { kind: "element", selector: "[data-kv='.rodata']", side: "right" },
        color: "var(--phase-be)",
      },
    ],
  },

  decode: {
    description: "Decodes each 4-byte machine word into RISC-V assembly instructions with operands.",
    steps: [
      {
        type: "popup",
        title: "Instruction Decoding",
        text: `Now we turn raw bytes into human-readable assembly. Each RISC-V instruction is exactly **4 bytes** (32 bits). The decoder reads those bits, identifies the instruction type, and extracts the operands: which registers to use and what immediate values are involved.

RISC-V has a clean, regular encoding. The bottom 7 bits identify the instruction format, making decoding straightforward compared to variable-length architectures like x86.

After this step we can see the program's logic for the first time: stack setup, variable storage, arithmetic, branches, and function calls.`,
      },
      {
        type: "callout",
        text: "\`addi\` means **add immediate**. This subtracts 32 from the stack pointer (\`x2\`), creating a 32-byte **stack frame** where the function stores its local variables and saved registers.",
        target: { kind: "instruction", address: "0x000110e4", side: "right" },
        color: "var(--phase-fe)",
      },
      {
        type: "callout",
        text: "\`sw\` means **store word**. This saves the return address (\`x1\`) onto the stack at offset +28. When the function finishes, it'll load this value back to know where to return.",
        target: { kind: "instruction", address: "0x000110e8", side: "right" },
        color: "var(--phase-fe)",
      },
      {
        type: "callout",
        text: "\`addi x10, x0, 20\` loads the constant 20 into register \`x10\`. In RISC-V, \`x0\` is hardwired to zero, so \"add 0 + 20\" is the standard way to load a constant.",
        target: { kind: "instruction", address: "0x000110f4", side: "right" },
        color: "var(--accent)",
      },
      {
        type: "callout",
        text: "\`jal\` means **jump and link**: a function call. It saves the return address in \`x1\` and jumps to \`parse_record\` at \`0x1112c\`. The call passes arguments via registers.",
        target: { kind: "instruction", address: "0x00011118", side: "right" },
        color: "var(--syn-keyword)",
      },
      {
        type: "callout",
        text: "\`jalr\` with \`x0\` as destination is a **return**. It jumps to the address stored in \`x1\` (the saved return address) without saving a link. This ends the function.",
        target: { kind: "instruction", address: "0x00011128", side: "right" },
        color: "var(--phase-be)",
      },
      {
        type: "callout",
        text: "Here's where \`parse_record\` starts. Same prologue pattern: allocate 32-byte stack frame, save return address and frame pointer. This is a compiler convention.",
        target: { kind: "instruction", address: "0x0001112c", side: "right" },
        color: "var(--phase-fe)",
      },
      {
        type: "callout",
        text: "\`bge\` means **branch if greater or equal**. This is the loop condition: if \`x10 >= x11\` (counter >= limit), jump to the exit. Otherwise, fall through to the loop body.",
        target: { kind: "instruction", address: "0x0001115c", side: "right" },
        color: "var(--accent)",
      },
      {
        type: "callout",
        text: "\`slli x11, x11, 3\` shifts left by 3 bits, which multiplies by 8. This computes the byte offset for array indexing: each element is 8 bytes (the size of a struct with two int fields).",
        target: { kind: "instruction", address: "0x0001116c", side: "right" },
        color: "var(--phase-an)",
      },
    ],
  },

  pcode: {
    description: "Lifts each assembly instruction into architecture-neutral p-code micro-operations.",
    steps: [
      {
        type: "popup",
        title: "P-Code Lifting",
        text: `Assembly instructions can pack multiple operations into one. P-code breaks each instruction into tiny, atomic operations that each do **exactly one thing**: \`INT_ADD\`, \`STORE\`, \`LOAD\`, \`COPY\`, \`BRANCH\`, etc.

P-code is Ghidra's intermediate representation (IR). Many decompilers use a similar concept: angr uses **VEX IR** from Valgrind, Binary Ninja has **BNIL**, and IDA Pro has its own microcode. The idea is the same: translate architecture-specific instructions into a universal language so the rest of the analysis pipeline works on any CPU.

After this step, the rest of our pipeline doesn't need to know about RISC-V specifically. The same analysis would work for x86, ARM, or MIPS code lifted to the same p-code.`,
      },
      {
        type: "callout",
        text: "One \`addi\` becomes one \`INT_ADD\` p-code op. \`register[0x2:4]\` means \"the 4-byte register at slot 2\" (the stack pointer). P-code uses explicit sizes for everything.",
        target: { kind: "instruction", address: "0x000110e4", side: "right" },
        color: "var(--phase-fe)",
      },
      {
        type: "callout",
        text: "A store-word (\`sw\`) becomes **two ops**: \`INT_ADD\` to compute the target address (base + offset), then \`STORE\` to write the value. The address calculation is now explicit.",
        target: { kind: "instruction", address: "0x000110e8", side: "right" },
        color: "var(--accent)",
      },
      {
        type: "callout",
        text: "\`jal\` (function call) becomes \`COPY\` (save return address to register) then \`CALL\` (jump to target). Each semantic action is its own operation.",
        target: { kind: "instruction", address: "0x00011118", side: "right" },
        color: "var(--syn-keyword)",
      },
      {
        type: "callout",
        text: "A branch (\`bge\`) becomes three ops: \`INT_SLESS\` (signed comparison), \`BOOL_NEGATE\` (invert the result since bge is \"not less than\"), and \`CBRANCH\` (conditional branch).",
        target: { kind: "instruction", address: "0x0001115c", side: "right" },
        color: "var(--phase-an)",
      },
      {
        type: "callout",
        text: "A return (\`jalr x0\`) becomes: \`COPY\` the return address, \`INT_AND\` to mask the low bit (RISC-V alignment convention), and \`RETURN\`. Three distinct semantic operations.",
        target: { kind: "instruction", address: "0x00011128", side: "right" },
        color: "var(--phase-be)",
      },
    ],
  },

  disasm: {
    description: "Partitions instructions into basic blocks and builds the Control Flow Graph.",
    steps: [
      {
        type: "popup",
        title: "Disassembly & CFG Construction",
        text: `Now something fundamental happens: we transform the flat instruction list into a **Control Flow Graph** (CFG).

A **basic block** is a maximal sequence of instructions with no branches in the middle: execution enters at the top and exits at the bottom. Branches and branch targets create block boundaries.

The edges between blocks show how execution flows. A conditional branch creates two edges (taken/not-taken). An unconditional jump creates one. A back edge (pointing to an earlier block) means there's a loop.

The CFG is the backbone of all subsequent analysis. It tells us every possible execution path through the code.`,
      },
      {
        type: "callout",
        text: "**Entry block** of \`parse_record\`: the function prologue. It saves registers, copies arguments to the stack, and initializes the accumulator (\`sum = 0\`) and loop counter (\`i = 0\`). Think of it as the setup code before a \`for\` loop.",
        target: { kind: "block", address: "0x1112c", side: "right" },
        color: "var(--phase-fe)",
      },
      {
        type: "callout",
        text: "**Loop header**: the decision point. It loads \`i\` and \`count\`, then does a signed comparison (\`bge\`). Two outgoing edges: one into the loop body (condition true), one to the exit (condition false). Loops typically have a header like this.",
        target: { kind: "block", address: "0x11154", side: "right", highlightLine: "bge" },
        color: "var(--accent)",
      },
      {
        type: "callout",
        text: "**Loop body**: the core computation. It computes \`base + i * 8\` to find the struct address, loads two 4-byte fields (\`field_0\` and \`field_4\`), and adds both to the accumulator. This is where the actual work happens.",
        target: { kind: "block", address: "0x11164", side: "right", highlightLine: "slli" },
        color: "var(--phase-an)",
      },
      {
        type: "callout",
        text: "**Loop latch**: increments \`i\` by 1 and jumps **back** to the header. This back edge (from a later block to an earlier one) is how the decompiler knows there's a loop. Without it, this would just be straight-line code.",
        target: { kind: "block", address: "0x111a8", side: "right", highlightLine: "addi" },
        color: "var(--phase-be)",
      },
      {
        type: "callout",
        text: "**Loop exit**: reached when \`i >= count\`. It loads the accumulated sum into \`x10\` (the return register), restores saved registers, and returns. In C, this is everything after the closing brace of the \`while\` loop.",
        target: { kind: "block", address: "0x111b8", side: "right", highlightLine: "RETURN" },
        color: "var(--phase-be)",
      },
      {
        type: "callout",
        text: "Notice the overall CFG shape: one entry, a diamond-shaped loop (header → body → latch → header), and one exit. This is a **natural loop**, the most common loop pattern in compiled code. The decompiler will later recover this as a \`while\` statement.",
        target: { kind: "block", address: "0x11154", side: "left" },
        color: "var(--accent)",
      },
    ],
  },

  ir: {
    description: "Wraps functions in IR containers with metadata and call-graph edges.",
    steps: [
      {
        type: "popup",
        title: "IR Containers",
        text: `The decompiler now organizes the CFGs into **function-level IR containers**. Each function gets metadata: stack frame size, whether the stack pointer changes dynamically, and a list of callees.

More importantly, we build the **call graph**: which functions call which. By scanning for \`CALL\` instructions, we discover that \`main\` at \`0x11118\` calls \`parse_record\` at \`0x1112c\`.

The call graph enables **interprocedural analysis** later. Understanding how data flows between functions (arguments passed, values returned) requires knowing who calls whom.`,
      },
      {
        type: "callout",
        text: "\`parse_record\` is a **leaf function**: it contains no \`CALL\` instructions. **Why does this matter?** Leaf functions typically don't modify global state through callees, making them simpler to analyze. The decompiler can analyze them first, then use the results when analyzing their callers.",
        target: { kind: "block", address: "0x1112c", side: "right" },
        color: "var(--phase-fe)",
      },
      {
        type: "callout",
        text: "The IR container also records the **stack frame size** (32 bytes) and whether the frame pointer changes dynamically. This metadata feeds directly into stack analysis later.",
        target: { kind: "block", address: "0x11154", side: "right" },
        color: "var(--phase-an)",
      },
      {
        type: "callout",
        text: "Switch to the **main** tab to see the caller side. \`main\` has a \`CALL const[0x1112c]\` instruction, creating a **call-graph edge** to \`parse_record\`. The call graph determines the order of interprocedural analysis: analyze callees before callers.",
        target: { kind: "block", address: "0x111b8", side: "right" },
        color: "var(--accent)",
      },
    ],
  },

  simplify: {
    description: "Rewrites redundant p-code patterns into simpler canonical forms.",
    steps: [
      {
        type: "popup",
        title: "Simplification",
        text: `Compilers and the p-code lifter often produce redundant patterns. For example, \`addi x10, x0, 20\` lifts to \`INT_ADD x10, 0, 20\`, but adding zero is pointless. It should just be \`COPY x10, 20\`.

**Simplification** applies algebraic rewrite rules:
- \`x + 0\` becomes \`COPY x\`
- \`x & 0xFFFFFFFF\` becomes \`COPY x\` (masking with all-ones is identity)
- \`LOAD\` through a known constant address can be simplified

This doesn't change program behavior, but it makes the IR cleaner for subsequent analyses to reason about. Fewer operations = faster and more precise analysis.`,
      },
      {
        type: "callout",
        text: "In \`main\`, \`addi x10, x0, 20\` was \`INT_ADD x10 <- 0, 20\`. Now it's **\`COPY x10 <- 0x14\`**. Why? RISC-V has no \"load immediate\" instruction, so it uses \`add reg, zero, constant\`. The lifter translates this literally, but the simplifier recognizes that adding zero is just a copy.",
        target: { kind: "block", address: "0x110e4", side: "right", yOffset: 0.25, highlightLine: "COPY register[0xa", fn: "main" },
        color: "var(--phase-an)",
      },
      {
        type: "callout",
        text: "Same pattern in \`parse_record\`'s entry block: \`COPY x10 <- 0\` and \`COPY x11 <- 0\` initialize the accumulator and loop counter. Before simplification, these were redundant \`INT_ADD ... 0, 0\` operations. Cleaner IR means later analyses (dataflow, types) have less noise to wade through.",
        target: { kind: "block", address: "0x1112c", side: "right", yOffset: 0.7, highlightLine: "addi x10, x0, 0" },
        color: "var(--accent)",
      },
      {
        type: "callout",
        text: "The return sequence simplifies too: \`INT_ADD unique <- x1, 0\` becomes \`COPY unique <- x1\`. The return address was being \"added to zero\" by the lifter. After simplification, it's clear this is just passing the return address through.",
        target: { kind: "block", address: "0x111b8", side: "right", yOffset: 0.8, highlightLine: "COPY unique" },
        color: "var(--phase-be)",
      },
      {
        type: "callout",
        text: "Notice the **diff highlights** showing what changed. Simplification is a semantics-preserving transformation: the program behaves the same way, but with fewer and simpler operations. This is a key principle in compiler optimization: simplify first, analyze later.",
        target: { kind: "block", address: "0x11164", side: "right", yOffset: 0.1 },
        color: "var(--phase-fe)",
      },
    ],
  },

  dataflow: {
    description: "Propagates known register values forward through the CFG edges.",
    steps: [
      {
        type: "popup",
        title: "Dataflow Analysis",
        text: `Dataflow analysis answers: **what do we know about each register's value at every point in the program?**

It works by propagating facts along CFG edges. If we know \`x10 = 0\` at block entry, and the block stores \`x10\` to memory, we know that memory location holds 0. Facts flow forward through straight-line code and **merge** at join points (like loop headers).

At loop headers, values from two paths merge. If the entry path says \`x10 = 0\` and the back-edge says \`x10 = unknown\`, the merged result is \`x10 = unknown\`. This conservative approach ensures correctness.

This is the foundation. Stack analysis, type inference, and variable recovery all build on dataflow.`,
      },
      {
        type: "callout",
        text: "At the function entry, the dataflow engine tracks that \`x10\` holds the first argument (base pointer) and \`x11\` holds the second (count). These **entry facts** propagate forward through every subsequent block along the CFG edges.",
        target: { kind: "block", address: "0x1112c", side: "right", yOffset: 0.4 },
        color: "var(--accent)",
      },
      {
        type: "callout",
        text: "The **loop header** is where dataflow gets interesting. Values arrive from two paths: the initial entry and the back edge. The engine **merges** them conservatively: if the entry says \`i = 0\` and the back edge says \`i = unknown\`, the merged result is \`unknown\`. This ensures correctness at the cost of precision.",
        target: { kind: "block", address: "0x11154", side: "right" },
        color: "var(--phase-an)",
      },
      {
        type: "callout",
        text: "Inside the loop body, dataflow tracks how values transform: the \`LOAD\` results are unknown (they depend on memory), but the pointer arithmetic (\`base + i * 8\`) can be tracked symbolically. These facts feed into type inference later.",
        target: { kind: "block", address: "0x11164", side: "right", yOffset: 0.3, highlightLine: "LOAD" },
        color: "var(--phase-fe)",
      },
      {
        type: "callout",
        text: "In \`main\`, everything is a constant: no branches, no loops, no uncertainty. Dataflow can track all values precisely. Switch to the \`main\` tab to see the simpler case.",
        target: { kind: "block", address: "0x111b8", side: "right" },
        color: "var(--phase-be)",
      },
    ],
  },

  ssa: {
    description: "Gives every register write a unique version number (Static Single Assignment).",
    steps: [
      {
        type: "popup",
        title: "SSA Form",
        text: `**Static Single Assignment** (SSA) gives every register write a unique version number. Instead of \`x10\` being overwritten many times, we get \`x10_0\`, \`x10_1\`, \`x10_2\`, etc. Each version is defined **only once**.

Why does this matter? Because it makes **data dependencies explicit**. If you see \`x10_3\` used somewhere, you know exactly which instruction created it. No ambiguity.

At loop headers where two execution paths merge, we insert **PHI nodes**: \`x10_2 = PHI(x10_0 from entry, x10_14 from back-edge)\`. PHI nodes say "pick whichever value corresponds to the path we came from."

SSA is the most important transformation in modern compilers and decompilers. It makes almost every subsequent analysis simpler and more precise.`,
      },
      {
        type: "callout",
        text: "Every register now has a **version suffix**: \`x10_0\` is the initial argument from the caller, \`x10_1\` is after the first write. **Why does this help?** Without SSA, when you see \`x10\` used in the loop body, you don't know if it's the argument or something computed in the loop. With SSA, the version number answers that instantly.",
        target: { kind: "block", address: "0x1112c", side: "right", yOffset: 0.1 },
        color: "var(--phase-an)",
      },
      {
        type: "callout",
        text: "**PHI nodes** at the loop header merge values from two paths. Think of it as: \"if we came from the entry, use \`x10_0\`; if we came from the back-edge, use the updated value.\" PHI nodes don't generate real instructions. They're a bookkeeping device that makes the merge point explicit.",
        target: { kind: "block", address: "0x11154", side: "right", highlightLine: "PHI" },
        color: "var(--phase-an)",
      },
      {
        type: "callout",
        text: "Each operation in the loop body creates a new version. You can trace any value's origin by following version numbers backward, like a chain of receipts. This makes optimizations like constant propagation and dead code elimination straightforward: just follow the version chain.",
        target: { kind: "block", address: "0x11164", side: "right", yOffset: 0.3 },
        color: "var(--accent)",
      },
      {
        type: "callout",
        text: "The loop latch produces new versions that flow back to the PHI nodes in the header. This creates a **cycle in the SSA graph**, the defining characteristic of loop-carried dependencies. The accumulator (\`sum\`) and counter (\`i\`) both have this cyclic pattern.",
        target: { kind: "block", address: "0x111a8", side: "right" },
        color: "var(--phase-be)",
      },
    ],
  },

  calls: {
    description: "Identifies function parameters, return values, and calling conventions.",
    steps: [
      {
        type: "popup",
        title: "Call Analysis",
        text: `RISC-V follows a standard calling convention: arguments are passed in registers \`x10\`-\`x17\` (also called \`a0\`-\`a7\`), and return values come back in \`x10\`-\`x11\`.

Call analysis examines each callsite to figure out **which registers carry arguments** and **which carry return values**. It does this by looking at which registers are written before the call (arguments) and read after the call (return values).

At \`0x11118\`, \`main\` passes two values to \`parse_record\`: \`x10\` (a pointer to local data) and \`x11\` (the count value 2). \`parse_record\` returns its result in \`x10\`.

This information is essential for recovering function signatures later.`,
      },
      {
        type: "callout",
        text: "At \`parse_record\`'s entry, the decompiler sees \`x10\` and \`x11\` being stored to the stack immediately. **Why store arguments?** The calling convention says argument registers may be overwritten by callees, so the function saves them to stack slots for safe access later. This pattern tells us: two parameters.",
        target: { kind: "block", address: "0x1112c", side: "right", highlightLine: "sw x10" },
        color: "var(--phase-fe)",
      },
      {
        type: "callout",
        text: "At the exit, \`x10\` holds the accumulated sum, which is the **return value**. How does the decompiler know? It looks at which registers are **live** (used by the caller after the return). The RISC-V convention says \`x10\` is the return register.",
        target: { kind: "block", address: "0x111b8", side: "right", highlightLine: "RETURN" },
        color: "var(--phase-be)",
      },
      {
        type: "callout",
        text: "The loop body reads from pointer \`x10\` (the base argument). The call analysis tracks that this argument flows through the entire function; it's not just used once and discarded. This **liveness** information helps type inference later.",
        target: { kind: "block", address: "0x11164", side: "right", yOffset: 0.3, highlightLine: "LOAD" },
        color: "var(--phase-an)",
      },
      {
        type: "callout",
        text: "Switch to the \`main\` tab to see the caller side. Before the \`CALL\` at \`0x11118\`, main writes \`x10\` (pointer) and \`x11\` (count = 2). After the call, it reads \`x10\` (the result). This bidirectional analysis, matching caller and callee, is how function signatures are recovered.",
        target: { kind: "block", address: "0x111a8", side: "left" },
        color: "var(--accent)",
      },
    ],
  },

  stack: {
    description: "Reverse-engineers each function's stack frame layout into typed memory slots.",
    steps: [
      {
        type: "popup",
        title: "Stack Analysis",
        text: `Every function uses a chunk of memory called the **stack frame** for local variables, saved registers, and passing arguments. The compiler arranges these at fixed offsets from the frame pointer.

Stack analysis examines every memory access relative to the stack/frame pointer and reconstructs the layout. For \`parse_record\`'s 32-byte frame, we discover:
- Offsets +28, +24: saved return address and frame pointer
- Offsets -12, -16: copies of the two arguments
- Offsets -20, -24: two local variables (the accumulator and loop counter)

Check the **analysis panel** on the left. It now shows the stack layout!`,
      },
      {
        type: "callout",
        text: "The **analysis panel** now shows the stack frame! Each colored bar represents a slot type: saved registers (return address, frame pointer), argument copies, and local variables. This is the memory layout the compiler chose.",
        target: { kind: "element", selector: ".analysis-panel", side: "right" },
        color: "var(--phase-an)",
      },
      {
        type: "callout",
        text: "How does the decompiler discover stack slots? By scanning every \`STORE\` and \`LOAD\` that uses the frame pointer (\`x8\`) as base. The store \`sw x10, -12(x8)\` writes to offset -12, creating a slot there. Each unique offset becomes a distinct variable candidate.",
        target: { kind: "block", address: "0x1112c", side: "right", yOffset: 0.35, highlightLine: "sw x10, -12" },
        color: "var(--accent)",
      },
      {
        type: "callout",
        text: "The loop body also accesses the stack: it loads the accumulator from offset -20, adds to it, and stores back. These repeated load-modify-store patterns on the same offset confirm that offset -20 is a **local variable** (the running sum), not a temporary.",
        target: { kind: "block", address: "0x11164", side: "right", yOffset: 0.6, highlightLine: "sw x10, -20" },
        color: "var(--phase-fe)",
      },
    ],
  },

  memory: {
    description: "Partitions memory accesses into distinct regions for alias analysis.",
    steps: [
      {
        type: "popup",
        title: "Memory Partitioning",
        text: `Programs access memory through pointers, and the decompiler needs to know which accesses might **alias** (refer to the same location). If two stores might write to the same address, we can't safely reorder or eliminate them.

Memory partitioning groups accesses into **partitions**: stack slots are distinct from each other (because they're at fixed, different offsets), and pointer-based accesses form separate value-based partitions.

In \`parse_record\`, the struct field accesses at offsets +0 and +4 (via the base pointer argument) form their own partitions, completely separate from the local stack variables. This separation is what allows us to later recognize them as struct field accesses.`,
      },
      {
        type: "callout",
        text: "**Why does aliasing matter?** If the decompiler can't prove that two memory accesses are independent, it must assume they might affect each other. That prevents optimizations and makes the output messier. Partitioning proves independence.",
        target: { kind: "block", address: "0x1112c", side: "right", yOffset: 0.3 },
        color: "var(--phase-fe)",
      },
      {
        type: "callout",
        text: "Stack slots at different offsets are generally independent, since they typically don't alias. Offset -20 (the accumulator) and offset -24 (the loop counter) are in separate partitions. This is the easy case: fixed offsets from a known base.",
        target: { kind: "block", address: "0x11164", side: "right", yOffset: 0.1 },
        color: "var(--phase-an)",
      },
      {
        type: "callout",
        text: "The two \`LOAD\`s from \`0(x10)\` and \`4(x10)\` are trickier: they use a **computed pointer** (base + i*8). The decompiler puts them in separate **value-based partitions** because their offsets differ. This separation is what later lets aggregate type discovery recognize them as struct fields.",
        target: { kind: "block", address: "0x11164", side: "right", yOffset: 0.5, highlightLine: "lw x11, 0(" },
        color: "var(--accent)",
      },
    ],
  },

  scalar_types: {
    description: "Infers primitive types (int, pointer, word) for every SSA value.",
    steps: [
      {
        type: "popup",
        title: "Scalar Type Inference",
        text: `Type inference figures out what **kind of data** each value represents. At the binary level, everything is just 32-bit words. But by observing how values are used, we can recover types:

- Used as a memory base address in \`LOAD\`/\`STORE\`? It's a **pointer**.
- Compared with a signed comparison (\`INT_SLESS\`, from \`blt\`/\`bge\`)? It's a **signed integer**.
- Used in arithmetic but never as an address? It stays as a generic **word** until more evidence appears.

In \`parse_record\`, \`x10_0\` (first argument) is typed as \`pointer:4\` because it's dereferenced with \`LOAD\`. The loop counter is \`int:4\` because it's used in a signed comparison.`,
      },
      {
        type: "callout",
        text: "The analysis panel now shows **type badges** on each stack slot. The key insight: types are inferred from **how values are used**, not from any explicit declaration. The binary has no type information, so the decompiler reconstructs it entirely from usage patterns.",
        target: { kind: "element", selector: ".analysis-panel", side: "right" },
        color: "var(--syn-type)",
      },
      {
        type: "callout",
        text: "\`x10\` is used as a base address in \`LOAD\` here, which is a strong signal for **pointer** type. The reasoning: values used as memory addresses in load/store operations are very likely pointers.",
        target: { kind: "block", address: "0x11164", side: "right", yOffset: 0.3, highlightLine: "LOAD" },
        color: "var(--syn-type)",
      },
      {
        type: "callout",
        text: "The branch condition uses \`INT_SLESS\` (signed less-than). This tells the decompiler that the loop counter and limit are **signed integers**, not unsigned. A small clue in the comparison operator reveals the programmer's intent.",
        target: { kind: "block", address: "0x11154", side: "right", highlightLine: "INT_SLESS" },
        color: "var(--accent)",
      },
    ],
  },

  aggregate_types: {
    description: "Discovers struct and array layouts from strided memory access patterns.",
    steps: [
      {
        type: "popup",
        title: "Aggregate Type Discovery",
        text: `When code accesses memory at **regular intervals** (like offsets +0 and +4 with a stride of 8), that's a strong signal of a struct or array.

The decompiler detects that \`parse_record\` shifts its index left by 3 bits (multiply by 8) before adding to the base pointer, then accesses offsets +0 and +4 from the result. This reveals:
- **Stride = 8 bytes** (from the shift-left-by-3)
- **Two fields at offsets 0 and 4** (from the LOAD offsets)
- Therefore: an 8-byte struct with two 4-byte integer fields

A struct type \`agg_8\` is born! The original C code defined a struct with \`id\` and \`value\` fields, and we just rediscovered it from the binary.`,
      },
      {
        type: "callout",
        text: "The analysis panel now shows a **struct diagram**: \`agg_8\` has two \`int32\` fields at offsets 0 and 4. This was discovered purely from memory access patterns, no debug symbols needed! The original code called this \`struct Record { int id; int value; }\`.",
        target: { kind: "element", selector: ".analysis-panel", side: "right" },
        color: "var(--phase-fe)",
      },
      {
        type: "callout",
        text: "\`slli x11, x11, 3\` shifts left by 3 = multiply by 8. **This is the key clue**: the stride of 8 bytes tells the decompiler that each array element is 8 bytes. Combined with the two 4-byte field accesses, the struct layout emerges: 4 + 4 = 8 bytes per element.",
        target: { kind: "block", address: "0x11164", side: "right", yOffset: 0.2, highlightLine: "slli" },
        color: "var(--phase-fe)",
      },
      {
        type: "callout",
        text: "Two \`LOAD\`s at offsets \`0(x10)\` and \`4(x10)\` from the computed element base. These become \`field_0\` and \`field_4\` of the struct. **How?** The decompiler sees that after computing \`base + i * 8\`, it accesses +0 and +4, two distinct offsets within the 8-byte stride.",
        target: { kind: "block", address: "0x11164", side: "right", yOffset: 0.5, highlightLine: "lw x11, 0(" },
        color: "var(--accent)",
      },
      {
        type: "callout",
        text: "Notice the pointer type in the analysis panel changed from \`ptr\` to **\`agg_8*\`**. The first argument is now recognized as a pointer to an array of structs, not just a raw pointer. Types propagate: discovering the struct refines the pointer type everywhere it's used.",
        target: { kind: "element", selector: ".analysis-panel", side: "right" },
        color: "var(--phase-an)",
      },
    ],
  },

  variables: {
    description: "Groups SSA values back into named high-level variables.",
    steps: [
      {
        type: "popup",
        title: "Variable Recovery",
        text: `SSA form gave every register write a unique name. Now we do the reverse: **group related SSA values back into high-level variables** that a human would recognize.

The algorithm looks at which SSA values share the same stack slot or are connected through PHI nodes. Values that flow into and out of the same slot are the same variable.

The two parameters become \`arg_x10\` (a pointer to the struct array) and \`arg_x11\` (the count). The two local stack slots become \`sum\` (the accumulator at offset -20) and \`i\` (the loop counter at offset -24). These names come from the stack layout and usage patterns.`,
      },
      {
        type: "callout",
        text: "The analysis panel now shows **variable names**: \`arg_x10\`, \`arg_x11\` for parameters, \`sum\` and \`i\` for locals. **How are names chosen?** Parameters get their register name, locals get descriptive names from their stack slot role. In a production decompiler, debug info (if available) would provide the original names.",
        target: { kind: "element", selector: ".analysis-panel", side: "right" },
        color: "var(--phase-be)",
      },
      {
        type: "callout",
        text: "The increment at \`0x111a8\` (\`addi x10, x10, 1\`) becomes **\`i++\`**. The algorithm traced all SSA versions of \`x10\` that flow through the loop counter's stack slot and merged them into one variable \`i\`. Multiple SSA names → one human-readable variable.",
        target: { kind: "block", address: "0x111a8", side: "right", yOffset: 0.3, highlightLine: "addi" },
        color: "var(--phase-be)",
      },
      {
        type: "callout",
        text: "The accumulator in the loop body (loaded, added to, stored back) is identified as variable \`sum\`. The **PHI node** at the loop header connects the initial value (0 from entry) with the updated value (from the back edge), confirming this is one variable across iterations.",
        target: { kind: "block", address: "0x11164", side: "right", yOffset: 0.6 },
        color: "var(--accent)",
      },
    ],
  },

  range: {
    description: "Computes numerical bounds for every variable using abstract interpretation.",
    steps: [
      {
        type: "popup",
        title: "Range Analysis",
        text: `Range analysis computes **numerical bounds** for every variable. Instead of tracking exact values (which is often impractical for loops), it tracks intervals: [min, max].

It uses **abstract interpretation**: symbolically executing the program with ranges instead of concrete values. The loop counter \`i\` starts at 0 and increments by 1 each iteration. Since we don't know how many iterations happen, the range widens to **[0, +inf)**.

In \`main\`, all locals are constants (assigned once, never modified in a loop), so their ranges are exact: \`[20,20]\`, \`[2,2]\`, \`[10,10]\`, \`[1,1]\`.

Ranges can help detect potential bugs (integer overflow), optimize code (remove unlikely branches), and check array access bounds.`,
      },
      {
        type: "callout",
        text: "**Range badges** appear on the analysis panel. The loop counter \`i\` has range \`[0, +∞)\` because the loop bound (\`count\`) is a runtime parameter. The accumulator \`sum\` starts at \`[0, 0]\`. **Why are ranges useful?** They can help detect buffer overflows, reason about loop termination, and enable optimizations like removing infeasible branches.",
        target: { kind: "element", selector: ".analysis-panel", side: "right" },
        color: "var(--accent)",
      },
      {
        type: "callout",
        text: "The comparison \`i < count\` at the loop header creates a **conditional constraint**: inside the loop body, \`i\` is expected to be in \`[0, count-1]\`. Outside the loop, \`i >= count\`. Range analysis tracks these path-sensitive bounds through each branch.",
        target: { kind: "block", address: "0x11154", side: "right", highlightLine: "CBRANCH" },
        color: "var(--accent)",
      },
      {
        type: "callout",
        text: "**Abstract interpretation** runs the loop symbolically. After one iteration, \`i\` could be 0 or 1. After two, 0-2. The engine detects this widening pattern and jumps to the fixed point: \`[0, +∞)\`. This technique guarantees termination of the analysis even for infinite loops.",
        target: { kind: "block", address: "0x111a8", side: "right" },
        color: "var(--phase-an)",
      },
    ],
  },

  interproc: {
    description: "Infers complete function signatures by analyzing cross-function data flow.",
    steps: [
      {
        type: "popup",
        title: "Interprocedural Analysis",
        text: `Now the decompiler looks **across function boundaries**. By combining all the information gathered so far (call analysis, type inference, variable recovery, aggregate types), it constructs complete function signatures.

\`parse_record\` takes two parameters:
1. An \`agg_8*\` (pointer to our discovered 8-byte struct array)
2. An \`int32\` (the element count)

And it returns an \`int32\` (the accumulated sum).

\`main\` takes no parameters and has no return value.

This is the final analytical step. We now know enough to generate C code.`,
      },
      {
        type: "callout",
        text: "The **function prototype** now appears in the analysis panel: \`int32 parse_record(agg_8*, int32)\`. This is the culmination of every previous analysis. Scalar types gave us \`int32\` and \`ptr\`, aggregate types refined the pointer to \`agg_8*\`, and call analysis identified which registers are parameters vs. return values.",
        target: { kind: "element", selector: ".analysis-panel", side: "right" },
        color: "var(--phase-fe)",
      },
      {
        type: "callout",
        text: "**Why is interprocedural analysis separate from call analysis?** Call analysis identifies *which registers* carry data. Interprocedural analysis combines that with *type information* from all analyses. It needs aggregate types, scalar types, and variable names, information that didn't exist when call analysis ran.",
        target: { kind: "block", address: "0x1112c", side: "right", yOffset: 0.2 },
        color: "var(--phase-an)",
      },
      {
        type: "callout",
        text: "The entry block stores \`x10\` (now typed \`agg_8*\`) and \`x11\` (typed \`int32\`) to the stack. With complete signatures, the code generator can emit proper C function declarations with typed parameters instead of generic register names.",
        target: { kind: "block", address: "0x1112c", side: "right", yOffset: 0.5 },
        color: "var(--accent)",
      },
    ],
  },

  structuring: {
    description: "Recovers high-level control structures (loops, if/else) from the CFG.",
    steps: [
      {
        type: "popup",
        title: "Control Flow Structuring",
        text: `The CFG is a graph of blocks and edges, but C code uses structured constructs: \`while\`, \`if/else\`, \`for\`, \`switch\`. The structuring pass finds patterns in the CFG that correspond to these constructs.

A **while loop** is detected when:
- A block (the header) has a conditional branch
- One successor leads to a body that eventually loops back to the header (the back edge)
- The other successor is the exit

For \`parse_record\`, blocks \`0x11154\` (header), \`0x11160\`/\`0x11164\` (body), and \`0x111a8\` (increment) form a **while loop**. Block \`0x111b8\` is the exit.

\`main\` is just a straight-line sequence. No gotos needed. The CFG is fully **reducible** (all loops are natural loops), which means it maps cleanly to structured C code.`,
      },
      {
        type: "callout",
        text: "The dashed box highlights the **while loop region**: header, body, and latch. The structuring algorithm identified this by finding a **back edge** (from latch to header) and computing all blocks that can reach the header through that edge. This is called a **natural loop**.",
        target: { kind: "block", address: "0x11154", side: "right" },
        color: "var(--phase-an)",
      },
      {
        type: "callout",
        text: "The loop header becomes the \`while\` condition. **Why \`while\` and not \`do-while\`?** Because the condition is tested *before* the first iteration: the entry edge goes to the header, not the body. If the condition is false initially, the body never executes.",
        target: { kind: "block", address: "0x11154", side: "left", highlightLine: "CBRANCH" },
        color: "var(--accent)",
      },
      {
        type: "callout",
        text: "The exit block is **outside** the loop region. In C, this maps to everything after the closing \`}\` of the \`while\`. It restores saved registers and returns the accumulated sum.",
        target: { kind: "block", address: "0x111b8", side: "right" },
        color: "var(--phase-be)",
      },
      {
        type: "callout",
        text: "**What if the CFG can't be structured?** Some CFGs (with irreducible control flow, like \`goto\` spaghetti) can't map to clean C. In those cases, the decompiler would emit \`goto\` statements. This CFG is **reducible**, so all control flow maps cleanly to \`while\`/\`if\`/\`for\` statements.",
        target: { kind: "block", address: "0x1112c", side: "right" },
        color: "var(--phase-fe)",
      },
    ],
  },

  c_lowering: {
    description: "Converts structured IR into C-like statements with typed variables.",
    steps: [
      {
        type: "popup",
        title: "C Lowering",
        text: `With all analysis complete (types, variables, ranges, control structures), we can finally generate **C-like code**.

Each p-code operation translates to a C statement:
- \`STORE\` becomes an assignment (\`x = value\`)
- \`LOAD\` becomes a variable read
- \`CBRANCH\` becomes a \`while\` condition
- \`INT_ADD\` becomes the \`+\` operator
- Array indexing with stride becomes \`array[i].field\`

The struct field accesses become \`arg_x10_4[local_24_4].field_0\`, a real **array-of-structs access pattern**. We're almost at the finish line!`,
      },
      {
        type: "callout",
        text: "\`parse_record\`'s body shows a clean **while loop** with struct field accesses: \`arg_x10[i].field_0 + arg_x10[i].field_4\`. From 232 bytes of machine code to readable loop logic! The struct stride (8 bytes) and field offsets (0, 4) produced the array-of-structs access pattern.",
        target: { kind: "element", selector: ".function-section:last-child", side: "right" },
        color: "var(--phase-be)",
      },
      {
        type: "callout",
        text: "\`main\` shows the calling setup: stores constants (20, 2, 10, 1) to local variables on the stack, takes the address of the struct data, and calls \`parse_record\`. The code generator emitted typed variables where we once had raw register numbers.",
        target: { kind: "element", selector: ".function-section:first-child", side: "right" },
        color: "var(--phase-fe)",
      },
      {
        type: "callout",
        text: "**This is not the final output yet.** C lowering produces an intermediate form close to C but still using internal names (\`arg_x10\`, \`field_0\`). The final step cleans up variable names, adds typedefs, and produces compilable C code.",
        target: { kind: "element", selector: ".function-section:last-child", side: "left" },
        color: "var(--accent)",
      },
    ],
  },

  c: {
    description: "The final decompiled C output with typedefs, declarations, and function bodies.",
    steps: [
      {
        type: "popup",
        title: "Final C Output",
        text: `This is it! **2,848 bytes of raw binary** have been transformed into readable C source code.

The output includes:
- A \`typedef\` for our discovered struct (\`agg_8\` with two \`int32_t\` fields)
- Forward declarations for both functions
- Complete function bodies with proper types and control flow

\`parse_record\` iterates an array of structs, summing both fields of each element. \`main\` sets up local data and calls it.

From incomprehensible machine bytes to code that tells a clear story. That's the magic of decompilation. Every step in this pipeline contributed: loading, decoding, lifting, control flow, dataflow, types, variables, structures, and finally code generation.`,
      },
      {
        type: "callout",
        text: "The struct \`agg_8\` is now a proper **C typedef**. Remember how we discovered it: the \`slli x11, x11, 3\` (multiply by 8) revealed the stride, and two \`LOAD\`s at offsets 0 and 4 revealed the fields. From bit shifts in machine code to a clean struct definition.",
        target: { kind: "element", selector: ".code-surface", side: "right" },
        color: "var(--phase-fe)",
      },
      {
        type: "callout",
        text: "Look at \`parse_record\`: a clean \`while\` loop iterating structs. Compare this with what we started: 232 bytes of incomprehensible machine code. Each pipeline stage contributed something: decoding gave us instructions, lifting gave us operations, SSA gave us data flow, type inference gave us types, and structuring gave us the \`while\` loop.",
        target: { kind: "element", selector: ".code-surface", side: "right" },
        color: "var(--phase-be)",
      },
      {
        type: "callout",
        text: "**What's still imperfect?** The variable names are generic (\`arg_x10\`, \`field_0\` instead of \`records\`, \`id\`). Without debug symbols, the decompiler can't recover original names. A production decompiler would use DWARF debug info if available, or let the analyst rename them manually.",
        target: { kind: "element", selector: ".code-surface", side: "left" },
        color: "var(--accent)",
      },
    ],
  },
};

export default WALKTHROUGHS;

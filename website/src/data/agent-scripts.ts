export interface AgentMessage {
  type: "intro" | "changed" | "graph" | "concept" | "trivia";
  text: string;
}

const AGENT_SCRIPTS: Record<string, AgentMessage[]> = {
  hero: [
    { type: "intro", text: "Welcome to tiny-dec! I'll walk you through how a decompiler transforms raw RISC-V machine code into readable C — step by step, stage by stage." },
    { type: "concept", text: "We have 19 stages ahead of us. Each one refines the representation: from raw bytes, through assembly, intermediate representations, and finally to C code." },
    { type: "trivia", text: "Our test binary contains two functions: main and parse_record. parse_record iterates an array of 8-byte structs, summing two fields. Simple enough to follow, complex enough to exercise every stage." },
  ],
  raw: [
    { type: "intro", text: "These are the raw bytes of the .text section — 232 bytes of RISC-V machine code. This is all we start with: no symbols, no structure, just bytes." },
    { type: "concept", text: "Each 4-byte group is one RISC-V instruction. The hex on the left is the address in memory. Everything the decompiler produces is derived from these bytes alone." },
    { type: "trivia", text: "RISC-V uses fixed 32-bit instructions (in the base ISA). That regularity makes decoding straightforward — unlike x86, where instructions can be anywhere from 1 to 15 bytes." },
  ],
  loader: [
    { type: "intro", text: "The loader reads the ELF binary and extracts metadata: architecture (riscv32), endianness (little-endian), entry point (0x110e4), and the code section." },
    { type: "concept", text: "ELF (Executable and Linkable Format) is the standard binary format on Linux. It contains sections (.text for code, .data for initialized data) and headers describing the target architecture." },
  ],
  decode: [
    { type: "intro", text: "Each 4-byte word is decoded into a structured instruction: opcode, operands, and addressing modes. The raw bits become meaningful assembly." },
    { type: "changed", text: "Compare this to the raw bytes — now every instruction has a mnemonic (addi, sw, lw, jal) and named operands (x2, x8, x10)." },
    { type: "concept", text: "RISC-V has a clean encoding: the opcode is always in bits [6:0], registers in fixed positions. This makes decoding fast and unambiguous." },
  ],
  pcode: [
    { type: "intro", text: "Each assembly instruction is lifted to P-code — a register-transfer language that makes implicit effects explicit. One assembly instruction may become several P-code operations." },
    { type: "changed", text: "Notice how 'sw x1, 28(x2)' became two operations: INT_ADD to compute the address, then STORE to write the value. P-code makes every step explicit." },
    { type: "concept", text: "P-code (inspired by Ghidra's Sleigh) abstracts away ISA details. Whether the source is ARM, x86, or RISC-V, the analysis operates on the same IR from here on." },
  ],
  disasm: [
    { type: "intro", text: "Recursive disassembly partitions instructions into basic blocks. Each block has a single entry, a single exit (the terminator), and successor edges." },
    { type: "changed", text: "This is where the CFG appears for the first time! Each box is a basic block. Edges show which block can execute after which." },
    { type: "graph", text: "Look at parse_record's CFG. Block 0x1112c initializes locals. Block 0x11154 is the loop header — it checks a condition and either falls through to the body or jumps to the exit. The dashed back-edge from 0x111a8 creates the loop." },
    { type: "concept", text: "A Control Flow Graph (CFG) is the backbone of all program analysis. Every subsequent stage operates on this structure — refining what's inside the blocks while preserving the graph topology." },
  ],
  ir: [
    { type: "intro", text: "Functions are placed into IR containers with call-graph edges. The block content is identical to the disassembly — this stage is about organizing functions, not transforming code." },
    { type: "changed", text: "The CFG looks the same, but now we know the inter-procedural structure: main calls parse_record at address 0x11118. This call-graph drives all later interprocedural analysis." },
    { type: "concept", text: "The IR container holds everything about a function: its blocks, its call sites, and metadata like reachability. It's the fundamental unit that all analysis passes operate on." },
  ],
  simplify: [
    { type: "intro", text: "Canonical simplification rewrites redundant operations. 'addi x10, x0, 20' (add zero to 20) becomes 'COPY x10 <- const[0x14]'. Fewer operations per instruction." },
    { type: "changed", text: "Look for COPY operations that replaced INT_ADD with a zero operand. The instruction count stays the same, but many two-operand additions became simpler single copies." },
    { type: "concept", text: "Canonicalization normalizes the IR so later passes see fewer patterns. Instead of 'x + 0', 'x * 1', and '0 + x' being different, they all become 'x'. Simpler IR means simpler analysis." },
  ],
  dataflow: [
    { type: "intro", text: "Intraprocedural dataflow propagates known facts through the CFG. Constant values, reachability, and liveness information flow along edges." },
    { type: "changed", text: "The IR looks very similar to the previous stage. Most changes are internal metadata — the analyzer now knows which values are live at each program point." },
    { type: "concept", text: "Dataflow analysis is iterative: facts propagate forward (constants) and backward (liveness) until a fixed point. For loops, this may take multiple passes over the loop body." },
  ],
  ssa: [
    { type: "intro", text: "SSA construction gives every variable definition a unique version. x10 becomes x10_0, x10_1, x10_2. Each name is defined exactly once in the entire function." },
    { type: "changed", text: "This is a major visible change! Every register reference now has a version subscript. And the header block gained PHI functions at the top — those are new." },
    { type: "graph", text: "The PHI at 0x11154 merges x10_1 (from entry) with x10_14 (from the latch). PHI 'selects' the right version depending on which edge we arrived from. Memory is versioned too: m0, m1, m2..." },
    { type: "concept", text: "Static Single Assignment makes dataflow trivial: to find where a value comes from, just look at its unique definition. No need to track 'which version of x10.' LLVM, GCC, and all modern compilers use SSA." },
    { type: "trivia", text: "MEM_PHI works like PHI but for memory state — it merges memory versions from different paths. This lets the analyzer reason about memory as precisely as registers." },
  ],
  calls: [
    { type: "intro", text: "The RISC-V ABI maps arguments to registers x10-x17 and return values to x10-x11. At callsite 0x11118, main passes a pointer in x10 and count=2 in x11." },
    { type: "changed", text: "Look at main's block — the CALL instruction expanded with CALL_CLOBBER (registers the callee might overwrite) and CALL_RETURN (the return value binding) lines." },
    { type: "concept", text: "ABI (Application Binary Interface) is the contract between caller and callee: which registers hold arguments, which are callee-saved, how the stack is managed. Without it, we couldn't reason across function boundaries." },
  ],
  stack: [
    { type: "intro", text: "Each function's stack frame is decomposed into typed slots. main has 6 slots: four locals, plus callee-saved x8 and return address x1." },
    { type: "changed", text: "The CFG blocks look the same as before — this analysis produces stack layout metadata rather than transforming the IR. But now we know what each memory access refers to." },
    { type: "concept", text: "Stack layout recovery maps raw memory offsets (sp-24, fp-12) to semantic roles: local variables, saved registers, argument homes. This is essential for recovering meaningful variable names later." },
  ],
  memory: [
    { type: "intro", text: "Each memory access is assigned to a partition — a group of accesses that provably refer to the same storage. This is like alias analysis but for a decompiler." },
    { type: "changed", text: "The blocks haven't changed, but the analyzer now groups all memory accesses into partitions: stack locals, argument homes, saved registers, and pointer dereferences." },
    { type: "graph", text: "parse_record has 8 partitions: 4 stack slots, 2 argument homes, and 2 value-based partitions for the struct field accesses at x10+0 and x10+4. Those value partitions will become struct fields later." },
    { type: "concept", text: "Memory partitioning is a form of alias analysis: it determines which memory accesses can (or can't) interfere. Non-aliasing partitions can be optimized independently." },
  ],
  scalar_types: [
    { type: "intro", text: "Type inference assigns int, pointer, or word type to every SSA value and memory partition. Values used in address computations get pointer type; loop counters get int." },
    { type: "changed", text: "No visible changes in the CFG blocks — type information is metadata. But now x10_0 in parse_record is typed pointer:4 (it's a base address), while loop variables are int:4." },
    { type: "concept", text: "The type lattice is: ⊥ → int/pointer/word → ⊤. Values start at ⊥ and refine based on how they're used. A value used in both address computation and arithmetic stays as word (ambiguous)." },
  ],
  aggregate_types: [
    { type: "intro", text: "Strided pointer accesses reveal aggregate structure. parse_record accesses x10_0 at offsets +0 and +4 with stride 8, revealing a struct with two 4-byte int fields." },
    { type: "changed", text: "Still no visible block changes, but the analyzer discovered agg_8 — an 8-byte struct with field_0 and field_4, both int32. This comes from the shift-left-by-3 (multiply by 8) indexing pattern." },
    { type: "concept", text: "Aggregate recovery is one of the hardest decompilation problems. The key insight: if a pointer is indexed with stride S, there's a struct of size S. Field offsets within that stride reveal the layout." },
  ],
  variables: [
    { type: "intro", text: "SSA values are mapped to high-level variables. Stack slots become named locals, register parameters become arguments with meaningful names." },
    { type: "changed", text: "Major visible change! Look at the blocks — SSA names like x10_1 are now local_20_4, x10_0 becomes arg_x10_4. Every block's content has changed to use variable names." },
    { type: "concept", text: "Variable recovery coalesces SSA versions back into variables. x10_1, x10_2, x10_3 might all become 'local_20_4' if they represent the same high-level variable at different points." },
  ],
  range: [
    { type: "intro", text: "Value range analysis determines the possible values of each variable — like 'this loop counter goes from 0 to n'. This enables bounds checking and optimization." },
    { type: "changed", text: "No visible block changes — ranges are metadata. But the analyzer now knows things like: local_24_4 starts at 0, increments by 1, and is bounded by arg_x11_4." },
    { type: "concept", text: "Range analysis uses abstract interpretation: instead of tracking exact values, we track intervals [min, max]. This over-approximation is sound — if range says 'always positive', it really is." },
  ],
  interproc: [
    { type: "intro", text: "Cross-function prototype inference determines each function's parameter and return types by looking at how call sites pass arguments and use return values." },
    { type: "changed", text: "No visible block changes. But the analysis inferred: parse_record(agg_8* arg_x10_4, int32_t arg_x11_4) → uint32_t. The pointer-to-struct type propagated from callee analysis." },
    { type: "concept", text: "Interprocedural analysis is iterative: caller shapes callee's signature, which reshapes caller's types, until convergence. This is how the struct pointer type flows from parse_record back to main." },
  ],
  structuring: [
    { type: "intro", text: "The final analysis stage recovers high-level control flow. The loop header, body, and latch merge into a 'while' construct. Branches become if/else." },
    { type: "changed", text: "The CFG structure itself changes here. The 6-block loop collapses into 3 nodes: init, while-loop, and exit. Watch the blocks merge and edges simplify." },
    { type: "graph", text: "The header (0x11154), fall-through (0x11160), body (0x11164), and latch (0x111a8) have merged into a single 'while' block. The back-edge becomes implicit — it's a loop!" },
    { type: "concept", text: "Structuring uses pattern matching on the CFG: back-edges indicate loops (while/for), two-way branches indicate if/else. The goal: produce code with no gotos." },
  ],
  c_lowering: [
    { type: "intro", text: "The structured IR is lowered to C-like statements with typed variables. The IR operations become assignments, expressions, and control flow keywords." },
    { type: "changed", text: "We're back to text! The CFG disappears — the code is now sequential with while-loops and assignments. parse_record has a clear: init, while (i < n), accumulate fields, return." },
    { type: "concept", text: "C lowering is mostly a syntax transformation: IR operations map to C operators, memory partitions map to local variables, and the structured CFG maps to loops and branches." },
  ],
  c: [
    { type: "intro", text: "The final rendered C includes a typedef struct agg_8, forward declarations, and two complete function bodies. From 232 bytes of machine code to readable C." },
    { type: "changed", text: "This is it — the complete decompiled output. Notice the struct definition, typed function signatures, while loop with array indexing and field access. All recovered automatically." },
    { type: "concept", text: "The 19 stages took us from raw bytes to this. Each stage was essential: without SSA, we couldn't track values; without type inference, we'd have raw casts everywhere; without structuring, we'd have gotos." },
    { type: "trivia", text: "Compare this to the original: the struct with field_0 and field_4, the while loop iterating an array — it's functionally equivalent to what a human would write." },
  ],
  completion: [
    { type: "intro", text: "You've walked through the entire decompilation pipeline! From 232 bytes of raw RISC-V machine code to clean, readable C with struct definitions and while loops." },
    { type: "concept", text: "The key insight: decompilation is a series of refinements. Each stage adds a small piece of understanding — control flow, data types, variable names, high-level structure — until the machine code becomes human-readable." },
    { type: "trivia", text: "tiny-dec is an educational decompiler built for learning. Real-world decompilers like Ghidra, IDA, and Binary Ninja use similar pipelines but handle far more complexity: indirect jumps, exception handling, optimized code, and multi-architecture support." },
  ],
};

export default AGENT_SCRIPTS;

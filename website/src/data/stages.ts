// Stage data for tiny-dec pipeline visualization
// This file defines the decompilation stages and their CFG representations

export type Phase = "frontend" | "analysis" | "backend";
export type ViewMode = "text" | "cfg";

export interface CFGBlock {
  address: string;
  label?: string;
  ir: string;
  annotations?: string[];
}

export interface CFGEdge {
  source: string;
  target: string;
  label?: string;
  type: "normal" | "back";
}

export interface CFGRegion {
  type: "while" | "if" | "block";
  label: string;
  blocks: string[];
  color: string;
}

export interface CFGData {
  blocks: CFGBlock[];
  edges: CFGEdge[];
  regions?: CFGRegion[];
}

export interface Stage {
  id: string;
  number: number;
  name: string;
  phase: Phase;
  description: string;
  githubDir: string;
  viewMode: ViewMode;
  content: string;
  cfg?: {
    main: CFGData;
    parse_record: CFGData;
  };
}

export const PHASE_META: Record<Phase, { label: string; color: string }> = {
  frontend: { label: "Frontend", color: "#5b9bd5" },
  analysis: { label: "Analysis", color: "#9b6fcc" },
  backend: { label: "Backend", color: "#5cb85c" },
};

/* ─── Raw Bytes (full ELF binary) ───────────────────────────────────────────── */
// Loaded from external file to keep this module readable
import { RAW_BYTES_CONTENT } from "./rawbytes";

/* ─── Stages ────────────────────────────────────────────────────────────────── */
const STAGES: Stage[] = [

  /* ── -1: RAW BYTES ──────────────────────────────────────────────── */
  {
    id: "raw",
    number: -1,
    name: "Raw Bytes",
    phase: "frontend",
    description: "The entire ELF binary: 2,848 bytes containing headers, code, debug info, and metadata.",
    githubDir: "",
    viewMode: "text",
    content: RAW_BYTES_CONTENT,
  },

  /* ── 0: LOADER ──────────────────────────────────────────────── */
  {
    id: "loader",
    number: 0,
    name: "Loader",
    phase: "frontend",
    description: "The loader reads the ELF binary, identifies the architecture (RISC-V 32-bit), finds the entry point, and locates the target function main via the symbol table. This establishes the starting point for all subsequent analysis.",
    githubDir: "tiny_dec/loader",
    viewMode: "text",
    content: `  binary: tests/fixtures/bin/fixture_struct_O0_nopie.elf
  arch: riscv32 (32-bit, little-endian)
  entrypoint: 0x110e4
  main: 0x110e4
  main_source: symbol_table

  sections:
    .text    vaddr=0x110e4 size=0xe8 end=0x111cc
    .rodata  vaddr=0x100d4 size=0x10 end=0x100e4`,
  },

  /* ── 1: INSTRUCTION DECODE ──────────────────────────────────────────────── */
  {
    id: "decode",
    number: 1,
    name: "Instruction Decode",
    phase: "frontend",
    description: "The decoder reads each 4-byte word and maps it to a RISC-V instruction with operands. We see addi, sw, lw, jal, jalr, and bge instructions with their register and immediate operands.",
    githubDir: "tiny_dec/decode",
    viewMode: "text",
    content: `  ; ---- main (0x110e4) ----
  0x000110e4: 0xfe010113  addi x2, x2, -32
  0x000110e8: 0x00112e23  sw x1, 28(x2)
  0x000110ec: 0x00812c23  sw x8, 24(x2)
  0x000110f0: 0x02010413  addi x8, x2, 32
  0x000110f4: 0x01400513  addi x10, x0, 20
  0x000110f8: 0xfea42a23  sw x10, -12(x8)
  0x000110fc: 0x00200593  addi x11, x0, 2
  0x00011100: 0xfeb42823  sw x11, -16(x8)
  0x00011104: 0x00a00513  addi x10, x0, 10
  0x00011108: 0xfea42623  sw x10, -20(x8)
  0x0001110c: 0x00100513  addi x10, x0, 1
  0x00011110: 0xfea42423  sw x10, -24(x8)
  0x00011114: 0xfe840513  addi x10, x8, -24
  0x00011118: 0x014000ef  jal x1, 0x1112c
  0x0001111c: 0x01c12083  lw x1, 28(x2)
  0x00011120: 0x01812403  lw x8, 24(x2)
  0x00011124: 0x02010113  addi x2, x2, 32
  0x00011128: 0x00008067  jalr x0, 0(x1)

  ; ---- parse_record (0x1112c) ----
  0x0001112c: 0xfe010113  addi x2, x2, -32
  0x00011130: 0x00112e23  sw x1, 28(x2)
  0x00011134: 0x00812c23  sw x8, 24(x2)
  0x00011138: 0x02010413  addi x8, x2, 32
  0x0001113c: 0xfea42a23  sw x10, -12(x8)
  0x00011140: 0xfeb42823  sw x11, -16(x8)
  0x00011144: 0x00000513  addi x10, x0, 0
  0x00011148: 0xfea42623  sw x10, -20(x8)
  0x0001114c: 0xfea42423  sw x10, -24(x8)
  0x00011150: 0x0040006f  jal x0, 0x11154
  0x00011154: 0xfe842503  lw x10, -24(x8)
  0x00011158: 0xff042583  lw x11, -16(x8)
  0x0001115c: 0x04b55e63  bge x10, x11, 0x111b8
  0x00011160: 0x0040006f  jal x0, 0x11164
  0x00011164: 0xff442503  lw x10, -12(x8)
  0x00011168: 0xfe842583  lw x11, -24(x8)
  0x0001116c: 0x00359593  slli x11, x11, 3
  0x00011170: 0x00b50533  add x10, x10, x11
  0x00011174: 0x00052583  lw x11, 0(x10)
  0x00011178: 0xfec42503  lw x10, -20(x8)
  0x0001117c: 0x00b50533  add x10, x10, x11
  0x00011180: 0xfea42623  sw x10, -20(x8)
  0x00011184: 0xff442503  lw x10, -12(x8)
  0x00011188: 0xfe842583  lw x11, -24(x8)
  0x0001118c: 0x00359593  slli x11, x11, 3
  0x00011190: 0x00b50533  add x10, x10, x11
  0x00011194: 0x00452583  lw x11, 4(x10)
  0x00011198: 0xfec42503  lw x10, -20(x8)
  0x0001119c: 0x00b50533  add x10, x10, x11
  0x000111a0: 0xfea42623  sw x10, -20(x8)
  0x000111a4: 0x0040006f  jal x0, 0x111a8
  0x000111a8: 0xfe842503  lw x10, -24(x8)
  0x000111ac: 0x00150513  addi x10, x10, 1
  0x000111b0: 0xfea42423  sw x10, -24(x8)
  0x000111b4: 0xfa1ff06f  jal x0, 0x11154
  0x000111b8: 0xfec42503  lw x10, -20(x8)
  0x000111bc: 0x01c12083  lw x1, 28(x2)
  0x000111c0: 0x01812403  lw x8, 24(x2)
  0x000111c4: 0x02010113  addi x2, x2, 32
  0x000111c8: 0x00008067  jalr x0, 0(x1)`,
  },

  /* ── 2: P-CODE LIFT ──────────────────────────────────────────────── */
  {
    id: "pcode",
    number: 2,
    name: "P-code Lift",
    phase: "frontend",
    description: "Each RISC-V instruction is lifted into one or more p-code operations: INT_ADD, STORE, LOAD, COPY, CALL, RETURN. This bridges the gap between machine-specific assembly and our architecture-neutral IR.",
    githubDir: "tiny_dec/ir",
    viewMode: "text",
    content: `  ; ---- main (0x110e4) ----
  0x000110e4: 0xfe010113  addi x2, x2, -32
      INT_ADD register[0x2:4] <- register[0x2:4], const[0xffffffe0:4]
  0x000110e8: 0x00112e23  sw x1, 28(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x1c:4]
      STORE unique[0x0:4], register[0x1:4]
  0x000110ec: 0x00812c23  sw x8, 24(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x18:4]
      STORE unique[0x0:4], register[0x8:4]
  0x000110f0: 0x02010413  addi x8, x2, 32
      INT_ADD register[0x8:4] <- register[0x2:4], const[0x20:4]
  0x000110f4: 0x01400513  addi x10, x0, 20
      INT_ADD register[0xa:4] <- const[0x0:4], const[0x14:4]
  0x000110f8: 0xfea42a23  sw x10, -12(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff4:4]
      STORE unique[0x0:4], register[0xa:4]
  0x000110fc: 0x00200593  addi x11, x0, 2
      INT_ADD register[0xb:4] <- const[0x0:4], const[0x2:4]
  0x00011100: 0xfeb42823  sw x11, -16(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff0:4]
      STORE unique[0x0:4], register[0xb:4]
  0x00011104: 0x00a00513  addi x10, x0, 10
      INT_ADD register[0xa:4] <- const[0x0:4], const[0xa:4]
  0x00011108: 0xfea42623  sw x10, -20(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffec:4]
      STORE unique[0x0:4], register[0xa:4]
  0x0001110c: 0x00100513  addi x10, x0, 1
      INT_ADD register[0xa:4] <- const[0x0:4], const[0x1:4]
  0x00011110: 0xfea42423  sw x10, -24(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffe8:4]
      STORE unique[0x0:4], register[0xa:4]
  0x00011114: 0xfe840513  addi x10, x8, -24
      INT_ADD register[0xa:4] <- register[0x8:4], const[0xffffffe8:4]
  0x00011118: 0x014000ef  jal x1, 0x1112c
      COPY register[0x1:4] <- const[0x1111c:4]
      CALL const[0x1112c:4]
  0x0001111c: 0x01c12083  lw x1, 28(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x1c:4]
      LOAD unique[0x4:4] <- unique[0x0:4]
      COPY register[0x1:4] <- unique[0x4:4]
  0x00011120: 0x01812403  lw x8, 24(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x18:4]
      LOAD unique[0x4:4] <- unique[0x0:4]
      COPY register[0x8:4] <- unique[0x4:4]
  0x00011124: 0x02010113  addi x2, x2, 32
      INT_ADD register[0x2:4] <- register[0x2:4], const[0x20:4]
  0x00011128: 0x00008067  jalr x0, 0(x1)
      INT_ADD unique[0x0:4] <- register[0x1:4], const[0x0:4]
      INT_AND unique[0x4:4] <- unique[0x0:4], const[0xfffffffe:4]
      RETURN unique[0x4:4]

  ; ---- parse_record (0x1112c) ----
  0x0001112c: 0xfe010113  addi x2, x2, -32
      INT_ADD register[0x2:4] <- register[0x2:4], const[0xffffffe0:4]
  0x00011130: 0x00112e23  sw x1, 28(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x1c:4]
      STORE unique[0x0:4], register[0x1:4]
  0x00011134: 0x00812c23  sw x8, 24(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x18:4]
      STORE unique[0x0:4], register[0x8:4]
  0x00011138: 0x02010413  addi x8, x2, 32
      INT_ADD register[0x8:4] <- register[0x2:4], const[0x20:4]
  0x0001113c: 0xfea42a23  sw x10, -12(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff4:4]
      STORE unique[0x0:4], register[0xa:4]
  0x00011140: 0xfeb42823  sw x11, -16(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff0:4]
      STORE unique[0x0:4], register[0xb:4]
  0x00011144: 0x00000513  addi x10, x0, 0
      COPY register[0xa:4] <- const[0x0:4]
  0x00011148: 0xfea42623  sw x10, -20(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffec:4]
      STORE unique[0x0:4], register[0xa:4]
  0x0001114c: 0xfea42423  sw x10, -24(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffe8:4]
      STORE unique[0x0:4], register[0xa:4]
  0x00011150: 0x0040006f  jal x0, 0x11154
      BRANCH const[0x11154:4]
  0x00011154: 0xfe842503  lw x10, -24(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffe8:4]
      LOAD register[0xa:4] <- unique[0x0:4]
  0x00011158: 0xff042583  lw x11, -16(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff0:4]
      LOAD register[0xb:4] <- unique[0x0:4]
  0x0001115c: 0x04b55e63  bge x10, x11, 0x111b8
      INT_SLESS unique[0x0:1] <- register[0xa:4], register[0xb:4]
      BOOL_NEGATE unique[0x4:1] <- unique[0x0:1]
      CBRANCH const[0x111b8:4], unique[0x4:1]
  0x00011160: 0x0040006f  jal x0, 0x11164
      BRANCH const[0x11164:4]
  0x00011164: 0xff442503  lw x10, -12(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff4:4]
      LOAD register[0xa:4] <- unique[0x0:4]
  0x00011168: 0xfe842583  lw x11, -24(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffe8:4]
      LOAD register[0xb:4] <- unique[0x0:4]
  0x0001116c: 0x00359593  slli x11, x11, 3
      INT_LEFT register[0xb:4] <- register[0xb:4], const[0x3:4]
  0x00011170: 0x00b50533  add x10, x10, x11
      INT_ADD register[0xa:4] <- register[0xa:4], register[0xb:4]
  0x00011174: 0x00052583  lw x11, 0(x10)
      COPY unique[0x0:4] <- register[0xa:4]
      LOAD register[0xb:4] <- unique[0x0:4]
  0x00011178: 0xfec42503  lw x10, -20(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffec:4]
      LOAD register[0xa:4] <- unique[0x0:4]
  0x0001117c: 0x00b50533  add x10, x10, x11
      INT_ADD register[0xa:4] <- register[0xa:4], register[0xb:4]
  0x00011180: 0xfea42623  sw x10, -20(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffec:4]
      STORE unique[0x0:4], register[0xa:4]
  0x00011184: 0xff442503  lw x10, -12(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff4:4]
      LOAD register[0xa:4] <- unique[0x0:4]
  0x00011188: 0xfe842583  lw x11, -24(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffe8:4]
      LOAD register[0xb:4] <- unique[0x0:4]
  0x0001118c: 0x00359593  slli x11, x11, 3
      INT_LEFT register[0xb:4] <- register[0xb:4], const[0x3:4]
  0x00011190: 0x00b50533  add x10, x10, x11
      INT_ADD register[0xa:4] <- register[0xa:4], register[0xb:4]
  0x00011194: 0x00452583  lw x11, 4(x10)
      INT_ADD unique[0x0:4] <- register[0xa:4], const[0x4:4]
      LOAD register[0xb:4] <- unique[0x0:4]
  0x00011198: 0xfec42503  lw x10, -20(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffec:4]
      LOAD register[0xa:4] <- unique[0x0:4]
  0x0001119c: 0x00b50533  add x10, x10, x11
      INT_ADD register[0xa:4] <- register[0xa:4], register[0xb:4]
  0x000111a0: 0xfea42623  sw x10, -20(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffec:4]
      STORE unique[0x0:4], register[0xa:4]
  0x000111a4: 0x0040006f  jal x0, 0x111a8
      BRANCH const[0x111a8:4]
  0x000111a8: 0xfe842503  lw x10, -24(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffe8:4]
      LOAD register[0xa:4] <- unique[0x0:4]
  0x000111ac: 0x00150513  addi x10, x10, 1
      INT_ADD register[0xa:4] <- register[0xa:4], const[0x1:4]
  0x000111b0: 0xfea42423  sw x10, -24(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffe8:4]
      STORE unique[0x0:4], register[0xa:4]
  0x000111b4: 0xfa1ff06f  jal x0, 0x11154
      BRANCH const[0x11154:4]
  0x000111b8: 0xfec42503  lw x10, -20(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffec:4]
      LOAD register[0xa:4] <- unique[0x0:4]
  0x000111bc: 0x01c12083  lw x1, 28(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x1c:4]
      LOAD unique[0x4:4] <- unique[0x0:4]
      COPY register[0x1:4] <- unique[0x4:4]
  0x000111c0: 0x01812403  lw x8, 24(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x18:4]
      LOAD unique[0x4:4] <- unique[0x0:4]
      COPY register[0x8:4] <- unique[0x4:4]
  0x000111c4: 0x02010113  addi x2, x2, 32
      INT_ADD register[0x2:4] <- register[0x2:4], const[0x20:4]
  0x000111c8: 0x00008067  jalr x0, 0(x1)
      INT_ADD unique[0x0:4] <- register[0x1:4], const[0x0:4]
      INT_AND unique[0x4:4] <- unique[0x0:4], const[0xfffffffe:4]
      RETURN unique[0x4:4]`,
  },

  /* ── 3: DISASSEMBLY & CFG ──────────────────────────────────────────────── */
  {
    id: "disasm",
    number: 3,
    name: "Disassembly & CFG",
    phase: "frontend",
    description: "Recursive disassembly partitions instructions into basic blocks. Each block has a terminator (return, jump, branch) and successor edges. main is a single straight-line block; parse_record has 6 blocks forming a loop.",
    githubDir: "tiny_dec/disasm",
    viewMode: "cfg",
    content: `  entry: 0x110e4
  order: 0x110e4
  block 0x110e4 term=return succ=[] calls=[0x1112c]
    0x000110e4: 0xfe010113  addi x2, x2, -32
      INT_ADD register[0x2:4] <- register[0x2:4], const[0xffffffe0:4]
    0x000110e8: 0x00112e23  sw x1, 28(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x1c:4]
      STORE unique[0x0:4], register[0x1:4]
    0x000110ec: 0x00812c23  sw x8, 24(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x18:4]
      STORE unique[0x0:4], register[0x8:4]
    0x000110f0: 0x02010413  addi x8, x2, 32
      INT_ADD register[0x8:4] <- register[0x2:4], const[0x20:4]
    0x000110f4: 0x01400513  addi x10, x0, 20
      INT_ADD register[0xa:4] <- const[0x0:4], const[0x14:4]
    0x000110f8: 0xfea42a23  sw x10, -12(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff4:4]
      STORE unique[0x0:4], register[0xa:4]
    0x000110fc: 0x00200593  addi x11, x0, 2
      INT_ADD register[0xb:4] <- const[0x0:4], const[0x2:4]
    0x00011100: 0xfeb42823  sw x11, -16(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff0:4]
      STORE unique[0x0:4], register[0xb:4]
    0x00011104: 0x00a00513  addi x10, x0, 10
      INT_ADD register[0xa:4] <- const[0x0:4], const[0xa:4]
    0x00011108: 0xfea42623  sw x10, -20(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffec:4]
      STORE unique[0x0:4], register[0xa:4]
    0x0001110c: 0x00100513  addi x10, x0, 1
      INT_ADD register[0xa:4] <- const[0x0:4], const[0x1:4]
    0x00011110: 0xfea42423  sw x10, -24(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffe8:4]
      STORE unique[0x0:4], register[0xa:4]
    0x00011114: 0xfe840513  addi x10, x8, -24
      INT_ADD register[0xa:4] <- register[0x8:4], const[0xffffffe8:4]
    0x00011118: 0x014000ef  jal x1, 0x1112c
      COPY register[0x1:4] <- const[0x1111c:4]
      CALL const[0x1112c:4]
    0x0001111c: 0x01c12083  lw x1, 28(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x1c:4]
      LOAD unique[0x4:4] <- unique[0x0:4]
      COPY register[0x1:4] <- unique[0x4:4]
    0x00011120: 0x01812403  lw x8, 24(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x18:4]
      LOAD unique[0x4:4] <- unique[0x0:4]
      COPY register[0x8:4] <- unique[0x4:4]
    0x00011124: 0x02010113  addi x2, x2, 32
      INT_ADD register[0x2:4] <- register[0x2:4], const[0x20:4]
    0x00011128: 0x00008067  jalr x0, 0(x1)
      INT_ADD unique[0x0:4] <- register[0x1:4], const[0x0:4]
      INT_AND unique[0x4:4] <- unique[0x0:4], const[0xfffffffe:4]
      RETURN unique[0x4:4]`,
    cfg: {
      main: {
        blocks: [
      {
        address: "0x110e4",
        ir: `    0x000110e4: 0xfe010113  addi x2, x2, -32
      INT_ADD register[0x2:4] <- register[0x2:4], const[0xffffffe0:4]
    0x000110e8: 0x00112e23  sw x1, 28(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x1c:4]
      STORE unique[0x0:4], register[0x1:4]
    0x000110ec: 0x00812c23  sw x8, 24(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x18:4]
      STORE unique[0x0:4], register[0x8:4]
    0x000110f0: 0x02010413  addi x8, x2, 32
      INT_ADD register[0x8:4] <- register[0x2:4], const[0x20:4]
    0x000110f4: 0x01400513  addi x10, x0, 20
      INT_ADD register[0xa:4] <- const[0x0:4], const[0x14:4]
    0x000110f8: 0xfea42a23  sw x10, -12(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff4:4]
      STORE unique[0x0:4], register[0xa:4]
    0x000110fc: 0x00200593  addi x11, x0, 2
      INT_ADD register[0xb:4] <- const[0x0:4], const[0x2:4]
    0x00011100: 0xfeb42823  sw x11, -16(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff0:4]
      STORE unique[0x0:4], register[0xb:4]
    0x00011104: 0x00a00513  addi x10, x0, 10
      INT_ADD register[0xa:4] <- const[0x0:4], const[0xa:4]
    0x00011108: 0xfea42623  sw x10, -20(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffec:4]
      STORE unique[0x0:4], register[0xa:4]
    0x0001110c: 0x00100513  addi x10, x0, 1
      INT_ADD register[0xa:4] <- const[0x0:4], const[0x1:4]
    0x00011110: 0xfea42423  sw x10, -24(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffe8:4]
      STORE unique[0x0:4], register[0xa:4]
    0x00011114: 0xfe840513  addi x10, x8, -24
      INT_ADD register[0xa:4] <- register[0x8:4], const[0xffffffe8:4]
    0x00011118: 0x014000ef  jal x1, 0x1112c
      COPY register[0x1:4] <- const[0x1111c:4]
      CALL const[0x1112c:4]
    0x0001111c: 0x01c12083  lw x1, 28(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x1c:4]
      LOAD unique[0x4:4] <- unique[0x0:4]
      COPY register[0x1:4] <- unique[0x4:4]
    0x00011120: 0x01812403  lw x8, 24(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x18:4]
      LOAD unique[0x4:4] <- unique[0x0:4]
      COPY register[0x8:4] <- unique[0x4:4]
    0x00011124: 0x02010113  addi x2, x2, 32
      INT_ADD register[0x2:4] <- register[0x2:4], const[0x20:4]
    0x00011128: 0x00008067  jalr x0, 0(x1)
      INT_ADD unique[0x0:4] <- register[0x1:4], const[0x0:4]
      INT_AND unique[0x4:4] <- unique[0x0:4], const[0xfffffffe:4]
      RETURN unique[0x4:4]`,
      },
        ],
        edges: [],
      },
      parse_record: {
        blocks: [
      {
        address: "0x1112c",
        ir: `        0x0001112c: 0xfe010113  addi x2, x2, -32
          INT_ADD register[0x2:4] <- register[0x2:4], const[0xffffffe0:4]
        0x00011130: 0x00112e23  sw x1, 28(x2)
          INT_ADD unique[0x0:4] <- register[0x2:4], const[0x1c:4]
          STORE unique[0x0:4], register[0x1:4]
        0x00011134: 0x00812c23  sw x8, 24(x2)
          INT_ADD unique[0x0:4] <- register[0x2:4], const[0x18:4]
          STORE unique[0x0:4], register[0x8:4]
        0x00011138: 0x02010413  addi x8, x2, 32
          INT_ADD register[0x8:4] <- register[0x2:4], const[0x20:4]
        0x0001113c: 0xfea42a23  sw x10, -12(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff4:4]
          STORE unique[0x0:4], register[0xa:4]
        0x00011140: 0xfeb42823  sw x11, -16(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff0:4]
          STORE unique[0x0:4], register[0xb:4]
        0x00011144: 0x00000513  addi x10, x0, 0
          COPY register[0xa:4] <- const[0x0:4]
        0x00011148: 0xfea42623  sw x10, -20(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffec:4]
          STORE unique[0x0:4], register[0xa:4]
        0x0001114c: 0xfea42423  sw x10, -24(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffe8:4]
          STORE unique[0x0:4], register[0xa:4]
        0x00011150: 0x0040006f  jal x0, 0x11154
          BRANCH const[0x11154:4]`,
      },
      {
        address: "0x11154",
        ir: `        0x00011154: 0xfe842503  lw x10, -24(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffe8:4]
          LOAD register[0xa:4] <- unique[0x0:4]
        0x00011158: 0xff042583  lw x11, -16(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff0:4]
          LOAD register[0xb:4] <- unique[0x0:4]
        0x0001115c: 0x04b55e63  bge x10, x11, 0x111b8
          INT_SLESS unique[0x0:1] <- register[0xa:4], register[0xb:4]
          BOOL_NEGATE unique[0x4:1] <- unique[0x0:1]
          CBRANCH const[0x111b8:4], unique[0x4:1]`,
      },
      {
        address: "0x111b8",
        ir: `        0x000111b8: 0xfec42503  lw x10, -20(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffec:4]
          LOAD register[0xa:4] <- unique[0x0:4]
        0x000111bc: 0x01c12083  lw x1, 28(x2)
          INT_ADD unique[0x0:4] <- register[0x2:4], const[0x1c:4]
          LOAD register[0x1:4] <- unique[0x0:4]
        0x000111c0: 0x01812403  lw x8, 24(x2)
          INT_ADD unique[0x0:4] <- register[0x2:4], const[0x18:4]
          LOAD register[0x8:4] <- unique[0x0:4]
        0x000111c4: 0x02010113  addi x2, x2, 32
          INT_ADD register[0x2:4] <- register[0x2:4], const[0x20:4]
        0x000111c8: 0x00008067  jalr x0, 0(x1)
          COPY unique[0x0:4] <- register[0x1:4]
          INT_AND unique[0x4:4] <- unique[0x0:4], const[0xfffffffe:4]
          RETURN unique[0x4:4]`,
      },
      {
        address: "0x11160",
        ir: `        0x00011160: 0x0040006f  jal x0, 0x11164
          BRANCH const[0x11164:4]`,
      },
      {
        address: "0x11164",
        ir: `        0x00011164: 0xff442503  lw x10, -12(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff4:4]
          LOAD register[0xa:4] <- unique[0x0:4]
        0x00011168: 0xfe842583  lw x11, -24(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffe8:4]
          LOAD register[0xb:4] <- unique[0x0:4]
        0x0001116c: 0x00359593  slli x11, x11, 3
          INT_LEFT register[0xb:4] <- register[0xb:4], const[0x3:4]
        0x00011170: 0x00b50533  add x10, x10, x11
          INT_ADD register[0xa:4] <- register[0xa:4], register[0xb:4]
        0x00011174: 0x00052583  lw x11, 0(x10)
          COPY unique[0x0:4] <- register[0xa:4]
          LOAD register[0xb:4] <- unique[0x0:4]
        0x00011178: 0xfec42503  lw x10, -20(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffec:4]
          LOAD register[0xa:4] <- unique[0x0:4]
        0x0001117c: 0x00b50533  add x10, x10, x11
          INT_ADD register[0xa:4] <- register[0xa:4], register[0xb:4]
        0x00011180: 0xfea42623  sw x10, -20(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffec:4]
          STORE unique[0x0:4], register[0xa:4]
        0x00011184: 0xff442503  lw x10, -12(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff4:4]
          LOAD register[0xa:4] <- unique[0x0:4]
        0x00011188: 0xfe842583  lw x11, -24(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffe8:4]
          LOAD register[0xb:4] <- unique[0x0:4]
        0x0001118c: 0x00359593  slli x11, x11, 3
          INT_LEFT register[0xb:4] <- register[0xb:4], const[0x3:4]
        0x00011190: 0x00b50533  add x10, x10, x11
          INT_ADD register[0xa:4] <- register[0xa:4], register[0xb:4]
        0x00011194: 0x00452583  lw x11, 4(x10)
          INT_ADD unique[0x0:4] <- register[0xa:4], const[0x4:4]
          LOAD register[0xb:4] <- unique[0x0:4]
        0x00011198: 0xfec42503  lw x10, -20(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffec:4]
          LOAD register[0xa:4] <- unique[0x0:4]
        0x0001119c: 0x00b50533  add x10, x10, x11
          INT_ADD register[0xa:4] <- register[0xa:4], register[0xb:4]
        0x000111a0: 0xfea42623  sw x10, -20(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffec:4]
          STORE unique[0x0:4], register[0xa:4]
        0x000111a4: 0x0040006f  jal x0, 0x111a8
          BRANCH const[0x111a8:4]`,
      },
      {
        address: "0x111a8",
        ir: `        0x000111a8: 0xfe842503  lw x10, -24(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffe8:4]
          LOAD register[0xa:4] <- unique[0x0:4]
        0x000111ac: 0x00150513  addi x10, x10, 1
          INT_ADD register[0xa:4] <- register[0xa:4], const[0x1:4]
        0x000111b0: 0xfea42423  sw x10, -24(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffe8:4]
          STORE unique[0x0:4], register[0xa:4]
        0x000111b4: 0xfa1ff06f  jal x0, 0x11154
          BRANCH const[0x11154:4]`,
      }
        ],
        edges: [
      { source: "0x1112c", target: "0x11154", type: "normal" },
      { source: "0x11154", target: "0x111b8", label: "taken: i >= n", type: "normal" },
      { source: "0x11154", target: "0x11160", label: "fall: i < n", type: "normal" },
      { source: "0x11160", target: "0x11164", type: "normal" },
      { source: "0x11164", target: "0x111a8", type: "normal" },
      { source: "0x111a8", target: "0x11154", label: "back edge", type: "back" },
        ],
      },
    },
  },

  /* ── 4: IR CONTAINERS ──────────────────────────────────────────────── */
  {
    id: "ir",
    number: 4,
    name: "IR Containers",
    phase: "frontend",
    description: "Functions are placed into IR containers with call-graph edges. We discover that main calls parse_record at address 0x11118. This container structure drives all subsequent interprocedural analysis.",
    githubDir: "tiny_dec/ir",
    viewMode: "cfg",
    content: `  root: 0x110e4
  order: 0x110e4, 0x1112c
  pending:
  invalidated:
  externals:
    <none>
  call_graph:
    0x110e4@0x11118 -> internal 0x1112c name=parse_record
  functions:
    function 0x110e4 name=main blocks=1 instructions=18 returns=[0x110e4] callees=[0x1112c]
    callsites:
      call 0x11118 block=0x110e4 -> 0x1112c name=parse_record
    function 0x1112c name=parse_record blocks=6 instructions=40 returns=[0x111b8] callees=[]
    callsites:
      <none>`,
    cfg: {
      main: {
        blocks: [
      {
        address: "0x110e4",
        ir: `    0x000110e4: 0xfe010113  addi x2, x2, -32
      INT_ADD register[0x2:4] <- register[0x2:4], const[0xffffffe0:4]
    0x000110e8: 0x00112e23  sw x1, 28(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x1c:4]
      STORE unique[0x0:4], register[0x1:4]
    0x000110ec: 0x00812c23  sw x8, 24(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x18:4]
      STORE unique[0x0:4], register[0x8:4]
    0x000110f0: 0x02010413  addi x8, x2, 32
      INT_ADD register[0x8:4] <- register[0x2:4], const[0x20:4]
    0x000110f4: 0x01400513  addi x10, x0, 20
      INT_ADD register[0xa:4] <- const[0x0:4], const[0x14:4]
    0x000110f8: 0xfea42a23  sw x10, -12(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff4:4]
      STORE unique[0x0:4], register[0xa:4]
    0x000110fc: 0x00200593  addi x11, x0, 2
      INT_ADD register[0xb:4] <- const[0x0:4], const[0x2:4]
    0x00011100: 0xfeb42823  sw x11, -16(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff0:4]
      STORE unique[0x0:4], register[0xb:4]
    0x00011104: 0x00a00513  addi x10, x0, 10
      INT_ADD register[0xa:4] <- const[0x0:4], const[0xa:4]
    0x00011108: 0xfea42623  sw x10, -20(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffec:4]
      STORE unique[0x0:4], register[0xa:4]
    0x0001110c: 0x00100513  addi x10, x0, 1
      INT_ADD register[0xa:4] <- const[0x0:4], const[0x1:4]
    0x00011110: 0xfea42423  sw x10, -24(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffe8:4]
      STORE unique[0x0:4], register[0xa:4]
    0x00011114: 0xfe840513  addi x10, x8, -24
      INT_ADD register[0xa:4] <- register[0x8:4], const[0xffffffe8:4]
    0x00011118: 0x014000ef  jal x1, 0x1112c
      COPY register[0x1:4] <- const[0x1111c:4]
      CALL const[0x1112c:4]
    0x0001111c: 0x01c12083  lw x1, 28(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x1c:4]
      LOAD unique[0x4:4] <- unique[0x0:4]
      COPY register[0x1:4] <- unique[0x4:4]
    0x00011120: 0x01812403  lw x8, 24(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x18:4]
      LOAD unique[0x4:4] <- unique[0x0:4]
      COPY register[0x8:4] <- unique[0x4:4]
    0x00011124: 0x02010113  addi x2, x2, 32
      INT_ADD register[0x2:4] <- register[0x2:4], const[0x20:4]
    0x00011128: 0x00008067  jalr x0, 0(x1)
      INT_ADD unique[0x0:4] <- register[0x1:4], const[0x0:4]
      INT_AND unique[0x4:4] <- unique[0x0:4], const[0xfffffffe:4]
      RETURN unique[0x4:4]`,
      },
        ],
        edges: [],
      },
      parse_record: {
        blocks: [
      {
        address: "0x1112c",
        ir: `        0x0001112c: 0xfe010113  addi x2, x2, -32
          INT_ADD register[0x2:4] <- register[0x2:4], const[0xffffffe0:4]
        0x00011130: 0x00112e23  sw x1, 28(x2)
          INT_ADD unique[0x0:4] <- register[0x2:4], const[0x1c:4]
          STORE unique[0x0:4], register[0x1:4]
        0x00011134: 0x00812c23  sw x8, 24(x2)
          INT_ADD unique[0x0:4] <- register[0x2:4], const[0x18:4]
          STORE unique[0x0:4], register[0x8:4]
        0x00011138: 0x02010413  addi x8, x2, 32
          INT_ADD register[0x8:4] <- register[0x2:4], const[0x20:4]
        0x0001113c: 0xfea42a23  sw x10, -12(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff4:4]
          STORE unique[0x0:4], register[0xa:4]
        0x00011140: 0xfeb42823  sw x11, -16(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff0:4]
          STORE unique[0x0:4], register[0xb:4]
        0x00011144: 0x00000513  addi x10, x0, 0
          COPY register[0xa:4] <- const[0x0:4]
        0x00011148: 0xfea42623  sw x10, -20(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffec:4]
          STORE unique[0x0:4], register[0xa:4]
        0x0001114c: 0xfea42423  sw x10, -24(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffe8:4]
          STORE unique[0x0:4], register[0xa:4]
        0x00011150: 0x0040006f  jal x0, 0x11154
          BRANCH const[0x11154:4]`,
      },
      {
        address: "0x11154",
        ir: `        0x00011154: 0xfe842503  lw x10, -24(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffe8:4]
          LOAD register[0xa:4] <- unique[0x0:4]
        0x00011158: 0xff042583  lw x11, -16(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff0:4]
          LOAD register[0xb:4] <- unique[0x0:4]
        0x0001115c: 0x04b55e63  bge x10, x11, 0x111b8
          INT_SLESS unique[0x0:1] <- register[0xa:4], register[0xb:4]
          BOOL_NEGATE unique[0x4:1] <- unique[0x0:1]
          CBRANCH const[0x111b8:4], unique[0x4:1]`,
      },
      {
        address: "0x111b8",
        ir: `        0x000111b8: 0xfec42503  lw x10, -20(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffec:4]
          LOAD register[0xa:4] <- unique[0x0:4]
        0x000111bc: 0x01c12083  lw x1, 28(x2)
          INT_ADD unique[0x0:4] <- register[0x2:4], const[0x1c:4]
          LOAD register[0x1:4] <- unique[0x0:4]
        0x000111c0: 0x01812403  lw x8, 24(x2)
          INT_ADD unique[0x0:4] <- register[0x2:4], const[0x18:4]
          LOAD register[0x8:4] <- unique[0x0:4]
        0x000111c4: 0x02010113  addi x2, x2, 32
          INT_ADD register[0x2:4] <- register[0x2:4], const[0x20:4]
        0x000111c8: 0x00008067  jalr x0, 0(x1)
          COPY unique[0x0:4] <- register[0x1:4]
          INT_AND unique[0x4:4] <- unique[0x0:4], const[0xfffffffe:4]
          RETURN unique[0x4:4]`,
      },
      {
        address: "0x11160",
        ir: `        0x00011160: 0x0040006f  jal x0, 0x11164
          BRANCH const[0x11164:4]`,
      },
      {
        address: "0x11164",
        ir: `        0x00011164: 0xff442503  lw x10, -12(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff4:4]
          LOAD register[0xa:4] <- unique[0x0:4]
        0x00011168: 0xfe842583  lw x11, -24(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffe8:4]
          LOAD register[0xb:4] <- unique[0x0:4]
        0x0001116c: 0x00359593  slli x11, x11, 3
          INT_LEFT register[0xb:4] <- register[0xb:4], const[0x3:4]
        0x00011170: 0x00b50533  add x10, x10, x11
          INT_ADD register[0xa:4] <- register[0xa:4], register[0xb:4]
        0x00011174: 0x00052583  lw x11, 0(x10)
          COPY unique[0x0:4] <- register[0xa:4]
          LOAD register[0xb:4] <- unique[0x0:4]
        0x00011178: 0xfec42503  lw x10, -20(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffec:4]
          LOAD register[0xa:4] <- unique[0x0:4]
        0x0001117c: 0x00b50533  add x10, x10, x11
          INT_ADD register[0xa:4] <- register[0xa:4], register[0xb:4]
        0x00011180: 0xfea42623  sw x10, -20(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffec:4]
          STORE unique[0x0:4], register[0xa:4]
        0x00011184: 0xff442503  lw x10, -12(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff4:4]
          LOAD register[0xa:4] <- unique[0x0:4]
        0x00011188: 0xfe842583  lw x11, -24(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffe8:4]
          LOAD register[0xb:4] <- unique[0x0:4]
        0x0001118c: 0x00359593  slli x11, x11, 3
          INT_LEFT register[0xb:4] <- register[0xb:4], const[0x3:4]
        0x00011190: 0x00b50533  add x10, x10, x11
          INT_ADD register[0xa:4] <- register[0xa:4], register[0xb:4]
        0x00011194: 0x00452583  lw x11, 4(x10)
          INT_ADD unique[0x0:4] <- register[0xa:4], const[0x4:4]
          LOAD register[0xb:4] <- unique[0x0:4]
        0x00011198: 0xfec42503  lw x10, -20(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffec:4]
          LOAD register[0xa:4] <- unique[0x0:4]
        0x0001119c: 0x00b50533  add x10, x10, x11
          INT_ADD register[0xa:4] <- register[0xa:4], register[0xb:4]
        0x000111a0: 0xfea42623  sw x10, -20(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffec:4]
          STORE unique[0x0:4], register[0xa:4]
        0x000111a4: 0x0040006f  jal x0, 0x111a8
          BRANCH const[0x111a8:4]`,
      },
      {
        address: "0x111a8",
        ir: `        0x000111a8: 0xfe842503  lw x10, -24(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffe8:4]
          LOAD register[0xa:4] <- unique[0x0:4]
        0x000111ac: 0x00150513  addi x10, x10, 1
          INT_ADD register[0xa:4] <- register[0xa:4], const[0x1:4]
        0x000111b0: 0xfea42423  sw x10, -24(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffe8:4]
          STORE unique[0x0:4], register[0xa:4]
        0x000111b4: 0xfa1ff06f  jal x0, 0x11154
          BRANCH const[0x11154:4]`,
      }
        ],
        edges: [
      { source: "0x1112c", target: "0x11154", type: "normal" },
      { source: "0x11154", target: "0x111b8", label: "taken: i >= n", type: "normal" },
      { source: "0x11154", target: "0x11160", label: "fall: i < n", type: "normal" },
      { source: "0x11160", target: "0x11164", type: "normal" },
      { source: "0x11164", target: "0x111a8", type: "normal" },
      { source: "0x111a8", target: "0x11154", label: "back edge", type: "back" },
        ],
      },
    },
  },

  /* ── 5: SIMPLIFY ──────────────────────────────────────────────── */
  {
    id: "simplify",
    number: 5,
    name: "Simplify",
    phase: "analysis",
    description: "Canonical simplification rewrites redundant operations. addi x10, x0, 20 (add zero to 20) becomes COPY x10 <- const[0x14]. The instruction count stays the same but operations per instruction decrease.",
    githubDir: "tiny_dec/analysis/simplify",
    viewMode: "cfg",
    content: `  root: 0x110e4
  order: 0x110e4, 0x1112c
  pending:
  invalidated:
  externals:
    <none>
  call_graph:
    0x110e4@0x11118 -> internal 0x1112c name=parse_record
  functions:
    function 0x110e4 name=main blocks=1 instructions=18 ops=29 returns=[0x110e4] callees=[0x1112c]
    callsites:
      call 0x11118 block=0x110e4 -> 0x1112c name=parse_record
    blocks:
      block 0x110e4 term=return succ=[] calls=[0x1112c]
        0x000110e4: 0xfe010113  addi x2, x2, -32
          INT_ADD register[0x2:4] <- register[0x2:4], const[0xffffffe0:4]
        0x000110e8: 0x00112e23  sw x1, 28(x2)
          INT_ADD unique[0x0:4] <- register[0x2:4], const[0x1c:4]
          STORE unique[0x0:4], register[0x1:4]
        0x000110ec: 0x00812c23  sw x8, 24(x2)
          INT_ADD unique[0x0:4] <- register[0x2:4], const[0x18:4]
          STORE unique[0x0:4], register[0x8:4]
        0x000110f0: 0x02010413  addi x8, x2, 32
          INT_ADD register[0x8:4] <- register[0x2:4], const[0x20:4]
        0x000110f4: 0x01400513  addi x10, x0, 20
          COPY register[0xa:4] <- const[0x14:4]
        0x000110f8: 0xfea42a23  sw x10, -12(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff4:4]
          STORE unique[0x0:4], register[0xa:4]
        0x000110fc: 0x00200593  addi x11, x0, 2
          COPY register[0xb:4] <- const[0x2:4]
        0x00011100: 0xfeb42823  sw x11, -16(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff0:4]
          STORE unique[0x0:4], register[0xb:4]
        0x00011104: 0x00a00513  addi x10, x0, 10
          COPY register[0xa:4] <- const[0xa:4]
        0x00011108: 0xfea42623  sw x10, -20(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffec:4]
          STORE unique[0x0:4], register[0xa:4]
        0x0001110c: 0x00100513  addi x10, x0, 1
          COPY register[0xa:4] <- const[0x1:4]
        0x00011110: 0xfea42423  sw x10, -24(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffe8:4]
          STORE unique[0x0:4], register[0xa:4]
        0x00011114: 0xfe840513  addi x10, x8, -24
          INT_ADD register[0xa:4] <- register[0x8:4], const[0xffffffe8:4]
        0x00011118: 0x014000ef  jal x1, 0x1112c
          COPY register[0x1:4] <- const[0x1111c:4]
          CALL const[0x1112c:4]
        0x0001111c: 0x01c12083  lw x1, 28(x2)
          INT_ADD unique[0x0:4] <- register[0x2:4], const[0x1c:4]
          LOAD register[0x1:4] <- unique[0x0:4]
        0x00011120: 0x01812403  lw x8, 24(x2)
          INT_ADD unique[0x0:4] <- register[0x2:4], const[0x18:4]
          LOAD register[0x8:4] <- unique[0x0:4]
        0x00011124: 0x02010113  addi x2, x2, 32
          INT_ADD register[0x2:4] <- register[0x2:4], const[0x20:4]
        0x00011128: 0x00008067  jalr x0, 0(x1)
          COPY unique[0x0:4] <- register[0x1:4]
          INT_AND unique[0x4:4] <- unique[0x0:4], const[0xfffffffe:4]
          RETURN unique[0x4:4]
    function 0x1112c name=parse_record blocks=6 instructions=40 ops=67 returns=[0x111b8] callees=[]
    callsites:
      <none>
    blocks:
      block 0x1112c term=jump succ=[jump:0x11154]
        0x0001112c: 0xfe010113  addi x2, x2, -32
          INT_ADD register[0x2:4] <- register[0x2:4], const[0xffffffe0:4]
        0x00011130: 0x00112e23  sw x1, 28(x2)
          INT_ADD unique[0x0:4] <- register[0x2:4], const[0x1c:4]
          STORE unique[0x0:4], register[0x1:4]
        0x00011134: 0x00812c23  sw x8, 24(x2)
          INT_ADD unique[0x0:4] <- register[0x2:4], const[0x18:4]
          STORE unique[0x0:4], register[0x8:4]
        0x00011138: 0x02010413  addi x8, x2, 32
          INT_ADD register[0x8:4] <- register[0x2:4], const[0x20:4]
        0x0001113c: 0xfea42a23  sw x10, -12(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff4:4]
          STORE unique[0x0:4], register[0xa:4]
        0x00011140: 0xfeb42823  sw x11, -16(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff0:4]
          STORE unique[0x0:4], register[0xb:4]
        0x00011144: 0x00000513  addi x10, x0, 0
          COPY register[0xa:4] <- const[0x0:4]
        0x00011148: 0xfea42623  sw x10, -20(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffec:4]
          STORE unique[0x0:4], register[0xa:4]
        0x0001114c: 0xfea42423  sw x10, -24(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffe8:4]
          STORE unique[0x0:4], register[0xa:4]
        0x00011150: 0x0040006f  jal x0, 0x11154
          BRANCH const[0x11154:4]
      block 0x11154 term=branch succ=[branch_taken:0x111b8, fallthrough:0x11160]
        0x00011154: 0xfe842503  lw x10, -24(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffe8:4]
          LOAD register[0xa:4] <- unique[0x0:4]
        0x00011158: 0xff042583  lw x11, -16(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff0:4]
          LOAD register[0xb:4] <- unique[0x0:4]
        0x0001115c: 0x04b55e63  bge x10, x11, 0x111b8
          INT_SLESS unique[0x0:1] <- register[0xa:4], register[0xb:4]
          BOOL_NEGATE unique[0x4:1] <- unique[0x0:1]
          CBRANCH const[0x111b8:4], unique[0x4:1]
      block 0x111b8 term=return succ=[]
        0x000111b8: 0xfec42503  lw x10, -20(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffec:4]
          LOAD register[0xa:4] <- unique[0x0:4]
        0x000111bc: 0x01c12083  lw x1, 28(x2)
          INT_ADD unique[0x0:4] <- register[0x2:4], const[0x1c:4]
          LOAD register[0x1:4] <- unique[0x0:4]
        0x000111c0: 0x01812403  lw x8, 24(x2)
          INT_ADD unique[0x0:4] <- register[0x2:4], const[0x18:4]
          LOAD register[0x8:4] <- unique[0x0:4]
        0x000111c4: 0x02010113  addi x2, x2, 32
          INT_ADD register[0x2:4] <- register[0x2:4], const[0x20:4]
        0x000111c8: 0x00008067  jalr x0, 0(x1)
          COPY unique[0x0:4] <- register[0x1:4]
          INT_AND unique[0x4:4] <- unique[0x0:4], const[0xfffffffe:4]
          RETURN unique[0x4:4]
      block 0x11160 term=jump succ=[jump:0x11164]
        0x00011160: 0x0040006f  jal x0, 0x11164
          BRANCH const[0x11164:4]
      block 0x11164 term=jump succ=[jump:0x111a8]
        0x00011164: 0xff442503  lw x10, -12(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff4:4]
          LOAD register[0xa:4] <- unique[0x0:4]
        0x00011168: 0xfe842583  lw x11, -24(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffe8:4]
          LOAD register[0xb:4] <- unique[0x0:4]
        0x0001116c: 0x00359593  slli x11, x11, 3
          INT_LEFT register[0xb:4] <- register[0xb:4], const[0x3:4]
        0x00011170: 0x00b50533  add x10, x10, x11
          INT_ADD register[0xa:4] <- register[0xa:4], register[0xb:4]
        0x00011174: 0x00052583  lw x11, 0(x10)
          COPY unique[0x0:4] <- register[0xa:4]
          LOAD register[0xb:4] <- unique[0x0:4]
        0x00011178: 0xfec42503  lw x10, -20(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffec:4]
          LOAD register[0xa:4] <- unique[0x0:4]
        0x0001117c: 0x00b50533  add x10, x10, x11
          INT_ADD register[0xa:4] <- register[0xa:4], register[0xb:4]
        0x00011180: 0xfea42623  sw x10, -20(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffec:4]
          STORE unique[0x0:4], register[0xa:4]
        0x00011184: 0xff442503  lw x10, -12(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff4:4]
          LOAD register[0xa:4] <- unique[0x0:4]
        0x00011188: 0xfe842583  lw x11, -24(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffe8:4]
          LOAD register[0xb:4] <- unique[0x0:4]
        0x0001118c: 0x00359593  slli x11, x11, 3
          INT_LEFT register[0xb:4] <- register[0xb:4], const[0x3:4]
        0x00011190: 0x00b50533  add x10, x10, x11
          INT_ADD register[0xa:4] <- register[0xa:4], register[0xb:4]
        0x00011194: 0x00452583  lw x11, 4(x10)
          INT_ADD unique[0x0:4] <- register[0xa:4], const[0x4:4]
          LOAD register[0xb:4] <- unique[0x0:4]
        0x00011198: 0xfec42503  lw x10, -20(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffec:4]
          LOAD register[0xa:4] <- unique[0x0:4]
        0x0001119c: 0x00b50533  add x10, x10, x11
          INT_ADD register[0xa:4] <- register[0xa:4], register[0xb:4]
        0x000111a0: 0xfea42623  sw x10, -20(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffec:4]
          STORE unique[0x0:4], register[0xa:4]
        0x000111a4: 0x0040006f  jal x0, 0x111a8
          BRANCH const[0x111a8:4]
      block 0x111a8 term=jump succ=[jump:0x11154]
        0x000111a8: 0xfe842503  lw x10, -24(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffe8:4]
          LOAD register[0xa:4] <- unique[0x0:4]
        0x000111ac: 0x00150513  addi x10, x10, 1
          INT_ADD register[0xa:4] <- register[0xa:4], const[0x1:4]
        0x000111b0: 0xfea42423  sw x10, -24(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffe8:4]
          STORE unique[0x0:4], register[0xa:4]
        0x000111b4: 0xfa1ff06f  jal x0, 0x11154
          BRANCH const[0x11154:4]`,
    cfg: {
      main: {
        blocks: [
      {
        address: "0x110e4",
        ir: `    0x000110e4: 0xfe010113  addi x2, x2, -32
      INT_ADD register[0x2:4] <- register[0x2:4], const[0xffffffe0:4]
    0x000110e8: 0x00112e23  sw x1, 28(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x1c:4]
      STORE unique[0x0:4], register[0x1:4]
    0x000110ec: 0x00812c23  sw x8, 24(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x18:4]
      STORE unique[0x0:4], register[0x8:4]
    0x000110f0: 0x02010413  addi x8, x2, 32
      INT_ADD register[0x8:4] <- register[0x2:4], const[0x20:4]
    0x000110f4: 0x01400513  addi x10, x0, 20
      COPY register[0xa:4] <- const[0x14:4]
    0x000110f8: 0xfea42a23  sw x10, -12(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff4:4]
      STORE unique[0x0:4], register[0xa:4]
    0x000110fc: 0x00200593  addi x11, x0, 2
      COPY register[0xb:4] <- const[0x2:4]
    0x00011100: 0xfeb42823  sw x11, -16(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff0:4]
      STORE unique[0x0:4], register[0xb:4]
    0x00011104: 0x00a00513  addi x10, x0, 10
      COPY register[0xa:4] <- const[0xa:4]
    0x00011108: 0xfea42623  sw x10, -20(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffec:4]
      STORE unique[0x0:4], register[0xa:4]
    0x0001110c: 0x00100513  addi x10, x0, 1
      COPY register[0xa:4] <- const[0x1:4]
    0x00011110: 0xfea42423  sw x10, -24(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffe8:4]
      STORE unique[0x0:4], register[0xa:4]
    0x00011114: 0xfe840513  addi x10, x8, -24
      INT_ADD register[0xa:4] <- register[0x8:4], const[0xffffffe8:4]
    0x00011118: 0x014000ef  jal x1, 0x1112c
      COPY register[0x1:4] <- const[0x1111c:4]
      CALL const[0x1112c:4]
    0x0001111c: 0x01c12083  lw x1, 28(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x1c:4]
      LOAD unique[0x4:4] <- unique[0x0:4]
      COPY register[0x1:4] <- unique[0x4:4]
    0x00011120: 0x01812403  lw x8, 24(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x18:4]
      LOAD unique[0x4:4] <- unique[0x0:4]
      COPY register[0x8:4] <- unique[0x4:4]
    0x00011124: 0x02010113  addi x2, x2, 32
      INT_ADD register[0x2:4] <- register[0x2:4], const[0x20:4]
    0x00011128: 0x00008067  jalr x0, 0(x1)
      COPY unique[0x0:4] <- register[0x1:4]
      INT_AND unique[0x4:4] <- unique[0x0:4], const[0xfffffffe:4]
      RETURN unique[0x4:4]`,
      },
        ],
        edges: [],
      },
      parse_record: {
        blocks: [
      {
        address: "0x1112c",
        ir: `        0x0001112c: 0xfe010113  addi x2, x2, -32
          INT_ADD register[0x2:4] <- register[0x2:4], const[0xffffffe0:4]
        0x00011130: 0x00112e23  sw x1, 28(x2)
          INT_ADD unique[0x0:4] <- register[0x2:4], const[0x1c:4]
          STORE unique[0x0:4], register[0x1:4]
        0x00011134: 0x00812c23  sw x8, 24(x2)
          INT_ADD unique[0x0:4] <- register[0x2:4], const[0x18:4]
          STORE unique[0x0:4], register[0x8:4]
        0x00011138: 0x02010413  addi x8, x2, 32
          INT_ADD register[0x8:4] <- register[0x2:4], const[0x20:4]
        0x0001113c: 0xfea42a23  sw x10, -12(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff4:4]
          STORE unique[0x0:4], register[0xa:4]
        0x00011140: 0xfeb42823  sw x11, -16(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff0:4]
          STORE unique[0x0:4], register[0xb:4]
        0x00011144: 0x00000513  addi x10, x0, 0
          COPY register[0xa:4] <- const[0x0:4]
        0x00011148: 0xfea42623  sw x10, -20(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffec:4]
          STORE unique[0x0:4], register[0xa:4]
        0x0001114c: 0xfea42423  sw x10, -24(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffe8:4]
          STORE unique[0x0:4], register[0xa:4]
        0x00011150: 0x0040006f  jal x0, 0x11154
          BRANCH const[0x11154:4]`,
      },
      {
        address: "0x11154",
        ir: `        0x00011154: 0xfe842503  lw x10, -24(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffe8:4]
          LOAD register[0xa:4] <- unique[0x0:4]
        0x00011158: 0xff042583  lw x11, -16(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff0:4]
          LOAD register[0xb:4] <- unique[0x0:4]
        0x0001115c: 0x04b55e63  bge x10, x11, 0x111b8
          INT_SLESS unique[0x0:1] <- register[0xa:4], register[0xb:4]
          BOOL_NEGATE unique[0x4:1] <- unique[0x0:1]
          CBRANCH const[0x111b8:4], unique[0x4:1]`,
      },
      {
        address: "0x111b8",
        ir: `        0x000111b8: 0xfec42503  lw x10, -20(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffec:4]
          LOAD register[0xa:4] <- unique[0x0:4]
        0x000111bc: 0x01c12083  lw x1, 28(x2)
          INT_ADD unique[0x0:4] <- register[0x2:4], const[0x1c:4]
          LOAD register[0x1:4] <- unique[0x0:4]
        0x000111c0: 0x01812403  lw x8, 24(x2)
          INT_ADD unique[0x0:4] <- register[0x2:4], const[0x18:4]
          LOAD register[0x8:4] <- unique[0x0:4]
        0x000111c4: 0x02010113  addi x2, x2, 32
          INT_ADD register[0x2:4] <- register[0x2:4], const[0x20:4]
        0x000111c8: 0x00008067  jalr x0, 0(x1)
          COPY unique[0x0:4] <- register[0x1:4]
          INT_AND unique[0x4:4] <- unique[0x0:4], const[0xfffffffe:4]
          RETURN unique[0x4:4]`,
      },
      {
        address: "0x11160",
        ir: `        0x00011160: 0x0040006f  jal x0, 0x11164
          BRANCH const[0x11164:4]`,
      },
      {
        address: "0x11164",
        ir: `        0x00011164: 0xff442503  lw x10, -12(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff4:4]
          LOAD register[0xa:4] <- unique[0x0:4]
        0x00011168: 0xfe842583  lw x11, -24(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffe8:4]
          LOAD register[0xb:4] <- unique[0x0:4]
        0x0001116c: 0x00359593  slli x11, x11, 3
          INT_LEFT register[0xb:4] <- register[0xb:4], const[0x3:4]
        0x00011170: 0x00b50533  add x10, x10, x11
          INT_ADD register[0xa:4] <- register[0xa:4], register[0xb:4]
        0x00011174: 0x00052583  lw x11, 0(x10)
          COPY unique[0x0:4] <- register[0xa:4]
          LOAD register[0xb:4] <- unique[0x0:4]
        0x00011178: 0xfec42503  lw x10, -20(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffec:4]
          LOAD register[0xa:4] <- unique[0x0:4]
        0x0001117c: 0x00b50533  add x10, x10, x11
          INT_ADD register[0xa:4] <- register[0xa:4], register[0xb:4]
        0x00011180: 0xfea42623  sw x10, -20(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffec:4]
          STORE unique[0x0:4], register[0xa:4]
        0x00011184: 0xff442503  lw x10, -12(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff4:4]
          LOAD register[0xa:4] <- unique[0x0:4]
        0x00011188: 0xfe842583  lw x11, -24(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffe8:4]
          LOAD register[0xb:4] <- unique[0x0:4]
        0x0001118c: 0x00359593  slli x11, x11, 3
          INT_LEFT register[0xb:4] <- register[0xb:4], const[0x3:4]
        0x00011190: 0x00b50533  add x10, x10, x11
          INT_ADD register[0xa:4] <- register[0xa:4], register[0xb:4]
        0x00011194: 0x00452583  lw x11, 4(x10)
          INT_ADD unique[0x0:4] <- register[0xa:4], const[0x4:4]
          LOAD register[0xb:4] <- unique[0x0:4]
        0x00011198: 0xfec42503  lw x10, -20(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffec:4]
          LOAD register[0xa:4] <- unique[0x0:4]
        0x0001119c: 0x00b50533  add x10, x10, x11
          INT_ADD register[0xa:4] <- register[0xa:4], register[0xb:4]
        0x000111a0: 0xfea42623  sw x10, -20(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffec:4]
          STORE unique[0x0:4], register[0xa:4]
        0x000111a4: 0x0040006f  jal x0, 0x111a8
          BRANCH const[0x111a8:4]`,
      },
      {
        address: "0x111a8",
        ir: `        0x000111a8: 0xfe842503  lw x10, -24(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffe8:4]
          LOAD register[0xa:4] <- unique[0x0:4]
        0x000111ac: 0x00150513  addi x10, x10, 1
          INT_ADD register[0xa:4] <- register[0xa:4], const[0x1:4]
        0x000111b0: 0xfea42423  sw x10, -24(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffe8:4]
          STORE unique[0x0:4], register[0xa:4]
        0x000111b4: 0xfa1ff06f  jal x0, 0x11154
          BRANCH const[0x11154:4]`,
      }
        ],
        edges: [
      { source: "0x1112c", target: "0x11154", type: "normal" },
      { source: "0x11154", target: "0x111b8", label: "taken: i >= n", type: "normal" },
      { source: "0x11154", target: "0x11160", label: "fall: i < n", type: "normal" },
      { source: "0x11160", target: "0x11164", type: "normal" },
      { source: "0x11164", target: "0x111a8", type: "normal" },
      { source: "0x111a8", target: "0x11154", label: "back edge", type: "back" },
        ],
      },
    },
  },

  /* ── 6: DATAFLOW ANALYSIS ──────────────────────────────────────────────── */
  {
    id: "dataflow",
    number: 6,
    name: "Dataflow Analysis",
    phase: "analysis",
    description: "Intraprocedural dataflow propagates known facts. The entry block of parse_record has out=[x10=0x0] because it sets x10 to zero before jumping to the loop header. Most blocks have empty in/out sets for this small program.",
    githubDir: "tiny_dec/analysis/dataflow",
    viewMode: "cfg",
    content: `  root: 0x110e4
  order: 0x110e4, 0x1112c
  pending:
  invalidated:
  externals:
    <none>
  call_graph:
    0x110e4@0x11118 -> internal 0x1112c name=parse_record
  functions:
    function 0x110e4 name=main blocks=1 recovered=0
    recovered_targets:
      <none>
    blocks:
      block 0x110e4 term=return succ=[] calls=[0x1112c] in=[<empty>] out=[<empty>]
    function 0x1112c name=parse_record blocks=6 recovered=0
    recovered_targets:
      <none>
    blocks:
      block 0x1112c term=jump succ=[jump:0x11154] in=[<empty>] out=[x10=0x0]
      block 0x11154 term=branch succ=[branch_taken:0x111b8, fallthrough:0x11160] in=[<empty>] out=[<empty>]
      block 0x111b8 term=return succ=[] in=[<empty>] out=[<empty>]
      block 0x11160 term=jump succ=[jump:0x11164] in=[<empty>] out=[<empty>]
      block 0x11164 term=jump succ=[jump:0x111a8] in=[<empty>] out=[<empty>]
      block 0x111a8 term=jump succ=[jump:0x11154] in=[<empty>] out=[<empty>]`,
    cfg: {
      main: {
        blocks: [
      {
        address: "0x110e4",
        ir: `    0x000110e4: 0xfe010113  addi x2, x2, -32
      INT_ADD register[0x2:4] <- register[0x2:4], const[0xffffffe0:4]
    0x000110e8: 0x00112e23  sw x1, 28(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x1c:4]
      STORE unique[0x0:4], register[0x1:4]
    0x000110ec: 0x00812c23  sw x8, 24(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x18:4]
      STORE unique[0x0:4], register[0x8:4]
    0x000110f0: 0x02010413  addi x8, x2, 32
      INT_ADD register[0x8:4] <- register[0x2:4], const[0x20:4]
    0x000110f4: 0x01400513  addi x10, x0, 20
      COPY register[0xa:4] <- const[0x14:4]
    0x000110f8: 0xfea42a23  sw x10, -12(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff4:4]
      STORE unique[0x0:4], register[0xa:4]
    0x000110fc: 0x00200593  addi x11, x0, 2
      COPY register[0xb:4] <- const[0x2:4]
    0x00011100: 0xfeb42823  sw x11, -16(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff0:4]
      STORE unique[0x0:4], register[0xb:4]
    0x00011104: 0x00a00513  addi x10, x0, 10
      COPY register[0xa:4] <- const[0xa:4]
    0x00011108: 0xfea42623  sw x10, -20(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffec:4]
      STORE unique[0x0:4], register[0xa:4]
    0x0001110c: 0x00100513  addi x10, x0, 1
      COPY register[0xa:4] <- const[0x1:4]
    0x00011110: 0xfea42423  sw x10, -24(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffe8:4]
      STORE unique[0x0:4], register[0xa:4]
    0x00011114: 0xfe840513  addi x10, x8, -24
      INT_ADD register[0xa:4] <- register[0x8:4], const[0xffffffe8:4]
    0x00011118: 0x014000ef  jal x1, 0x1112c
      COPY register[0x1:4] <- const[0x1111c:4]
      CALL const[0x1112c:4]
    0x0001111c: 0x01c12083  lw x1, 28(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x1c:4]
      LOAD unique[0x4:4] <- unique[0x0:4]
      COPY register[0x1:4] <- unique[0x4:4]
    0x00011120: 0x01812403  lw x8, 24(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x18:4]
      LOAD unique[0x4:4] <- unique[0x0:4]
      COPY register[0x8:4] <- unique[0x4:4]
    0x00011124: 0x02010113  addi x2, x2, 32
      INT_ADD register[0x2:4] <- register[0x2:4], const[0x20:4]
    0x00011128: 0x00008067  jalr x0, 0(x1)
      COPY unique[0x0:4] <- register[0x1:4]
      INT_AND unique[0x4:4] <- unique[0x0:4], const[0xfffffffe:4]
      RETURN unique[0x4:4]`,
      },
        ],
        edges: [],
      },
      parse_record: {
        blocks: [
      {
        address: "0x1112c",
        ir: `        0x0001112c: 0xfe010113  addi x2, x2, -32
          INT_ADD register[0x2:4] <- register[0x2:4], const[0xffffffe0:4]
        0x00011130: 0x00112e23  sw x1, 28(x2)
          INT_ADD unique[0x0:4] <- register[0x2:4], const[0x1c:4]
          STORE unique[0x0:4], register[0x1:4]
        0x00011134: 0x00812c23  sw x8, 24(x2)
          INT_ADD unique[0x0:4] <- register[0x2:4], const[0x18:4]
          STORE unique[0x0:4], register[0x8:4]
        0x00011138: 0x02010413  addi x8, x2, 32
          INT_ADD register[0x8:4] <- register[0x2:4], const[0x20:4]
        0x0001113c: 0xfea42a23  sw x10, -12(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff4:4]
          STORE unique[0x0:4], register[0xa:4]
        0x00011140: 0xfeb42823  sw x11, -16(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff0:4]
          STORE unique[0x0:4], register[0xb:4]
        0x00011144: 0x00000513  addi x10, x0, 0
          COPY register[0xa:4] <- const[0x0:4]
        0x00011148: 0xfea42623  sw x10, -20(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffec:4]
          STORE unique[0x0:4], register[0xa:4]
        0x0001114c: 0xfea42423  sw x10, -24(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffe8:4]
          STORE unique[0x0:4], register[0xa:4]
        0x00011150: 0x0040006f  jal x0, 0x11154
          BRANCH const[0x11154:4]`,
      },
      {
        address: "0x11154",
        ir: `        0x00011154: 0xfe842503  lw x10, -24(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffe8:4]
          LOAD register[0xa:4] <- unique[0x0:4]
        0x00011158: 0xff042583  lw x11, -16(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff0:4]
          LOAD register[0xb:4] <- unique[0x0:4]
        0x0001115c: 0x04b55e63  bge x10, x11, 0x111b8
          INT_SLESS unique[0x0:1] <- register[0xa:4], register[0xb:4]
          BOOL_NEGATE unique[0x4:1] <- unique[0x0:1]
          CBRANCH const[0x111b8:4], unique[0x4:1]`,
      },
      {
        address: "0x111b8",
        ir: `        0x000111b8: 0xfec42503  lw x10, -20(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffec:4]
          LOAD register[0xa:4] <- unique[0x0:4]
        0x000111bc: 0x01c12083  lw x1, 28(x2)
          INT_ADD unique[0x0:4] <- register[0x2:4], const[0x1c:4]
          LOAD register[0x1:4] <- unique[0x0:4]
        0x000111c0: 0x01812403  lw x8, 24(x2)
          INT_ADD unique[0x0:4] <- register[0x2:4], const[0x18:4]
          LOAD register[0x8:4] <- unique[0x0:4]
        0x000111c4: 0x02010113  addi x2, x2, 32
          INT_ADD register[0x2:4] <- register[0x2:4], const[0x20:4]
        0x000111c8: 0x00008067  jalr x0, 0(x1)
          COPY unique[0x0:4] <- register[0x1:4]
          INT_AND unique[0x4:4] <- unique[0x0:4], const[0xfffffffe:4]
          RETURN unique[0x4:4]`,
      },
      {
        address: "0x11160",
        ir: `        0x00011160: 0x0040006f  jal x0, 0x11164
          BRANCH const[0x11164:4]`,
      },
      {
        address: "0x11164",
        ir: `        0x00011164: 0xff442503  lw x10, -12(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff4:4]
          LOAD register[0xa:4] <- unique[0x0:4]
        0x00011168: 0xfe842583  lw x11, -24(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffe8:4]
          LOAD register[0xb:4] <- unique[0x0:4]
        0x0001116c: 0x00359593  slli x11, x11, 3
          INT_LEFT register[0xb:4] <- register[0xb:4], const[0x3:4]
        0x00011170: 0x00b50533  add x10, x10, x11
          INT_ADD register[0xa:4] <- register[0xa:4], register[0xb:4]
        0x00011174: 0x00052583  lw x11, 0(x10)
          COPY unique[0x0:4] <- register[0xa:4]
          LOAD register[0xb:4] <- unique[0x0:4]
        0x00011178: 0xfec42503  lw x10, -20(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffec:4]
          LOAD register[0xa:4] <- unique[0x0:4]
        0x0001117c: 0x00b50533  add x10, x10, x11
          INT_ADD register[0xa:4] <- register[0xa:4], register[0xb:4]
        0x00011180: 0xfea42623  sw x10, -20(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffec:4]
          STORE unique[0x0:4], register[0xa:4]
        0x00011184: 0xff442503  lw x10, -12(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff4:4]
          LOAD register[0xa:4] <- unique[0x0:4]
        0x00011188: 0xfe842583  lw x11, -24(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffe8:4]
          LOAD register[0xb:4] <- unique[0x0:4]
        0x0001118c: 0x00359593  slli x11, x11, 3
          INT_LEFT register[0xb:4] <- register[0xb:4], const[0x3:4]
        0x00011190: 0x00b50533  add x10, x10, x11
          INT_ADD register[0xa:4] <- register[0xa:4], register[0xb:4]
        0x00011194: 0x00452583  lw x11, 4(x10)
          INT_ADD unique[0x0:4] <- register[0xa:4], const[0x4:4]
          LOAD register[0xb:4] <- unique[0x0:4]
        0x00011198: 0xfec42503  lw x10, -20(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffec:4]
          LOAD register[0xa:4] <- unique[0x0:4]
        0x0001119c: 0x00b50533  add x10, x10, x11
          INT_ADD register[0xa:4] <- register[0xa:4], register[0xb:4]
        0x000111a0: 0xfea42623  sw x10, -20(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffec:4]
          STORE unique[0x0:4], register[0xa:4]
        0x000111a4: 0x0040006f  jal x0, 0x111a8
          BRANCH const[0x111a8:4]`,
      },
      {
        address: "0x111a8",
        ir: `        0x000111a8: 0xfe842503  lw x10, -24(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffe8:4]
          LOAD register[0xa:4] <- unique[0x0:4]
        0x000111ac: 0x00150513  addi x10, x10, 1
          INT_ADD register[0xa:4] <- register[0xa:4], const[0x1:4]
        0x000111b0: 0xfea42423  sw x10, -24(x8)
          INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffe8:4]
          STORE unique[0x0:4], register[0xa:4]
        0x000111b4: 0xfa1ff06f  jal x0, 0x11154
          BRANCH const[0x11154:4]`,
      }
        ],
        edges: [
      { source: "0x1112c", target: "0x11154", type: "normal" },
      { source: "0x11154", target: "0x111b8", label: "taken: i >= n", type: "normal" },
      { source: "0x11154", target: "0x11160", label: "fall: i < n", type: "normal" },
      { source: "0x11160", target: "0x11164", type: "normal" },
      { source: "0x11164", target: "0x111a8", type: "normal" },
      { source: "0x111a8", target: "0x11154", label: "back edge", type: "back" },
        ],
      },
    },
  },

  /* ── 7: SSA CONSTRUCTION ──────────────────────────────────────────────── */
  {
    id: "ssa",
    number: 7,
    name: "SSA Construction",
    phase: "analysis",
    description: "Each register definition gets a unique version (e.g., x10_1, x10_2). At the loop header (block 0x11154), phi-functions merge values from the entry and back-edge: PHI x10_2 <- 0x1112c:x10_1, 0x111a8:x10_14. Memory is also versioned.",
    githubDir: "tiny_dec/analysis/ssa",
    viewMode: "cfg",
    content: `  root: 0x110e4
  order: 0x110e4, 0x1112c
  pending:
  invalidated:
  externals:
    <none>
  call_graph:
    0x110e4@0x11118 -> internal 0x1112c name=parse_record
  functions:
    function 0x110e4 name=main reachable=1 unreachable=0 phis=0
    live_ins:
      x1_0:4
      x2_0:4
      x8_0:4
    memory_live_in:
      m0
    unreachable_blocks:
      <none>
    blocks:
      block 0x110e4 term=return succ=[] calls=[0x1112c] idom=<entry> df=[]
        0x000110e4: 0xfe010113  addi x2, x2, -32
          INT_ADD x2_1:4 <- x2_0:4, const[0xffffffe0:4]
        0x000110e8: 0x00112e23  sw x1, 28(x2)
          INT_ADD u0_1:4 <- x2_1:4, const[0x1c:4]
          STORE u0_1:4, x1_0:4 [m0 -> m1]
        0x000110ec: 0x00812c23  sw x8, 24(x2)
          INT_ADD u0_2:4 <- x2_1:4, const[0x18:4]
          STORE u0_2:4, x8_0:4 [m1 -> m2]
        0x000110f0: 0x02010413  addi x8, x2, 32
          INT_ADD x8_1:4 <- x2_1:4, const[0x20:4]
        0x000110f4: 0x01400513  addi x10, x0, 20
          COPY x10_1:4 <- const[0x14:4]
        0x000110f8: 0xfea42a23  sw x10, -12(x8)
          INT_ADD u0_3:4 <- x8_1:4, const[0xfffffff4:4]
          STORE u0_3:4, x10_1:4 [m2 -> m3]
        0x000110fc: 0x00200593  addi x11, x0, 2
          COPY x11_1:4 <- const[0x2:4]
        0x00011100: 0xfeb42823  sw x11, -16(x8)
          INT_ADD u0_4:4 <- x8_1:4, const[0xfffffff0:4]
          STORE u0_4:4, x11_1:4 [m3 -> m4]
        0x00011104: 0x00a00513  addi x10, x0, 10
          COPY x10_2:4 <- const[0xa:4]
        0x00011108: 0xfea42623  sw x10, -20(x8)
          INT_ADD u0_5:4 <- x8_1:4, const[0xffffffec:4]
          STORE u0_5:4, x10_2:4 [m4 -> m5]
        0x0001110c: 0x00100513  addi x10, x0, 1
          COPY x10_3:4 <- const[0x1:4]
        0x00011110: 0xfea42423  sw x10, -24(x8)
          INT_ADD u0_6:4 <- x8_1:4, const[0xffffffe8:4]
          STORE u0_6:4, x10_3:4 [m5 -> m6]
        0x00011114: 0xfe840513  addi x10, x8, -24
          INT_ADD x10_4:4 <- x8_1:4, const[0xffffffe8:4]
        0x00011118: 0x014000ef  jal x1, 0x1112c
          COPY x1_1:4 <- const[0x1111c:4]
          CALL const[0x1112c:4] [m6 -> m7]
          CALL_CLOBBER x1_2:4 <- const[0x11118:4]
          CALL_CLOBBER x5_1:4 <- const[0x11118:4]
          CALL_CLOBBER x6_1:4 <- const[0x11118:4]
          CALL_CLOBBER x7_1:4 <- const[0x11118:4]
          CALL_RETURN x10_5:4 <- const[0x11118:4]
          CALL_RETURN x11_2:4 <- const[0x11118:4]
          CALL_CLOBBER x12_1:4 <- const[0x11118:4]
          CALL_CLOBBER x13_1:4 <- const[0x11118:4]
          CALL_CLOBBER x14_1:4 <- const[0x11118:4]
          CALL_CLOBBER x15_1:4 <- const[0x11118:4]
          CALL_CLOBBER x16_1:4 <- const[0x11118:4]
          CALL_CLOBBER x17_1:4 <- const[0x11118:4]
          CALL_CLOBBER x28_1:4 <- const[0x11118:4]
          CALL_CLOBBER x29_1:4 <- const[0x11118:4]
          CALL_CLOBBER x30_1:4 <- const[0x11118:4]
          CALL_CLOBBER x31_1:4 <- const[0x11118:4]
        0x0001111c: 0x01c12083  lw x1, 28(x2)
          INT_ADD u0_7:4 <- x2_1:4, const[0x1c:4]
          LOAD x1_3:4 <- u0_7:4 [m7]
        0x00011120: 0x01812403  lw x8, 24(x2)
          INT_ADD u0_8:4 <- x2_1:4, const[0x18:4]
          LOAD x8_2:4 <- u0_8:4 [m7]
        0x00011124: 0x02010113  addi x2, x2, 32
          INT_ADD x2_2:4 <- x2_1:4, const[0x20:4]
        0x00011128: 0x00008067  jalr x0, 0(x1)
          COPY u0_9:4 <- x1_3:4
          INT_AND u4_1:4 <- u0_9:4, const[0xfffffffe:4]
          RETURN u4_1:4
    function 0x1112c name=parse_record reachable=6 unreachable=0 phis=2
    live_ins:
      x1_0:4
      x2_0:4
      x8_0:4
      x10_0:4
      x11_0:4
    memory_live_in:
      m0
    unreachable_blocks:
      <none>
    blocks:
      block 0x1112c term=jump succ=[jump:0x11154] idom=<entry> df=[]
        0x0001112c: 0xfe010113  addi x2, x2, -32
          INT_ADD x2_1:4 <- x2_0:4, const[0xffffffe0:4]
        0x00011130: 0x00112e23  sw x1, 28(x2)
          INT_ADD u0_1:4 <- x2_1:4, const[0x1c:4]
          STORE u0_1:4, x1_0:4 [m0 -> m1]
        0x00011134: 0x00812c23  sw x8, 24(x2)
          INT_ADD u0_2:4 <- x2_1:4, const[0x18:4]
          STORE u0_2:4, x8_0:4 [m1 -> m2]
        0x00011138: 0x02010413  addi x8, x2, 32
          INT_ADD x8_1:4 <- x2_1:4, const[0x20:4]
        0x0001113c: 0xfea42a23  sw x10, -12(x8)
          INT_ADD u0_3:4 <- x8_1:4, const[0xfffffff4:4]
          STORE u0_3:4, x10_0:4 [m2 -> m3]
        0x00011140: 0xfeb42823  sw x11, -16(x8)
          INT_ADD u0_4:4 <- x8_1:4, const[0xfffffff0:4]
          STORE u0_4:4, x11_0:4 [m3 -> m4]
        0x00011144: 0x00000513  addi x10, x0, 0
          COPY x10_1:4 <- const[0x0:4]
        0x00011148: 0xfea42623  sw x10, -20(x8)
          INT_ADD u0_5:4 <- x8_1:4, const[0xffffffec:4]
          STORE u0_5:4, x10_1:4 [m4 -> m5]
        0x0001114c: 0xfea42423  sw x10, -24(x8)
          INT_ADD u0_6:4 <- x8_1:4, const[0xffffffe8:4]
          STORE u0_6:4, x10_1:4 [m5 -> m6]
        0x00011150: 0x0040006f  jal x0, 0x11154
          BRANCH const[0x11154:4]
      block 0x11154 term=branch succ=[branch_taken:0x111b8, fallthrough:0x11160] idom=0x1112c df=[0x11154]
        MEM_PHI m7 <- 0x1112c:m6, 0x111a8:m10
        PHI x10_2:4 <- 0x1112c:x10_1:4, 0x111a8:x10_14:4
        PHI x11_1:4 <- 0x1112c:x11_0:4, 0x111a8:x11_8:4
        0x00011154: 0xfe842503  lw x10, -24(x8)
          INT_ADD u0_7:4 <- x8_1:4, const[0xffffffe8:4]
          LOAD x10_3:4 <- u0_7:4 [m7]
        0x00011158: 0xff042583  lw x11, -16(x8)
          INT_ADD u0_8:4 <- x8_1:4, const[0xfffffff0:4]
          LOAD x11_2:4 <- u0_8:4 [m7]
        0x0001115c: 0x04b55e63  bge x10, x11, 0x111b8
          INT_SLESS u0_1:1 <- x10_3:4, x11_2:4
          BOOL_NEGATE u4_1:1 <- u0_1:1
          CBRANCH const[0x111b8:4], u4_1:1
      block 0x111b8 term=return succ=[] idom=0x11154 df=[]
        0x000111b8: 0xfec42503  lw x10, -20(x8)
          INT_ADD u0_9:4 <- x8_1:4, const[0xffffffec:4]
          LOAD x10_4:4 <- u0_9:4 [m7]
        0x000111bc: 0x01c12083  lw x1, 28(x2)
          INT_ADD u0_10:4 <- x2_1:4, const[0x1c:4]
          LOAD x1_1:4 <- u0_10:4 [m7]
        0x000111c0: 0x01812403  lw x8, 24(x2)
          INT_ADD u0_11:4 <- x2_1:4, const[0x18:4]
          LOAD x8_2:4 <- u0_11:4 [m7]
        0x000111c4: 0x02010113  addi x2, x2, 32
          INT_ADD x2_2:4 <- x2_1:4, const[0x20:4]
        0x000111c8: 0x00008067  jalr x0, 0(x1)
          COPY u0_12:4 <- x1_1:4
          INT_AND u4_1:4 <- u0_12:4, const[0xfffffffe:4]
          RETURN u4_1:4
      block 0x11160 term=jump succ=[jump:0x11164] idom=0x11154 df=[0x11154]
        0x00011160: 0x0040006f  jal x0, 0x11164
          BRANCH const[0x11164:4]
      block 0x11164 term=jump succ=[jump:0x111a8] idom=0x11160 df=[0x11154]
        0x00011164: 0xff442503  lw x10, -12(x8)
          INT_ADD u0_13:4 <- x8_1:4, const[0xfffffff4:4]
          LOAD x10_5:4 <- u0_13:4 [m7]
        0x00011168: 0xfe842583  lw x11, -24(x8)
          INT_ADD u0_14:4 <- x8_1:4, const[0xffffffe8:4]
          LOAD x11_3:4 <- u0_14:4 [m7]
        0x0001116c: 0x00359593  slli x11, x11, 3
          INT_LEFT x11_4:4 <- x11_3:4, const[0x3:4]
        0x00011170: 0x00b50533  add x10, x10, x11
          INT_ADD x10_6:4 <- x10_5:4, x11_4:4
        0x00011174: 0x00052583  lw x11, 0(x10)
          COPY u0_15:4 <- x10_6:4
          LOAD x11_5:4 <- u0_15:4 [m7]
        0x00011178: 0xfec42503  lw x10, -20(x8)
          INT_ADD u0_16:4 <- x8_1:4, const[0xffffffec:4]
          LOAD x10_7:4 <- u0_16:4 [m7]
        0x0001117c: 0x00b50533  add x10, x10, x11
          INT_ADD x10_8:4 <- x10_7:4, x11_5:4
        0x00011180: 0xfea42623  sw x10, -20(x8)
          INT_ADD u0_17:4 <- x8_1:4, const[0xffffffec:4]
          STORE u0_17:4, x10_8:4 [m7 -> m8]
        0x00011184: 0xff442503  lw x10, -12(x8)
          INT_ADD u0_18:4 <- x8_1:4, const[0xfffffff4:4]
          LOAD x10_9:4 <- u0_18:4 [m8]
        0x00011188: 0xfe842583  lw x11, -24(x8)
          INT_ADD u0_19:4 <- x8_1:4, const[0xffffffe8:4]
          LOAD x11_6:4 <- u0_19:4 [m8]
        0x0001118c: 0x00359593  slli x11, x11, 3
          INT_LEFT x11_7:4 <- x11_6:4, const[0x3:4]
        0x00011190: 0x00b50533  add x10, x10, x11
          INT_ADD x10_10:4 <- x10_9:4, x11_7:4
        0x00011194: 0x00452583  lw x11, 4(x10)
          INT_ADD u0_20:4 <- x10_10:4, const[0x4:4]
          LOAD x11_8:4 <- u0_20:4 [m8]
        0x00011198: 0xfec42503  lw x10, -20(x8)
          INT_ADD u0_21:4 <- x8_1:4, const[0xffffffec:4]
          LOAD x10_11:4 <- u0_21:4 [m8]
        0x0001119c: 0x00b50533  add x10, x10, x11
          INT_ADD x10_12:4 <- x10_11:4, x11_8:4
        0x000111a0: 0xfea42623  sw x10, -20(x8)
          INT_ADD u0_22:4 <- x8_1:4, const[0xffffffec:4]
          STORE u0_22:4, x10_12:4 [m8 -> m9]
        0x000111a4: 0x0040006f  jal x0, 0x111a8
          BRANCH const[0x111a8:4]
      block 0x111a8 term=jump succ=[jump:0x11154] idom=0x11164 df=[0x11154]
        0x000111a8: 0xfe842503  lw x10, -24(x8)
          INT_ADD u0_23:4 <- x8_1:4, const[0xffffffe8:4]
          LOAD x10_13:4 <- u0_23:4 [m9]
        0x000111ac: 0x00150513  addi x10, x10, 1
          INT_ADD x10_14:4 <- x10_13:4, const[0x1:4]
        0x000111b0: 0xfea42423  sw x10, -24(x8)
          INT_ADD u0_24:4 <- x8_1:4, const[0xffffffe8:4]
          STORE u0_24:4, x10_14:4 [m9 -> m10]
        0x000111b4: 0xfa1ff06f  jal x0, 0x11154
          BRANCH const[0x11154:4]`,
    cfg: {
      main: {
        blocks: [
      {
        address: "0x110e4",
        ir: `    0x000110e4: 0xfe010113  addi x2, x2, -32
      INT_ADD register[0x2:4] <- register[0x2:4], const[0xffffffe0:4]
    0x000110e8: 0x00112e23  sw x1, 28(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x1c:4]
      STORE unique[0x0:4], register[0x1:4]
    0x000110ec: 0x00812c23  sw x8, 24(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x18:4]
      STORE unique[0x0:4], register[0x8:4]
    0x000110f0: 0x02010413  addi x8, x2, 32
      INT_ADD register[0x8:4] <- register[0x2:4], const[0x20:4]
    0x000110f4: 0x01400513  addi x10, x0, 20
      COPY register[0xa:4] <- const[0x14:4]
    0x000110f8: 0xfea42a23  sw x10, -12(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff4:4]
      STORE unique[0x0:4], register[0xa:4]
    0x000110fc: 0x00200593  addi x11, x0, 2
      COPY register[0xb:4] <- const[0x2:4]
    0x00011100: 0xfeb42823  sw x11, -16(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff0:4]
      STORE unique[0x0:4], register[0xb:4]
    0x00011104: 0x00a00513  addi x10, x0, 10
      COPY register[0xa:4] <- const[0xa:4]
    0x00011108: 0xfea42623  sw x10, -20(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffec:4]
      STORE unique[0x0:4], register[0xa:4]
    0x0001110c: 0x00100513  addi x10, x0, 1
      COPY register[0xa:4] <- const[0x1:4]
    0x00011110: 0xfea42423  sw x10, -24(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffe8:4]
      STORE unique[0x0:4], register[0xa:4]
    0x00011114: 0xfe840513  addi x10, x8, -24
      INT_ADD register[0xa:4] <- register[0x8:4], const[0xffffffe8:4]
    0x00011118: 0x014000ef  jal x1, 0x1112c
      COPY register[0x1:4] <- const[0x1111c:4]
      CALL const[0x1112c:4]
    0x0001111c: 0x01c12083  lw x1, 28(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x1c:4]
      LOAD unique[0x4:4] <- unique[0x0:4]
      COPY register[0x1:4] <- unique[0x4:4]
    0x00011120: 0x01812403  lw x8, 24(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x18:4]
      LOAD unique[0x4:4] <- unique[0x0:4]
      COPY register[0x8:4] <- unique[0x4:4]
    0x00011124: 0x02010113  addi x2, x2, 32
      INT_ADD register[0x2:4] <- register[0x2:4], const[0x20:4]
    0x00011128: 0x00008067  jalr x0, 0(x1)
      COPY unique[0x0:4] <- register[0x1:4]
      INT_AND unique[0x4:4] <- unique[0x0:4], const[0xfffffffe:4]
      RETURN unique[0x4:4]`,
      },
        ],
        edges: [],
      },
      parse_record: {
        blocks: [
      {
        address: "0x1112c",
        ir: `        0x0001112c: 0xfe010113  addi x2, x2, -32
          INT_ADD x2_1:4 <- x2_0:4, const[0xffffffe0:4]
        0x00011130: 0x00112e23  sw x1, 28(x2)
          INT_ADD u0_1:4 <- x2_1:4, const[0x1c:4]
          STORE u0_1:4, x1_0:4 [m0 -> m1]
        0x00011134: 0x00812c23  sw x8, 24(x2)
          INT_ADD u0_2:4 <- x2_1:4, const[0x18:4]
          STORE u0_2:4, x8_0:4 [m1 -> m2]
        0x00011138: 0x02010413  addi x8, x2, 32
          INT_ADD x8_1:4 <- x2_1:4, const[0x20:4]
        0x0001113c: 0xfea42a23  sw x10, -12(x8)
          INT_ADD u0_3:4 <- x8_1:4, const[0xfffffff4:4]
          STORE u0_3:4, x10_0:4 [m2 -> m3]
        0x00011140: 0xfeb42823  sw x11, -16(x8)
          INT_ADD u0_4:4 <- x8_1:4, const[0xfffffff0:4]
          STORE u0_4:4, x11_0:4 [m3 -> m4]
        0x00011144: 0x00000513  addi x10, x0, 0
          COPY x10_1:4 <- const[0x0:4]
        0x00011148: 0xfea42623  sw x10, -20(x8)
          INT_ADD u0_5:4 <- x8_1:4, const[0xffffffec:4]
          STORE u0_5:4, x10_1:4 [m4 -> m5]
        0x0001114c: 0xfea42423  sw x10, -24(x8)
          INT_ADD u0_6:4 <- x8_1:4, const[0xffffffe8:4]
          STORE u0_6:4, x10_1:4 [m5 -> m6]
        0x00011150: 0x0040006f  jal x0, 0x11154
          BRANCH const[0x11154:4]`,
      },
      {
        address: "0x11154",
        ir: `        MEM_PHI m7 <- 0x1112c:m6, 0x111a8:m10
        PHI x10_2:4 <- 0x1112c:x10_1:4, 0x111a8:x10_14:4
        PHI x11_1:4 <- 0x1112c:x11_0:4, 0x111a8:x11_8:4
        0x00011154: 0xfe842503  lw x10, -24(x8)
          INT_ADD u0_7:4 <- x8_1:4, const[0xffffffe8:4]
          LOAD x10_3:4 <- u0_7:4 [m7]
        0x00011158: 0xff042583  lw x11, -16(x8)
          INT_ADD u0_8:4 <- x8_1:4, const[0xfffffff0:4]
          LOAD x11_2:4 <- u0_8:4 [m7]
        0x0001115c: 0x04b55e63  bge x10, x11, 0x111b8
          INT_SLESS u0_1:1 <- x10_3:4, x11_2:4
          BOOL_NEGATE u4_1:1 <- u0_1:1
          CBRANCH const[0x111b8:4], u4_1:1`,
      },
      {
        address: "0x111b8",
        ir: `        0x000111b8: 0xfec42503  lw x10, -20(x8)
          INT_ADD u0_9:4 <- x8_1:4, const[0xffffffec:4]
          LOAD x10_4:4 <- u0_9:4 [m7]
        0x000111bc: 0x01c12083  lw x1, 28(x2)
          INT_ADD u0_10:4 <- x2_1:4, const[0x1c:4]
          LOAD x1_1:4 <- u0_10:4 [m7]
        0x000111c0: 0x01812403  lw x8, 24(x2)
          INT_ADD u0_11:4 <- x2_1:4, const[0x18:4]
          LOAD x8_2:4 <- u0_11:4 [m7]
        0x000111c4: 0x02010113  addi x2, x2, 32
          INT_ADD x2_2:4 <- x2_1:4, const[0x20:4]
        0x000111c8: 0x00008067  jalr x0, 0(x1)
          COPY u0_12:4 <- x1_1:4
          INT_AND u4_1:4 <- u0_12:4, const[0xfffffffe:4]
          RETURN u4_1:4`,
      },
      {
        address: "0x11160",
        ir: `        0x00011160: 0x0040006f  jal x0, 0x11164
          BRANCH const[0x11164:4]`,
      },
      {
        address: "0x11164",
        ir: `        0x00011164: 0xff442503  lw x10, -12(x8)
          INT_ADD u0_13:4 <- x8_1:4, const[0xfffffff4:4]
          LOAD x10_5:4 <- u0_13:4 [m7]
        0x00011168: 0xfe842583  lw x11, -24(x8)
          INT_ADD u0_14:4 <- x8_1:4, const[0xffffffe8:4]
          LOAD x11_3:4 <- u0_14:4 [m7]
        0x0001116c: 0x00359593  slli x11, x11, 3
          INT_LEFT x11_4:4 <- x11_3:4, const[0x3:4]
        0x00011170: 0x00b50533  add x10, x10, x11
          INT_ADD x10_6:4 <- x10_5:4, x11_4:4
        0x00011174: 0x00052583  lw x11, 0(x10)
          COPY u0_15:4 <- x10_6:4
          LOAD x11_5:4 <- u0_15:4 [m7]
        0x00011178: 0xfec42503  lw x10, -20(x8)
          INT_ADD u0_16:4 <- x8_1:4, const[0xffffffec:4]
          LOAD x10_7:4 <- u0_16:4 [m7]
        0x0001117c: 0x00b50533  add x10, x10, x11
          INT_ADD x10_8:4 <- x10_7:4, x11_5:4
        0x00011180: 0xfea42623  sw x10, -20(x8)
          INT_ADD u0_17:4 <- x8_1:4, const[0xffffffec:4]
          STORE u0_17:4, x10_8:4 [m7 -> m8]
        0x00011184: 0xff442503  lw x10, -12(x8)
          INT_ADD u0_18:4 <- x8_1:4, const[0xfffffff4:4]
          LOAD x10_9:4 <- u0_18:4 [m8]
        0x00011188: 0xfe842583  lw x11, -24(x8)
          INT_ADD u0_19:4 <- x8_1:4, const[0xffffffe8:4]
          LOAD x11_6:4 <- u0_19:4 [m8]
        0x0001118c: 0x00359593  slli x11, x11, 3
          INT_LEFT x11_7:4 <- x11_6:4, const[0x3:4]
        0x00011190: 0x00b50533  add x10, x10, x11
          INT_ADD x10_10:4 <- x10_9:4, x11_7:4
        0x00011194: 0x00452583  lw x11, 4(x10)
          INT_ADD u0_20:4 <- x10_10:4, const[0x4:4]
          LOAD x11_8:4 <- u0_20:4 [m8]
        0x00011198: 0xfec42503  lw x10, -20(x8)
          INT_ADD u0_21:4 <- x8_1:4, const[0xffffffec:4]
          LOAD x10_11:4 <- u0_21:4 [m8]
        0x0001119c: 0x00b50533  add x10, x10, x11
          INT_ADD x10_12:4 <- x10_11:4, x11_8:4
        0x000111a0: 0xfea42623  sw x10, -20(x8)
          INT_ADD u0_22:4 <- x8_1:4, const[0xffffffec:4]
          STORE u0_22:4, x10_12:4 [m8 -> m9]
        0x000111a4: 0x0040006f  jal x0, 0x111a8
          BRANCH const[0x111a8:4]`,
      },
      {
        address: "0x111a8",
        ir: `        0x000111a8: 0xfe842503  lw x10, -24(x8)
          INT_ADD u0_23:4 <- x8_1:4, const[0xffffffe8:4]
          LOAD x10_13:4 <- u0_23:4 [m9]
        0x000111ac: 0x00150513  addi x10, x10, 1
          INT_ADD x10_14:4 <- x10_13:4, const[0x1:4]
        0x000111b0: 0xfea42423  sw x10, -24(x8)
          INT_ADD u0_24:4 <- x8_1:4, const[0xffffffe8:4]
          STORE u0_24:4, x10_14:4 [m9 -> m10]
        0x000111b4: 0xfa1ff06f  jal x0, 0x11154
          BRANCH const[0x11154:4]`,
      }
        ],
        edges: [
      { source: "0x1112c", target: "0x11154", type: "normal" },
      { source: "0x11154", target: "0x111b8", label: "taken: i >= n", type: "normal" },
      { source: "0x11154", target: "0x11160", label: "fall: i < n", type: "normal" },
      { source: "0x11160", target: "0x11164", type: "normal" },
      { source: "0x11164", target: "0x111a8", type: "normal" },
      { source: "0x111a8", target: "0x11154", label: "back edge", type: "back" },
        ],
      },
    },
  },

  /* ── 8: CALL ANALYSIS ──────────────────────────────────────────────── */
  {
    id: "calls",
    number: 8,
    name: "Call Analysis",
    phase: "analysis",
    description: "The RISC-V rv32i_ilp32 ABI maps arguments to registers x10-x17 and return values to x10-x11. At callsite 0x11118, main passes x10=x10_4 (pointer to locals) and x11=x11_1 (count=2) to parse_record.",
    githubDir: "tiny_dec/analysis/calls",
    viewMode: "cfg",
    content: `  root: 0x110e4
  order: 0x110e4, 0x1112c
  pending:
  invalidated:
  abi: rv32i_ilp32 args=[x10, x11, x12, x13, x14, x15, x16, x17] returns=[x10, x11] clobbers=[x1, x5, x6, x7, x10, x11, x12, x13, x14, x15, x16, x17, x28, x29, x30, x31]
  externals:
    <none>
  call_graph:
    0x110e4@0x11118 -> internal 0x1112c name=parse_record
  functions:
    function 0x110e4 name=main callsites=1 pending=[]
    abi: rv32i_ilp32 args=[x10, x11, x12, x13, x14, x15, x16, x17] returns=[x10, x11] clobbers=[x1, x5, x6, x7, x10, x11, x12, x13, x14, x15, x16, x17, x28, x29, x30, x31]
    callsites:
      call 0x11118 block=0x110e4 via=direct -> internal 0x1112c name=parse_record args=[x10=x10_4:4, x11=x11_1:4] mem=[m6 -> m7] returns=[x10=x10_5:4, x11=x11_2:4]
    function 0x1112c name=parse_record callsites=0 pending=[]
    abi: rv32i_ilp32 args=[x10, x11, x12, x13, x14, x15, x16, x17] returns=[x10, x11] clobbers=[x1, x5, x6, x7, x10, x11, x12, x13, x14, x15, x16, x17, x28, x29, x30, x31]
    callsites:
      <none>`,
    cfg: {
      main: {
        blocks: [
      {
        address: "0x110e4",
        ir: `    0x000110e4: 0xfe010113  addi x2, x2, -32
      INT_ADD register[0x2:4] <- register[0x2:4], const[0xffffffe0:4]
    0x000110e8: 0x00112e23  sw x1, 28(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x1c:4]
      STORE unique[0x0:4], register[0x1:4]
    0x000110ec: 0x00812c23  sw x8, 24(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x18:4]
      STORE unique[0x0:4], register[0x8:4]
    0x000110f0: 0x02010413  addi x8, x2, 32
      INT_ADD register[0x8:4] <- register[0x2:4], const[0x20:4]
    0x000110f4: 0x01400513  addi x10, x0, 20
      COPY register[0xa:4] <- const[0x14:4]
    0x000110f8: 0xfea42a23  sw x10, -12(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff4:4]
      STORE unique[0x0:4], register[0xa:4]
    0x000110fc: 0x00200593  addi x11, x0, 2
      COPY register[0xb:4] <- const[0x2:4]
    0x00011100: 0xfeb42823  sw x11, -16(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff0:4]
      STORE unique[0x0:4], register[0xb:4]
    0x00011104: 0x00a00513  addi x10, x0, 10
      COPY register[0xa:4] <- const[0xa:4]
    0x00011108: 0xfea42623  sw x10, -20(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffec:4]
      STORE unique[0x0:4], register[0xa:4]
    0x0001110c: 0x00100513  addi x10, x0, 1
      COPY register[0xa:4] <- const[0x1:4]
    0x00011110: 0xfea42423  sw x10, -24(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffe8:4]
      STORE unique[0x0:4], register[0xa:4]
    0x00011114: 0xfe840513  addi x10, x8, -24
      INT_ADD register[0xa:4] <- register[0x8:4], const[0xffffffe8:4]
    0x00011118: 0x014000ef  jal x1, 0x1112c
      COPY register[0x1:4] <- const[0x1111c:4]
      CALL const[0x1112c:4]
    0x0001111c: 0x01c12083  lw x1, 28(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x1c:4]
      LOAD unique[0x4:4] <- unique[0x0:4]
      COPY register[0x1:4] <- unique[0x4:4]
    0x00011120: 0x01812403  lw x8, 24(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x18:4]
      LOAD unique[0x4:4] <- unique[0x0:4]
      COPY register[0x8:4] <- unique[0x4:4]
    0x00011124: 0x02010113  addi x2, x2, 32
      INT_ADD register[0x2:4] <- register[0x2:4], const[0x20:4]
    0x00011128: 0x00008067  jalr x0, 0(x1)
      COPY unique[0x0:4] <- register[0x1:4]
      INT_AND unique[0x4:4] <- unique[0x0:4], const[0xfffffffe:4]
      RETURN unique[0x4:4]`,
      },
        ],
        edges: [],
      },
      parse_record: {
        blocks: [
      {
        address: "0x1112c",
        ir: `        0x0001112c: 0xfe010113  addi x2, x2, -32
          INT_ADD x2_1:4 <- x2_0:4, const[0xffffffe0:4]
        0x00011130: 0x00112e23  sw x1, 28(x2)
          INT_ADD u0_1:4 <- x2_1:4, const[0x1c:4]
          STORE u0_1:4, x1_0:4 [m0 -> m1]
        0x00011134: 0x00812c23  sw x8, 24(x2)
          INT_ADD u0_2:4 <- x2_1:4, const[0x18:4]
          STORE u0_2:4, x8_0:4 [m1 -> m2]
        0x00011138: 0x02010413  addi x8, x2, 32
          INT_ADD x8_1:4 <- x2_1:4, const[0x20:4]
        0x0001113c: 0xfea42a23  sw x10, -12(x8)
          INT_ADD u0_3:4 <- x8_1:4, const[0xfffffff4:4]
          STORE u0_3:4, x10_0:4 [m2 -> m3]
        0x00011140: 0xfeb42823  sw x11, -16(x8)
          INT_ADD u0_4:4 <- x8_1:4, const[0xfffffff0:4]
          STORE u0_4:4, x11_0:4 [m3 -> m4]
        0x00011144: 0x00000513  addi x10, x0, 0
          COPY x10_1:4 <- const[0x0:4]
        0x00011148: 0xfea42623  sw x10, -20(x8)
          INT_ADD u0_5:4 <- x8_1:4, const[0xffffffec:4]
          STORE u0_5:4, x10_1:4 [m4 -> m5]
        0x0001114c: 0xfea42423  sw x10, -24(x8)
          INT_ADD u0_6:4 <- x8_1:4, const[0xffffffe8:4]
          STORE u0_6:4, x10_1:4 [m5 -> m6]
        0x00011150: 0x0040006f  jal x0, 0x11154
          BRANCH const[0x11154:4]`,
      },
      {
        address: "0x11154",
        ir: `        MEM_PHI m7 <- 0x1112c:m6, 0x111a8:m10
        PHI x10_2:4 <- 0x1112c:x10_1:4, 0x111a8:x10_14:4
        PHI x11_1:4 <- 0x1112c:x11_0:4, 0x111a8:x11_8:4
        0x00011154: 0xfe842503  lw x10, -24(x8)
          INT_ADD u0_7:4 <- x8_1:4, const[0xffffffe8:4]
          LOAD x10_3:4 <- u0_7:4 [m7]
        0x00011158: 0xff042583  lw x11, -16(x8)
          INT_ADD u0_8:4 <- x8_1:4, const[0xfffffff0:4]
          LOAD x11_2:4 <- u0_8:4 [m7]
        0x0001115c: 0x04b55e63  bge x10, x11, 0x111b8
          INT_SLESS u0_1:1 <- x10_3:4, x11_2:4
          BOOL_NEGATE u4_1:1 <- u0_1:1
          CBRANCH const[0x111b8:4], u4_1:1`,
      },
      {
        address: "0x111b8",
        ir: `        0x000111b8: 0xfec42503  lw x10, -20(x8)
          INT_ADD u0_9:4 <- x8_1:4, const[0xffffffec:4]
          LOAD x10_4:4 <- u0_9:4 [m7]
        0x000111bc: 0x01c12083  lw x1, 28(x2)
          INT_ADD u0_10:4 <- x2_1:4, const[0x1c:4]
          LOAD x1_1:4 <- u0_10:4 [m7]
        0x000111c0: 0x01812403  lw x8, 24(x2)
          INT_ADD u0_11:4 <- x2_1:4, const[0x18:4]
          LOAD x8_2:4 <- u0_11:4 [m7]
        0x000111c4: 0x02010113  addi x2, x2, 32
          INT_ADD x2_2:4 <- x2_1:4, const[0x20:4]
        0x000111c8: 0x00008067  jalr x0, 0(x1)
          COPY u0_12:4 <- x1_1:4
          INT_AND u4_1:4 <- u0_12:4, const[0xfffffffe:4]
          RETURN u4_1:4`,
      },
      {
        address: "0x11160",
        ir: `        0x00011160: 0x0040006f  jal x0, 0x11164
          BRANCH const[0x11164:4]`,
      },
      {
        address: "0x11164",
        ir: `        0x00011164: 0xff442503  lw x10, -12(x8)
          INT_ADD u0_13:4 <- x8_1:4, const[0xfffffff4:4]
          LOAD x10_5:4 <- u0_13:4 [m7]
        0x00011168: 0xfe842583  lw x11, -24(x8)
          INT_ADD u0_14:4 <- x8_1:4, const[0xffffffe8:4]
          LOAD x11_3:4 <- u0_14:4 [m7]
        0x0001116c: 0x00359593  slli x11, x11, 3
          INT_LEFT x11_4:4 <- x11_3:4, const[0x3:4]
        0x00011170: 0x00b50533  add x10, x10, x11
          INT_ADD x10_6:4 <- x10_5:4, x11_4:4
        0x00011174: 0x00052583  lw x11, 0(x10)
          COPY u0_15:4 <- x10_6:4
          LOAD x11_5:4 <- u0_15:4 [m7]
        0x00011178: 0xfec42503  lw x10, -20(x8)
          INT_ADD u0_16:4 <- x8_1:4, const[0xffffffec:4]
          LOAD x10_7:4 <- u0_16:4 [m7]
        0x0001117c: 0x00b50533  add x10, x10, x11
          INT_ADD x10_8:4 <- x10_7:4, x11_5:4
        0x00011180: 0xfea42623  sw x10, -20(x8)
          INT_ADD u0_17:4 <- x8_1:4, const[0xffffffec:4]
          STORE u0_17:4, x10_8:4 [m7 -> m8]
        0x00011184: 0xff442503  lw x10, -12(x8)
          INT_ADD u0_18:4 <- x8_1:4, const[0xfffffff4:4]
          LOAD x10_9:4 <- u0_18:4 [m8]
        0x00011188: 0xfe842583  lw x11, -24(x8)
          INT_ADD u0_19:4 <- x8_1:4, const[0xffffffe8:4]
          LOAD x11_6:4 <- u0_19:4 [m8]
        0x0001118c: 0x00359593  slli x11, x11, 3
          INT_LEFT x11_7:4 <- x11_6:4, const[0x3:4]
        0x00011190: 0x00b50533  add x10, x10, x11
          INT_ADD x10_10:4 <- x10_9:4, x11_7:4
        0x00011194: 0x00452583  lw x11, 4(x10)
          INT_ADD u0_20:4 <- x10_10:4, const[0x4:4]
          LOAD x11_8:4 <- u0_20:4 [m8]
        0x00011198: 0xfec42503  lw x10, -20(x8)
          INT_ADD u0_21:4 <- x8_1:4, const[0xffffffec:4]
          LOAD x10_11:4 <- u0_21:4 [m8]
        0x0001119c: 0x00b50533  add x10, x10, x11
          INT_ADD x10_12:4 <- x10_11:4, x11_8:4
        0x000111a0: 0xfea42623  sw x10, -20(x8)
          INT_ADD u0_22:4 <- x8_1:4, const[0xffffffec:4]
          STORE u0_22:4, x10_12:4 [m8 -> m9]
        0x000111a4: 0x0040006f  jal x0, 0x111a8
          BRANCH const[0x111a8:4]`,
      },
      {
        address: "0x111a8",
        ir: `        0x000111a8: 0xfe842503  lw x10, -24(x8)
          INT_ADD u0_23:4 <- x8_1:4, const[0xffffffe8:4]
          LOAD x10_13:4 <- u0_23:4 [m9]
        0x000111ac: 0x00150513  addi x10, x10, 1
          INT_ADD x10_14:4 <- x10_13:4, const[0x1:4]
        0x000111b0: 0xfea42423  sw x10, -24(x8)
          INT_ADD u0_24:4 <- x8_1:4, const[0xffffffe8:4]
          STORE u0_24:4, x10_14:4 [m9 -> m10]
        0x000111b4: 0xfa1ff06f  jal x0, 0x11154
          BRANCH const[0x11154:4]`,
      }
        ],
        edges: [
      { source: "0x1112c", target: "0x11154", type: "normal" },
      { source: "0x11154", target: "0x111b8", label: "taken: i >= n", type: "normal" },
      { source: "0x11154", target: "0x11160", label: "fall: i < n", type: "normal" },
      { source: "0x11160", target: "0x11164", type: "normal" },
      { source: "0x11164", target: "0x111a8", type: "normal" },
      { source: "0x111a8", target: "0x11154", label: "back edge", type: "back" },
        ],
      },
    },
  },

  /* ── 9: STACK ANALYSIS ──────────────────────────────────────────────── */
  {
    id: "stack",
    number: 9,
    name: "Stack Analysis",
    phase: "analysis",
    description: "Each function's stack frame is decomposed into typed slots. main has 6 slots: four locals at offsets -24 through -12, plus callee-saved x8 and return address x1. parse_record has similar structure plus argument home slots.",
    githubDir: "tiny_dec/analysis/stack",
    viewMode: "cfg",
    content: `  root: 0x110e4
  order: 0x110e4, 0x1112c
  pending:
  invalidated:
  externals:
    <none>
  call_graph:
    0x110e4@0x11118 -> internal 0x1112c name=parse_record
  functions:
    function 0x110e4 name=main frame_size=32 fp=frame_pointer x8=x8_1:4 delta=+0 dynamic_sp=no slots=6 pending=[]
    slots:
      slot -24 size=4 role=local accesses=1
        store 0x11110 block=0x110e4 slot=-24 size=4 via=frame_pointer(x8) value=x10_3:4
      slot -20 size=4 role=local accesses=1
        store 0x11108 block=0x110e4 slot=-20 size=4 via=frame_pointer(x8) value=x10_2:4
      slot -16 size=4 role=local accesses=1
        store 0x11100 block=0x110e4 slot=-16 size=4 via=frame_pointer(x8) value=x11_1:4
      slot -12 size=4 role=local accesses=1
        store 0x110f8 block=0x110e4 slot=-12 size=4 via=frame_pointer(x8) value=x10_1:4
      slot -8 size=4 role=saved_register(x8) accesses=2
        store 0x110ec block=0x110e4 slot=-8 size=4 via=stack_pointer(x2) value=x8_0:4
        load 0x11120 block=0x110e4 slot=-8 size=4 via=stack_pointer(x2) value=x8_2:4
      slot -4 size=4 role=saved_register(x1) accesses=2
        store 0x110e8 block=0x110e4 slot=-4 size=4 via=stack_pointer(x2) value=x1_0:4
        load 0x1111c block=0x110e4 slot=-4 size=4 via=stack_pointer(x2) value=x1_3:4
    function 0x1112c name=parse_record frame_size=32 fp=frame_pointer x8=x8_1:4 delta=+0 dynamic_sp=no slots=6 pending=[]
    slots:
      slot -24 size=4 role=local accesses=6
        store 0x1114c block=0x1112c slot=-24 size=4 via=frame_pointer(x8) value=x10_1:4
        load 0x11154 block=0x11154 slot=-24 size=4 via=frame_pointer(x8) value=x10_3:4
        load 0x11168 block=0x11164 slot=-24 size=4 via=frame_pointer(x8) value=x11_3:4
        load 0x11188 block=0x11164 slot=-24 size=4 via=frame_pointer(x8) value=x11_6:4
        load 0x111a8 block=0x111a8 slot=-24 size=4 via=frame_pointer(x8) value=x10_13:4
        store 0x111b0 block=0x111a8 slot=-24 size=4 via=frame_pointer(x8) value=x10_14:4
      slot -20 size=4 role=local accesses=6
        store 0x11148 block=0x1112c slot=-20 size=4 via=frame_pointer(x8) value=x10_1:4
        load 0x11178 block=0x11164 slot=-20 size=4 via=frame_pointer(x8) value=x10_7:4
        store 0x11180 block=0x11164 slot=-20 size=4 via=frame_pointer(x8) value=x10_8:4
        load 0x11198 block=0x11164 slot=-20 size=4 via=frame_pointer(x8) value=x10_11:4
        store 0x111a0 block=0x11164 slot=-20 size=4 via=frame_pointer(x8) value=x10_12:4
        load 0x111b8 block=0x111b8 slot=-20 size=4 via=frame_pointer(x8) value=x10_4:4
      slot -16 size=4 role=argument_home(x11) accesses=2
        store 0x11140 block=0x1112c slot=-16 size=4 via=frame_pointer(x8) value=x11_0:4
        load 0x11158 block=0x11154 slot=-16 size=4 via=frame_pointer(x8) value=x11_2:4
      slot -12 size=4 role=argument_home(x10) accesses=3
        store 0x1113c block=0x1112c slot=-12 size=4 via=frame_pointer(x8) value=x10_0:4
        load 0x11164 block=0x11164 slot=-12 size=4 via=frame_pointer(x8) value=x10_5:4
        load 0x11184 block=0x11164 slot=-12 size=4 via=frame_pointer(x8) value=x10_9:4
      slot -8 size=4 role=saved_register(x8) accesses=2
        store 0x11134 block=0x1112c slot=-8 size=4 via=stack_pointer(x2) value=x8_0:4
        load 0x111c0 block=0x111b8 slot=-8 size=4 via=stack_pointer(x2) value=x8_2:4
      slot -4 size=4 role=saved_register(x1) accesses=2
        store 0x11130 block=0x1112c slot=-4 size=4 via=stack_pointer(x2) value=x1_0:4
        load 0x111bc block=0x111b8 slot=-4 size=4 via=stack_pointer(x2) value=x1_1:4`,
    cfg: {
      main: {
        blocks: [
      {
        address: "0x110e4",
        ir: `    0x000110e4: 0xfe010113  addi x2, x2, -32
      INT_ADD register[0x2:4] <- register[0x2:4], const[0xffffffe0:4]
    0x000110e8: 0x00112e23  sw x1, 28(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x1c:4]
      STORE unique[0x0:4], register[0x1:4]
    0x000110ec: 0x00812c23  sw x8, 24(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x18:4]
      STORE unique[0x0:4], register[0x8:4]
    0x000110f0: 0x02010413  addi x8, x2, 32
      INT_ADD register[0x8:4] <- register[0x2:4], const[0x20:4]
    0x000110f4: 0x01400513  addi x10, x0, 20
      COPY register[0xa:4] <- const[0x14:4]
    0x000110f8: 0xfea42a23  sw x10, -12(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff4:4]
      STORE unique[0x0:4], register[0xa:4]
    0x000110fc: 0x00200593  addi x11, x0, 2
      COPY register[0xb:4] <- const[0x2:4]
    0x00011100: 0xfeb42823  sw x11, -16(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff0:4]
      STORE unique[0x0:4], register[0xb:4]
    0x00011104: 0x00a00513  addi x10, x0, 10
      COPY register[0xa:4] <- const[0xa:4]
    0x00011108: 0xfea42623  sw x10, -20(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffec:4]
      STORE unique[0x0:4], register[0xa:4]
    0x0001110c: 0x00100513  addi x10, x0, 1
      COPY register[0xa:4] <- const[0x1:4]
    0x00011110: 0xfea42423  sw x10, -24(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffe8:4]
      STORE unique[0x0:4], register[0xa:4]
    0x00011114: 0xfe840513  addi x10, x8, -24
      INT_ADD register[0xa:4] <- register[0x8:4], const[0xffffffe8:4]
    0x00011118: 0x014000ef  jal x1, 0x1112c
      COPY register[0x1:4] <- const[0x1111c:4]
      CALL const[0x1112c:4]
    0x0001111c: 0x01c12083  lw x1, 28(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x1c:4]
      LOAD unique[0x4:4] <- unique[0x0:4]
      COPY register[0x1:4] <- unique[0x4:4]
    0x00011120: 0x01812403  lw x8, 24(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x18:4]
      LOAD unique[0x4:4] <- unique[0x0:4]
      COPY register[0x8:4] <- unique[0x4:4]
    0x00011124: 0x02010113  addi x2, x2, 32
      INT_ADD register[0x2:4] <- register[0x2:4], const[0x20:4]
    0x00011128: 0x00008067  jalr x0, 0(x1)
      COPY unique[0x0:4] <- register[0x1:4]
      INT_AND unique[0x4:4] <- unique[0x0:4], const[0xfffffffe:4]
      RETURN unique[0x4:4]`,
        annotations: ["stack: [sp-32..sp] frame", "slots: local_12(sp-12), local_16(sp-16), local_20(sp-20), local_24(sp-24)"],
      },
        ],
        edges: [],
      },
      parse_record: {
        blocks: [
      {
        address: "0x1112c",
        ir: `        0x0001112c: 0xfe010113  addi x2, x2, -32
          INT_ADD x2_1:4 <- x2_0:4, const[0xffffffe0:4]
        0x00011130: 0x00112e23  sw x1, 28(x2)
          INT_ADD u0_1:4 <- x2_1:4, const[0x1c:4]
          STORE u0_1:4, x1_0:4 [m0 -> m1]
        0x00011134: 0x00812c23  sw x8, 24(x2)
          INT_ADD u0_2:4 <- x2_1:4, const[0x18:4]
          STORE u0_2:4, x8_0:4 [m1 -> m2]
        0x00011138: 0x02010413  addi x8, x2, 32
          INT_ADD x8_1:4 <- x2_1:4, const[0x20:4]
        0x0001113c: 0xfea42a23  sw x10, -12(x8)
          INT_ADD u0_3:4 <- x8_1:4, const[0xfffffff4:4]
          STORE u0_3:4, x10_0:4 [m2 -> m3]
        0x00011140: 0xfeb42823  sw x11, -16(x8)
          INT_ADD u0_4:4 <- x8_1:4, const[0xfffffff0:4]
          STORE u0_4:4, x11_0:4 [m3 -> m4]
        0x00011144: 0x00000513  addi x10, x0, 0
          COPY x10_1:4 <- const[0x0:4]
        0x00011148: 0xfea42623  sw x10, -20(x8)
          INT_ADD u0_5:4 <- x8_1:4, const[0xffffffec:4]
          STORE u0_5:4, x10_1:4 [m4 -> m5]
        0x0001114c: 0xfea42423  sw x10, -24(x8)
          INT_ADD u0_6:4 <- x8_1:4, const[0xffffffe8:4]
          STORE u0_6:4, x10_1:4 [m5 -> m6]
        0x00011150: 0x0040006f  jal x0, 0x11154
          BRANCH const[0x11154:4]`,
        annotations: ["stack: [sp-32..sp] frame, [sp+28] saved ra, [sp+24] saved s0", "slots: local_20(sp-12), local_16(sp-16), local_12(sp-20), local_8(sp-24)"],
      },
      {
        address: "0x11154",
        label: "header",
        ir: `        MEM_PHI m7 <- 0x1112c:m6, 0x111a8:m10
        PHI x10_2:4 <- 0x1112c:x10_1:4, 0x111a8:x10_14:4
        PHI x11_1:4 <- 0x1112c:x11_0:4, 0x111a8:x11_8:4
        0x00011154: 0xfe842503  lw x10, -24(x8)
          INT_ADD u0_7:4 <- x8_1:4, const[0xffffffe8:4]
          LOAD x10_3:4 <- u0_7:4 [m7]
        0x00011158: 0xff042583  lw x11, -16(x8)
          INT_ADD u0_8:4 <- x8_1:4, const[0xfffffff0:4]
          LOAD x11_2:4 <- u0_8:4 [m7]
        0x0001115c: 0x04b55e63  bge x10, x11, 0x111b8
          INT_SLESS u0_1:1 <- x10_3:4, x11_2:4
          BOOL_NEGATE u4_1:1 <- u0_1:1
          CBRANCH const[0x111b8:4], u4_1:1`,
        annotations: ["reads: local_8(sp-24), local_16(sp-16)"],
      },
      {
        address: "0x111b8",
        label: "exit",
        ir: `        0x000111b8: 0xfec42503  lw x10, -20(x8)
          INT_ADD u0_9:4 <- x8_1:4, const[0xffffffec:4]
          LOAD x10_4:4 <- u0_9:4 [m7]
        0x000111bc: 0x01c12083  lw x1, 28(x2)
          INT_ADD u0_10:4 <- x2_1:4, const[0x1c:4]
          LOAD x1_1:4 <- u0_10:4 [m7]
        0x000111c0: 0x01812403  lw x8, 24(x2)
          INT_ADD u0_11:4 <- x2_1:4, const[0x18:4]
          LOAD x8_2:4 <- u0_11:4 [m7]
        0x000111c4: 0x02010113  addi x2, x2, 32
          INT_ADD x2_2:4 <- x2_1:4, const[0x20:4]
        0x000111c8: 0x00008067  jalr x0, 0(x1)
          COPY u0_12:4 <- x1_1:4
          INT_AND u4_1:4 <- u0_12:4, const[0xfffffffe:4]
          RETURN u4_1:4`,
        annotations: ["reads: local_12(sp-20)", "returns: x10 = local_12"],
      },
      {
        address: "0x11160",
        label: "connector",
        ir: `        0x00011160: 0x0040006f  jal x0, 0x11164
          BRANCH const[0x11164:4]`,
        annotations: ["(no stack access)"],
      },
      {
        address: "0x11164",
        label: "body",
        ir: `        0x00011164: 0xff442503  lw x10, -12(x8)
          INT_ADD u0_13:4 <- x8_1:4, const[0xfffffff4:4]
          LOAD x10_5:4 <- u0_13:4 [m7]
        0x00011168: 0xfe842583  lw x11, -24(x8)
          INT_ADD u0_14:4 <- x8_1:4, const[0xffffffe8:4]
          LOAD x11_3:4 <- u0_14:4 [m7]
        0x0001116c: 0x00359593  slli x11, x11, 3
          INT_LEFT x11_4:4 <- x11_3:4, const[0x3:4]
        0x00011170: 0x00b50533  add x10, x10, x11
          INT_ADD x10_6:4 <- x10_5:4, x11_4:4
        0x00011174: 0x00052583  lw x11, 0(x10)
          COPY u0_15:4 <- x10_6:4
          LOAD x11_5:4 <- u0_15:4 [m7]
        0x00011178: 0xfec42503  lw x10, -20(x8)
          INT_ADD u0_16:4 <- x8_1:4, const[0xffffffec:4]
          LOAD x10_7:4 <- u0_16:4 [m7]
        0x0001117c: 0x00b50533  add x10, x10, x11
          INT_ADD x10_8:4 <- x10_7:4, x11_5:4
        0x00011180: 0xfea42623  sw x10, -20(x8)
          INT_ADD u0_17:4 <- x8_1:4, const[0xffffffec:4]
          STORE u0_17:4, x10_8:4 [m7 -> m8]
        0x00011184: 0xff442503  lw x10, -12(x8)
          INT_ADD u0_18:4 <- x8_1:4, const[0xfffffff4:4]
          LOAD x10_9:4 <- u0_18:4 [m8]
        0x00011188: 0xfe842583  lw x11, -24(x8)
          INT_ADD u0_19:4 <- x8_1:4, const[0xffffffe8:4]
          LOAD x11_6:4 <- u0_19:4 [m8]
        0x0001118c: 0x00359593  slli x11, x11, 3
          INT_LEFT x11_7:4 <- x11_6:4, const[0x3:4]
        0x00011190: 0x00b50533  add x10, x10, x11
          INT_ADD x10_10:4 <- x10_9:4, x11_7:4
        0x00011194: 0x00452583  lw x11, 4(x10)
          INT_ADD u0_20:4 <- x10_10:4, const[0x4:4]
          LOAD x11_8:4 <- u0_20:4 [m8]
        0x00011198: 0xfec42503  lw x10, -20(x8)
          INT_ADD u0_21:4 <- x8_1:4, const[0xffffffec:4]
          LOAD x10_11:4 <- u0_21:4 [m8]
        0x0001119c: 0x00b50533  add x10, x10, x11
          INT_ADD x10_12:4 <- x10_11:4, x11_8:4
        0x000111a0: 0xfea42623  sw x10, -20(x8)
          INT_ADD u0_22:4 <- x8_1:4, const[0xffffffec:4]
          STORE u0_22:4, x10_12:4 [m8 -> m9]
        0x000111a4: 0x0040006f  jal x0, 0x111a8
          BRANCH const[0x111a8:4]`,
        annotations: ["reads: local_16(sp-16), local_8(sp-24), local_12(sp-20)", "writes: local_12(sp-20)"],
      },
      {
        address: "0x111a8",
        label: "latch",
        ir: `        0x000111a8: 0xfe842503  lw x10, -24(x8)
          INT_ADD u0_23:4 <- x8_1:4, const[0xffffffe8:4]
          LOAD x10_13:4 <- u0_23:4 [m9]
        0x000111ac: 0x00150513  addi x10, x10, 1
          INT_ADD x10_14:4 <- x10_13:4, const[0x1:4]
        0x000111b0: 0xfea42423  sw x10, -24(x8)
          INT_ADD u0_24:4 <- x8_1:4, const[0xffffffe8:4]
          STORE u0_24:4, x10_14:4 [m9 -> m10]
        0x000111b4: 0xfa1ff06f  jal x0, 0x11154
          BRANCH const[0x11154:4]`,
        annotations: ["reads: local_8(sp-24)", "writes: local_8(sp-24)"],
      }
        ],
        edges: [
      { source: "0x1112c", target: "0x11154", type: "normal" },
      { source: "0x11154", target: "0x111b8", label: "taken: i >= n", type: "normal" },
      { source: "0x11154", target: "0x11160", label: "fall: i < n", type: "normal" },
      { source: "0x11160", target: "0x11164", type: "normal" },
      { source: "0x11164", target: "0x111a8", type: "normal" },
      { source: "0x111a8", target: "0x11154", label: "back edge", type: "back" },
        ],
      },
    },
  },

  /* ── 10: MEMORY ANALYSIS ──────────────────────────────────────────────── */
  {
    id: "memory",
    number: 10,
    name: "Memory Analysis",
    phase: "analysis",
    description: "Each memory access is assigned to a partition: stack slots (local variables, argument homes, saved registers) and value-based partitions (pointer dereferences). parse_record has 8 partitions including two value partitions for struct field accesses at x10+0 and x10+4.",
    githubDir: "tiny_dec/analysis/memory",
    viewMode: "cfg",
    content: `  root: 0x110e4
  order: 0x110e4, 0x1112c
  pending:
  invalidated:
  externals:
    <none>
  call_graph:
    0x110e4@0x11118 -> internal 0x1112c name=parse_record
  functions:
    function 0x110e4 name=main frame_size=32 dynamic_sp=no partitions=6 accesses=8 pending=[]
    partitions:
      stack_slot -24 size=4 role=local accesses=1
        store 0x11110 block=0x110e4 size=4 value=x10_3:4 [m5 -> m6]
      stack_slot -20 size=4 role=local accesses=1
        store 0x11108 block=0x110e4 size=4 value=x10_2:4 [m4 -> m5]
      stack_slot -16 size=4 role=local accesses=1
        store 0x11100 block=0x110e4 size=4 value=x11_1:4 [m3 -> m4]
      stack_slot -12 size=4 role=local accesses=1
        store 0x110f8 block=0x110e4 size=4 value=x10_1:4 [m2 -> m3]
      stack_slot -8 size=4 role=saved_register(x8) accesses=2
        store 0x110ec block=0x110e4 size=4 value=x8_0:4 [m1 -> m2]
        load 0x11120 block=0x110e4 size=4 value=x8_2:4 [m7]
      stack_slot -4 size=4 role=saved_register(x1) accesses=2
        store 0x110e8 block=0x110e4 size=4 value=x1_0:4 [m0 -> m1]
        load 0x1111c block=0x110e4 size=4 value=x1_3:4 [m7]
    function 0x1112c name=parse_record frame_size=32 dynamic_sp=no partitions=8 accesses=23 pending=[]
    partitions:
      stack_slot -24 size=4 role=local accesses=6
        store 0x1114c block=0x1112c size=4 value=x10_1:4 [m5 -> m6]
        load 0x11154 block=0x11154 size=4 value=x10_3:4 [m7]
        load 0x11168 block=0x11164 size=4 value=x11_3:4 [m7]
        load 0x11188 block=0x11164 size=4 value=x11_6:4 [m8]
        load 0x111a8 block=0x111a8 size=4 value=x10_13:4 [m9]
        store 0x111b0 block=0x111a8 size=4 value=x10_14:4 [m9 -> m10]
      stack_slot -20 size=4 role=local accesses=6
        store 0x11148 block=0x1112c size=4 value=x10_1:4 [m4 -> m5]
        load 0x11178 block=0x11164 size=4 value=x10_7:4 [m7]
        store 0x11180 block=0x11164 size=4 value=x10_8:4 [m7 -> m8]
        load 0x11198 block=0x11164 size=4 value=x10_11:4 [m8]
        store 0x111a0 block=0x11164 size=4 value=x10_12:4 [m8 -> m9]
        load 0x111b8 block=0x111b8 size=4 value=x10_4:4 [m7]
      stack_slot -16 size=4 role=argument_home(x11) accesses=2
        store 0x11140 block=0x1112c size=4 value=x11_0:4 [m3 -> m4]
        load 0x11158 block=0x11154 size=4 value=x11_2:4 [m7]
      stack_slot -12 size=4 role=argument_home(x10) accesses=3
        store 0x1113c block=0x1112c size=4 value=x10_0:4 [m2 -> m3]
        load 0x11164 block=0x11164 size=4 value=x10_5:4 [m7]
        load 0x11184 block=0x11164 size=4 value=x10_9:4 [m8]
      stack_slot -8 size=4 role=saved_register(x8) accesses=2
        store 0x11134 block=0x1112c size=4 value=x8_0:4 [m1 -> m2]
        load 0x111c0 block=0x111b8 size=4 value=x8_2:4 [m7]
      stack_slot -4 size=4 role=saved_register(x1) accesses=2
        store 0x11130 block=0x1112c size=4 value=x1_0:4 [m0 -> m1]
        load 0x111bc block=0x111b8 size=4 value=x1_1:4 [m7]
      value x10_0:4 offset=+0 size=4 accesses=1
        load 0x11174 block=0x11164 size=4 value=x11_5:4 [m7]
      value x10_0:4 offset=+4 size=4 accesses=1
        load 0x11194 block=0x11164 size=4 value=x11_8:4 [m8]`,
    cfg: {
      main: {
        blocks: [
      {
        address: "0x110e4",
        ir: `    0x000110e4: 0xfe010113  addi x2, x2, -32
      INT_ADD register[0x2:4] <- register[0x2:4], const[0xffffffe0:4]
    0x000110e8: 0x00112e23  sw x1, 28(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x1c:4]
      STORE unique[0x0:4], register[0x1:4]
    0x000110ec: 0x00812c23  sw x8, 24(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x18:4]
      STORE unique[0x0:4], register[0x8:4]
    0x000110f0: 0x02010413  addi x8, x2, 32
      INT_ADD register[0x8:4] <- register[0x2:4], const[0x20:4]
    0x000110f4: 0x01400513  addi x10, x0, 20
      COPY register[0xa:4] <- const[0x14:4]
    0x000110f8: 0xfea42a23  sw x10, -12(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff4:4]
      STORE unique[0x0:4], register[0xa:4]
    0x000110fc: 0x00200593  addi x11, x0, 2
      COPY register[0xb:4] <- const[0x2:4]
    0x00011100: 0xfeb42823  sw x11, -16(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff0:4]
      STORE unique[0x0:4], register[0xb:4]
    0x00011104: 0x00a00513  addi x10, x0, 10
      COPY register[0xa:4] <- const[0xa:4]
    0x00011108: 0xfea42623  sw x10, -20(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffec:4]
      STORE unique[0x0:4], register[0xa:4]
    0x0001110c: 0x00100513  addi x10, x0, 1
      COPY register[0xa:4] <- const[0x1:4]
    0x00011110: 0xfea42423  sw x10, -24(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffe8:4]
      STORE unique[0x0:4], register[0xa:4]
    0x00011114: 0xfe840513  addi x10, x8, -24
      INT_ADD register[0xa:4] <- register[0x8:4], const[0xffffffe8:4]
    0x00011118: 0x014000ef  jal x1, 0x1112c
      COPY register[0x1:4] <- const[0x1111c:4]
      CALL const[0x1112c:4]
    0x0001111c: 0x01c12083  lw x1, 28(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x1c:4]
      LOAD unique[0x4:4] <- unique[0x0:4]
      COPY register[0x1:4] <- unique[0x4:4]
    0x00011120: 0x01812403  lw x8, 24(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x18:4]
      LOAD unique[0x4:4] <- unique[0x0:4]
      COPY register[0x8:4] <- unique[0x4:4]
    0x00011124: 0x02010113  addi x2, x2, 32
      INT_ADD register[0x2:4] <- register[0x2:4], const[0x20:4]
    0x00011128: 0x00008067  jalr x0, 0(x1)
      COPY unique[0x0:4] <- register[0x1:4]
      INT_AND unique[0x4:4] <- unique[0x0:4], const[0xfffffffe:4]
      RETURN unique[0x4:4]`,
        annotations: ["partitions: P0={local_12,local_16} args, P1={local_20,local_24} locals"],
      },
        ],
        edges: [],
      },
      parse_record: {
        blocks: [
      {
        address: "0x1112c",
        ir: `        0x0001112c: 0xfe010113  addi x2, x2, -32
          INT_ADD x2_1:4 <- x2_0:4, const[0xffffffe0:4]
        0x00011130: 0x00112e23  sw x1, 28(x2)
          INT_ADD u0_1:4 <- x2_1:4, const[0x1c:4]
          STORE u0_1:4, x1_0:4 [m0 -> m1]
        0x00011134: 0x00812c23  sw x8, 24(x2)
          INT_ADD u0_2:4 <- x2_1:4, const[0x18:4]
          STORE u0_2:4, x8_0:4 [m1 -> m2]
        0x00011138: 0x02010413  addi x8, x2, 32
          INT_ADD x8_1:4 <- x2_1:4, const[0x20:4]
        0x0001113c: 0xfea42a23  sw x10, -12(x8)
          INT_ADD u0_3:4 <- x8_1:4, const[0xfffffff4:4]
          STORE u0_3:4, x10_0:4 [m2 -> m3]
        0x00011140: 0xfeb42823  sw x11, -16(x8)
          INT_ADD u0_4:4 <- x8_1:4, const[0xfffffff0:4]
          STORE u0_4:4, x11_0:4 [m3 -> m4]
        0x00011144: 0x00000513  addi x10, x0, 0
          COPY x10_1:4 <- const[0x0:4]
        0x00011148: 0xfea42623  sw x10, -20(x8)
          INT_ADD u0_5:4 <- x8_1:4, const[0xffffffec:4]
          STORE u0_5:4, x10_1:4 [m4 -> m5]
        0x0001114c: 0xfea42423  sw x10, -24(x8)
          INT_ADD u0_6:4 <- x8_1:4, const[0xffffffe8:4]
          STORE u0_6:4, x10_1:4 [m5 -> m6]
        0x00011150: 0x0040006f  jal x0, 0x11154
          BRANCH const[0x11154:4]`,
        annotations: ["partition P0: {local_20, local_16}, function args (base, count)", "partition P1: {local_12, local_8}, loop vars (sum, i)", "partition P2: {saved_ra, saved_s0}, callee-saved"],
      },
      {
        address: "0x11154",
        ir: `        MEM_PHI m7 <- 0x1112c:m6, 0x111a8:m10
        PHI x10_2:4 <- 0x1112c:x10_1:4, 0x111a8:x10_14:4
        PHI x11_1:4 <- 0x1112c:x11_0:4, 0x111a8:x11_8:4
        0x00011154: 0xfe842503  lw x10, -24(x8)
          INT_ADD u0_7:4 <- x8_1:4, const[0xffffffe8:4]
          LOAD x10_3:4 <- u0_7:4 [m7]
        0x00011158: 0xff042583  lw x11, -16(x8)
          INT_ADD u0_8:4 <- x8_1:4, const[0xfffffff0:4]
          LOAD x11_2:4 <- u0_8:4 [m7]
        0x0001115c: 0x04b55e63  bge x10, x11, 0x111b8
          INT_SLESS u0_1:1 <- x10_3:4, x11_2:4
          BOOL_NEGATE u4_1:1 <- u0_1:1
          CBRANCH const[0x111b8:4], u4_1:1`,
        annotations: ["reads: P1.local_8, P0.local_16"],
      },
      {
        address: "0x111b8",
        ir: `        0x000111b8: 0xfec42503  lw x10, -20(x8)
          INT_ADD u0_9:4 <- x8_1:4, const[0xffffffec:4]
          LOAD x10_4:4 <- u0_9:4 [m7]
        0x000111bc: 0x01c12083  lw x1, 28(x2)
          INT_ADD u0_10:4 <- x2_1:4, const[0x1c:4]
          LOAD x1_1:4 <- u0_10:4 [m7]
        0x000111c0: 0x01812403  lw x8, 24(x2)
          INT_ADD u0_11:4 <- x2_1:4, const[0x18:4]
          LOAD x8_2:4 <- u0_11:4 [m7]
        0x000111c4: 0x02010113  addi x2, x2, 32
          INT_ADD x2_2:4 <- x2_1:4, const[0x20:4]
        0x000111c8: 0x00008067  jalr x0, 0(x1)
          COPY u0_12:4 <- x1_1:4
          INT_AND u4_1:4 <- u0_12:4, const[0xfffffffe:4]
          RETURN u4_1:4`,
        annotations: ["reads: P1.local_12 → return value"],
      },
      {
        address: "0x11160",
        ir: `        0x00011160: 0x0040006f  jal x0, 0x11164
          BRANCH const[0x11164:4]`,
        annotations: ["(no memory partition access)"],
      },
      {
        address: "0x11164",
        ir: `        0x00011164: 0xff442503  lw x10, -12(x8)
          INT_ADD u0_13:4 <- x8_1:4, const[0xfffffff4:4]
          LOAD x10_5:4 <- u0_13:4 [m7]
        0x00011168: 0xfe842583  lw x11, -24(x8)
          INT_ADD u0_14:4 <- x8_1:4, const[0xffffffe8:4]
          LOAD x11_3:4 <- u0_14:4 [m7]
        0x0001116c: 0x00359593  slli x11, x11, 3
          INT_LEFT x11_4:4 <- x11_3:4, const[0x3:4]
        0x00011170: 0x00b50533  add x10, x10, x11
          INT_ADD x10_6:4 <- x10_5:4, x11_4:4
        0x00011174: 0x00052583  lw x11, 0(x10)
          COPY u0_15:4 <- x10_6:4
          LOAD x11_5:4 <- u0_15:4 [m7]
        0x00011178: 0xfec42503  lw x10, -20(x8)
          INT_ADD u0_16:4 <- x8_1:4, const[0xffffffec:4]
          LOAD x10_7:4 <- u0_16:4 [m7]
        0x0001117c: 0x00b50533  add x10, x10, x11
          INT_ADD x10_8:4 <- x10_7:4, x11_5:4
        0x00011180: 0xfea42623  sw x10, -20(x8)
          INT_ADD u0_17:4 <- x8_1:4, const[0xffffffec:4]
          STORE u0_17:4, x10_8:4 [m7 -> m8]
        0x00011184: 0xff442503  lw x10, -12(x8)
          INT_ADD u0_18:4 <- x8_1:4, const[0xfffffff4:4]
          LOAD x10_9:4 <- u0_18:4 [m8]
        0x00011188: 0xfe842583  lw x11, -24(x8)
          INT_ADD u0_19:4 <- x8_1:4, const[0xffffffe8:4]
          LOAD x11_6:4 <- u0_19:4 [m8]
        0x0001118c: 0x00359593  slli x11, x11, 3
          INT_LEFT x11_7:4 <- x11_6:4, const[0x3:4]
        0x00011190: 0x00b50533  add x10, x10, x11
          INT_ADD x10_10:4 <- x10_9:4, x11_7:4
        0x00011194: 0x00452583  lw x11, 4(x10)
          INT_ADD u0_20:4 <- x10_10:4, const[0x4:4]
          LOAD x11_8:4 <- u0_20:4 [m8]
        0x00011198: 0xfec42503  lw x10, -20(x8)
          INT_ADD u0_21:4 <- x8_1:4, const[0xffffffec:4]
          LOAD x10_11:4 <- u0_21:4 [m8]
        0x0001119c: 0x00b50533  add x10, x10, x11
          INT_ADD x10_12:4 <- x10_11:4, x11_8:4
        0x000111a0: 0xfea42623  sw x10, -20(x8)
          INT_ADD u0_22:4 <- x8_1:4, const[0xffffffec:4]
          STORE u0_22:4, x10_12:4 [m8 -> m9]
        0x000111a4: 0x0040006f  jal x0, 0x111a8
          BRANCH const[0x111a8:4]`,
        annotations: ["reads: P0.local_16, P1.local_8, P1.local_12  via pointer deref", "writes: P1.local_12"],
      },
      {
        address: "0x111a8",
        ir: `        0x000111a8: 0xfe842503  lw x10, -24(x8)
          INT_ADD u0_23:4 <- x8_1:4, const[0xffffffe8:4]
          LOAD x10_13:4 <- u0_23:4 [m9]
        0x000111ac: 0x00150513  addi x10, x10, 1
          INT_ADD x10_14:4 <- x10_13:4, const[0x1:4]
        0x000111b0: 0xfea42423  sw x10, -24(x8)
          INT_ADD u0_24:4 <- x8_1:4, const[0xffffffe8:4]
          STORE u0_24:4, x10_14:4 [m9 -> m10]
        0x000111b4: 0xfa1ff06f  jal x0, 0x11154
          BRANCH const[0x11154:4]`,
        annotations: ["reads: P1.local_8", "writes: P1.local_8 (i++)"],
      }
        ],
        edges: [
      { source: "0x1112c", target: "0x11154", type: "normal" },
      { source: "0x11154", target: "0x111b8", label: "taken: i >= n", type: "normal" },
      { source: "0x11154", target: "0x11160", label: "fall: i < n", type: "normal" },
      { source: "0x11160", target: "0x11164", type: "normal" },
      { source: "0x11164", target: "0x111a8", type: "normal" },
      { source: "0x111a8", target: "0x11154", label: "back edge", type: "back" },
        ],
      },
    },
  },

  /* ── 11: SCALAR TYPES ──────────────────────────────────────────────── */
  {
    id: "scalar_types",
    number: 11,
    name: "Scalar Types",
    phase: "analysis",
    description: "Type inference assigns int:4, pointer:4, or word:4 to every SSA value and memory partition. In parse_record, x10_0 is typed as pointer:4 because it is used as a base for memory loads, while loop counters are int:4.",
    githubDir: "tiny_dec/analysis/types",
    viewMode: "cfg",
    content: `  root: 0x110e4
  order: 0x110e4, 0x1112c
  pending:
  invalidated:
  externals:
    <none>
  call_graph:
    0x110e4@0x11118 -> internal 0x1112c name=parse_record
  functions:
    function 0x110e4 name=main frame_size=32 dynamic_sp=no typed_partitions=5 typed_values=9 pending=[]
    partitions:
      stack_slot -24 size=4 role=local type=int:4
      stack_slot -20 size=4 role=local type=int:4
      stack_slot -16 size=4 role=local type=int:4
      stack_slot -12 size=4 role=local type=int:4
      stack_slot -4 size=4 role=saved_register(x1) type=word:4
    values:
      x1_0:4 type=word:4
      x1_1:4 type=int:4
      x1_3:4 type=word:4
      x10_1:4 type=int:4
      x10_2:4 type=int:4
      x10_3:4 type=int:4
      x11_1:4 type=int:4
      u0_9:4 type=word:4
      u4_1:4 type=word:4
    function 0x1112c name=parse_record frame_size=32 dynamic_sp=no typed_partitions=7 typed_values=32 pending=[]
    partitions:
      stack_slot -24 size=4 role=local type=int:4
      stack_slot -20 size=4 role=local type=int:4
      stack_slot -16 size=4 role=argument_home(x11) type=int:4
      stack_slot -12 size=4 role=argument_home(x10) type=pointer:4
      stack_slot -4 size=4 role=saved_register(x1) type=word:4
      value x10_0:4 offset=+0 size=4 type=int:4
      value x10_0:4 offset=+4 size=4 type=int:4
    values:
      x1_0:4 type=word:4
      x1_1:4 type=word:4
      x10_0:4 type=pointer:4
      x10_1:4 type=int:4
      x10_2:4 type=int:4
      x10_3:4 type=int:4
      x10_4:4 type=int:4
      x10_5:4 type=pointer:4
      x10_6:4 type=pointer:4
      x10_7:4 type=int:4
      x10_8:4 type=int:4
      x10_9:4 type=pointer:4
      x10_10:4 type=pointer:4
      x10_11:4 type=int:4
      x10_12:4 type=int:4
      x10_13:4 type=int:4
      x10_14:4 type=int:4
      x11_0:4 type=int:4
      x11_1:4 type=int:4
      x11_2:4 type=int:4
      x11_3:4 type=int:4
      x11_4:4 type=int:4
      x11_5:4 type=int:4
      x11_6:4 type=int:4
      x11_7:4 type=int:4
      x11_8:4 type=int:4
      u0_1:1 type=bool:1
      u0_12:4 type=word:4
      u0_15:4 type=pointer:4
      u0_20:4 type=pointer:4
      u4_1:1 type=bool:1
      u4_1:4 type=word:4`,
    cfg: {
      main: {
        blocks: [
      {
        address: "0x110e4",
        ir: `    0x000110e4: 0xfe010113  addi x2, x2, -32
      INT_ADD register[0x2:4] <- register[0x2:4], const[0xffffffe0:4]
    0x000110e8: 0x00112e23  sw x1, 28(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x1c:4]
      STORE unique[0x0:4], register[0x1:4]
    0x000110ec: 0x00812c23  sw x8, 24(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x18:4]
      STORE unique[0x0:4], register[0x8:4]
    0x000110f0: 0x02010413  addi x8, x2, 32
      INT_ADD register[0x8:4] <- register[0x2:4], const[0x20:4]
    0x000110f4: 0x01400513  addi x10, x0, 20
      COPY register[0xa:4] <- const[0x14:4]
    0x000110f8: 0xfea42a23  sw x10, -12(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff4:4]
      STORE unique[0x0:4], register[0xa:4]
    0x000110fc: 0x00200593  addi x11, x0, 2
      COPY register[0xb:4] <- const[0x2:4]
    0x00011100: 0xfeb42823  sw x11, -16(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff0:4]
      STORE unique[0x0:4], register[0xb:4]
    0x00011104: 0x00a00513  addi x10, x0, 10
      COPY register[0xa:4] <- const[0xa:4]
    0x00011108: 0xfea42623  sw x10, -20(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffec:4]
      STORE unique[0x0:4], register[0xa:4]
    0x0001110c: 0x00100513  addi x10, x0, 1
      COPY register[0xa:4] <- const[0x1:4]
    0x00011110: 0xfea42423  sw x10, -24(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffe8:4]
      STORE unique[0x0:4], register[0xa:4]
    0x00011114: 0xfe840513  addi x10, x8, -24
      INT_ADD register[0xa:4] <- register[0x8:4], const[0xffffffe8:4]
    0x00011118: 0x014000ef  jal x1, 0x1112c
      COPY register[0x1:4] <- const[0x1111c:4]
      CALL const[0x1112c:4]
    0x0001111c: 0x01c12083  lw x1, 28(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x1c:4]
      LOAD unique[0x4:4] <- unique[0x0:4]
      COPY register[0x1:4] <- unique[0x4:4]
    0x00011120: 0x01812403  lw x8, 24(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x18:4]
      LOAD unique[0x4:4] <- unique[0x0:4]
      COPY register[0x8:4] <- unique[0x4:4]
    0x00011124: 0x02010113  addi x2, x2, 32
      INT_ADD register[0x2:4] <- register[0x2:4], const[0x20:4]
    0x00011128: 0x00008067  jalr x0, 0(x1)
      COPY unique[0x0:4] <- register[0x1:4]
      INT_AND unique[0x4:4] <- unique[0x0:4], const[0xfffffffe:4]
      RETURN unique[0x4:4]`,
        annotations: ["types: x10_4:ptr4, x11_1:int4 → parse_record args"],
      },
        ],
        edges: [],
      },
      parse_record: {
        blocks: [
      {
        address: "0x1112c",
        ir: `        0x0001112c: 0xfe010113  addi x2, x2, -32
          INT_ADD x2_1:4 <- x2_0:4, const[0xffffffe0:4]
        0x00011130: 0x00112e23  sw x1, 28(x2)
          INT_ADD u0_1:4 <- x2_1:4, const[0x1c:4]
          STORE u0_1:4, x1_0:4 [m0 -> m1]
        0x00011134: 0x00812c23  sw x8, 24(x2)
          INT_ADD u0_2:4 <- x2_1:4, const[0x18:4]
          STORE u0_2:4, x8_0:4 [m1 -> m2]
        0x00011138: 0x02010413  addi x8, x2, 32
          INT_ADD x8_1:4 <- x2_1:4, const[0x20:4]
        0x0001113c: 0xfea42a23  sw x10, -12(x8)
          INT_ADD u0_3:4 <- x8_1:4, const[0xfffffff4:4]
          STORE u0_3:4, x10_0:4 [m2 -> m3]
        0x00011140: 0xfeb42823  sw x11, -16(x8)
          INT_ADD u0_4:4 <- x8_1:4, const[0xfffffff0:4]
          STORE u0_4:4, x11_0:4 [m3 -> m4]
        0x00011144: 0x00000513  addi x10, x0, 0
          COPY x10_1:4 <- const[0x0:4]
        0x00011148: 0xfea42623  sw x10, -20(x8)
          INT_ADD u0_5:4 <- x8_1:4, const[0xffffffec:4]
          STORE u0_5:4, x10_1:4 [m4 -> m5]
        0x0001114c: 0xfea42423  sw x10, -24(x8)
          INT_ADD u0_6:4 <- x8_1:4, const[0xffffffe8:4]
          STORE u0_6:4, x10_1:4 [m5 -> m6]
        0x00011150: 0x0040006f  jal x0, 0x11154
          BRANCH const[0x11154:4]`,
        annotations: ["types: x10_0:ptr4 (base addr), x11_0:int4 (count)", "x8_1:ptr4 (frame ptr), x2_1:ptr4 (stack ptr)"],
      },
      {
        address: "0x11154",
        ir: `        MEM_PHI m7 <- 0x1112c:m6, 0x111a8:m10
        PHI x10_2:4 <- 0x1112c:x10_1:4, 0x111a8:x10_14:4
        PHI x11_1:4 <- 0x1112c:x11_0:4, 0x111a8:x11_8:4
        0x00011154: 0xfe842503  lw x10, -24(x8)
          INT_ADD u0_7:4 <- x8_1:4, const[0xffffffe8:4]
          LOAD x10_3:4 <- u0_7:4 [m7]
        0x00011158: 0xff042583  lw x11, -16(x8)
          INT_ADD u0_8:4 <- x8_1:4, const[0xfffffff0:4]
          LOAD x11_2:4 <- u0_8:4 [m7]
        0x0001115c: 0x04b55e63  bge x10, x11, 0x111b8
          INT_SLESS u0_1:1 <- x10_3:4, x11_2:4
          BOOL_NEGATE u4_1:1 <- u0_1:1
          CBRANCH const[0x111b8:4], u4_1:1`,
        annotations: ["types: x10_2:ptr4 (PHI), x15_2:int4 (PHI)", "comparison: x15_2:int4 <s x11_0:int4"],
      },
      {
        address: "0x111b8",
        ir: `        0x000111b8: 0xfec42503  lw x10, -20(x8)
          INT_ADD u0_9:4 <- x8_1:4, const[0xffffffec:4]
          LOAD x10_4:4 <- u0_9:4 [m7]
        0x000111bc: 0x01c12083  lw x1, 28(x2)
          INT_ADD u0_10:4 <- x2_1:4, const[0x1c:4]
          LOAD x1_1:4 <- u0_10:4 [m7]
        0x000111c0: 0x01812403  lw x8, 24(x2)
          INT_ADD u0_11:4 <- x2_1:4, const[0x18:4]
          LOAD x8_2:4 <- u0_11:4 [m7]
        0x000111c4: 0x02010113  addi x2, x2, 32
          INT_ADD x2_2:4 <- x2_1:4, const[0x20:4]
        0x000111c8: 0x00008067  jalr x0, 0(x1)
          COPY u0_12:4 <- x1_1:4
          INT_AND u4_1:4 <- u0_12:4, const[0xfffffffe:4]
          RETURN u4_1:4`,
        annotations: ["return type: x15_2:uint4 → uint32_t"],
      },
      {
        address: "0x11160",
        ir: `        0x00011160: 0x0040006f  jal x0, 0x11164
          BRANCH const[0x11164:4]`,
        annotations: ["(pass-through, no new types)"],
      },
      {
        address: "0x11164",
        ir: `        0x00011164: 0xff442503  lw x10, -12(x8)
          INT_ADD u0_13:4 <- x8_1:4, const[0xfffffff4:4]
          LOAD x10_5:4 <- u0_13:4 [m7]
        0x00011168: 0xfe842583  lw x11, -24(x8)
          INT_ADD u0_14:4 <- x8_1:4, const[0xffffffe8:4]
          LOAD x11_3:4 <- u0_14:4 [m7]
        0x0001116c: 0x00359593  slli x11, x11, 3
          INT_LEFT x11_4:4 <- x11_3:4, const[0x3:4]
        0x00011170: 0x00b50533  add x10, x10, x11
          INT_ADD x10_6:4 <- x10_5:4, x11_4:4
        0x00011174: 0x00052583  lw x11, 0(x10)
          COPY u0_15:4 <- x10_6:4
          LOAD x11_5:4 <- u0_15:4 [m7]
        0x00011178: 0xfec42503  lw x10, -20(x8)
          INT_ADD u0_16:4 <- x8_1:4, const[0xffffffec:4]
          LOAD x10_7:4 <- u0_16:4 [m7]
        0x0001117c: 0x00b50533  add x10, x10, x11
          INT_ADD x10_8:4 <- x10_7:4, x11_5:4
        0x00011180: 0xfea42623  sw x10, -20(x8)
          INT_ADD u0_17:4 <- x8_1:4, const[0xffffffec:4]
          STORE u0_17:4, x10_8:4 [m7 -> m8]
        0x00011184: 0xff442503  lw x10, -12(x8)
          INT_ADD u0_18:4 <- x8_1:4, const[0xfffffff4:4]
          LOAD x10_9:4 <- u0_18:4 [m8]
        0x00011188: 0xfe842583  lw x11, -24(x8)
          INT_ADD u0_19:4 <- x8_1:4, const[0xffffffe8:4]
          LOAD x11_6:4 <- u0_19:4 [m8]
        0x0001118c: 0x00359593  slli x11, x11, 3
          INT_LEFT x11_7:4 <- x11_6:4, const[0x3:4]
        0x00011190: 0x00b50533  add x10, x10, x11
          INT_ADD x10_10:4 <- x10_9:4, x11_7:4
        0x00011194: 0x00452583  lw x11, 4(x10)
          INT_ADD u0_20:4 <- x10_10:4, const[0x4:4]
          LOAD x11_8:4 <- u0_20:4 [m8]
        0x00011198: 0xfec42503  lw x10, -20(x8)
          INT_ADD u0_21:4 <- x8_1:4, const[0xffffffec:4]
          LOAD x10_11:4 <- u0_21:4 [m8]
        0x0001119c: 0x00b50533  add x10, x10, x11
          INT_ADD x10_12:4 <- x10_11:4, x11_8:4
        0x000111a0: 0xfea42623  sw x10, -20(x8)
          INT_ADD u0_22:4 <- x8_1:4, const[0xffffffec:4]
          STORE u0_22:4, x10_12:4 [m8 -> m9]
        0x000111a4: 0x0040006f  jal x0, 0x111a8
          BRANCH const[0x111a8:4]`,
        annotations: ["types: loads via x10_2:ptr4 → int4", "x15_5:int4 (field_0), x15_7:int4 (field_4)", "x15_8:int4 (sum accumulation)"],
      },
      {
        address: "0x111a8",
        ir: `        0x000111a8: 0xfe842503  lw x10, -24(x8)
          INT_ADD u0_23:4 <- x8_1:4, const[0xffffffe8:4]
          LOAD x10_13:4 <- u0_23:4 [m9]
        0x000111ac: 0x00150513  addi x10, x10, 1
          INT_ADD x10_14:4 <- x10_13:4, const[0x1:4]
        0x000111b0: 0xfea42423  sw x10, -24(x8)
          INT_ADD u0_24:4 <- x8_1:4, const[0xffffffe8:4]
          STORE u0_24:4, x10_14:4 [m9 -> m10]
        0x000111b4: 0xfa1ff06f  jal x0, 0x11154
          BRANCH const[0x11154:4]`,
        annotations: ["types: x15_9:int4 (i + 1)"],
      }
        ],
        edges: [
      { source: "0x1112c", target: "0x11154", type: "normal" },
      { source: "0x11154", target: "0x111b8", label: "taken: i >= n", type: "normal" },
      { source: "0x11154", target: "0x11160", label: "fall: i < n", type: "normal" },
      { source: "0x11160", target: "0x11164", type: "normal" },
      { source: "0x11164", target: "0x111a8", type: "normal" },
      { source: "0x111a8", target: "0x11154", label: "back edge", type: "back" },
        ],
      },
    },
  },

  /* ── 12: AGGREGATE TYPES ──────────────────────────────────────────────── */
  {
    id: "aggregate_types",
    number: 12,
    name: "Aggregate Types",
    phase: "analysis",
    description: "Strided pointer accesses reveal aggregate structure. parse_record accesses x10_0 at offsets +0 and +4 with stride 8 (from slli x11, x11, 3), revealing a struct with two 4-byte integer fields.",
    githubDir: "tiny_dec/analysis/types",
    viewMode: "cfg",
    content: `  root: 0x110e4
  order: 0x110e4, 0x1112c
  pending:
  invalidated:
  externals:
    <none>
  call_graph:
    0x110e4@0x11118 -> internal 0x1112c name=parse_record
  functions:
    function 0x110e4 name=main frame_size=32 dynamic_sp=no aggregates=0 pending=[]
    aggregates:
      <none>
    function 0x1112c name=parse_record frame_size=32 dynamic_sp=no aggregates=1 pending=[]
    aggregates:
      aggregate pointer x10_0:4 stride=? fields=2
        field +0 size=4 type=int:4 partitions=[value x10_0:4 offset=+0 size=4]
        field +4 size=4 type=int:4 partitions=[value x10_0:4 offset=+4 size=4]`,
    cfg: {
      main: {
        blocks: [
      {
        address: "0x110e4",
        ir: `    0x000110e4: 0xfe010113  addi x2, x2, -32
      INT_ADD register[0x2:4] <- register[0x2:4], const[0xffffffe0:4]
    0x000110e8: 0x00112e23  sw x1, 28(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x1c:4]
      STORE unique[0x0:4], register[0x1:4]
    0x000110ec: 0x00812c23  sw x8, 24(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x18:4]
      STORE unique[0x0:4], register[0x8:4]
    0x000110f0: 0x02010413  addi x8, x2, 32
      INT_ADD register[0x8:4] <- register[0x2:4], const[0x20:4]
    0x000110f4: 0x01400513  addi x10, x0, 20
      COPY register[0xa:4] <- const[0x14:4]
    0x000110f8: 0xfea42a23  sw x10, -12(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff4:4]
      STORE unique[0x0:4], register[0xa:4]
    0x000110fc: 0x00200593  addi x11, x0, 2
      COPY register[0xb:4] <- const[0x2:4]
    0x00011100: 0xfeb42823  sw x11, -16(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff0:4]
      STORE unique[0x0:4], register[0xb:4]
    0x00011104: 0x00a00513  addi x10, x0, 10
      COPY register[0xa:4] <- const[0xa:4]
    0x00011108: 0xfea42623  sw x10, -20(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffec:4]
      STORE unique[0x0:4], register[0xa:4]
    0x0001110c: 0x00100513  addi x10, x0, 1
      COPY register[0xa:4] <- const[0x1:4]
    0x00011110: 0xfea42423  sw x10, -24(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffe8:4]
      STORE unique[0x0:4], register[0xa:4]
    0x00011114: 0xfe840513  addi x10, x8, -24
      INT_ADD register[0xa:4] <- register[0x8:4], const[0xffffffe8:4]
    0x00011118: 0x014000ef  jal x1, 0x1112c
      COPY register[0x1:4] <- const[0x1111c:4]
      CALL const[0x1112c:4]
    0x0001111c: 0x01c12083  lw x1, 28(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x1c:4]
      LOAD unique[0x4:4] <- unique[0x0:4]
      COPY register[0x1:4] <- unique[0x4:4]
    0x00011120: 0x01812403  lw x8, 24(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x18:4]
      LOAD unique[0x4:4] <- unique[0x0:4]
      COPY register[0x8:4] <- unique[0x4:4]
    0x00011124: 0x02010113  addi x2, x2, 32
      INT_ADD register[0x2:4] <- register[0x2:4], const[0x20:4]
    0x00011128: 0x00008067  jalr x0, 0(x1)
      COPY unique[0x0:4] <- register[0x1:4]
      INT_AND unique[0x4:4] <- unique[0x0:4], const[0xfffffffe:4]
      RETURN unique[0x4:4]`,
        annotations: ["local_20 typed: agg_8[...] (array of agg_8)"],
      },
        ],
        edges: [],
      },
      parse_record: {
        blocks: [
      {
        address: "0x1112c",
        ir: `        0x0001112c: 0xfe010113  addi x2, x2, -32
          INT_ADD x2_1:4 <- x2_0:4, const[0xffffffe0:4]
        0x00011130: 0x00112e23  sw x1, 28(x2)
          INT_ADD u0_1:4 <- x2_1:4, const[0x1c:4]
          STORE u0_1:4, x1_0:4 [m0 -> m1]
        0x00011134: 0x00812c23  sw x8, 24(x2)
          INT_ADD u0_2:4 <- x2_1:4, const[0x18:4]
          STORE u0_2:4, x8_0:4 [m1 -> m2]
        0x00011138: 0x02010413  addi x8, x2, 32
          INT_ADD x8_1:4 <- x2_1:4, const[0x20:4]
        0x0001113c: 0xfea42a23  sw x10, -12(x8)
          INT_ADD u0_3:4 <- x8_1:4, const[0xfffffff4:4]
          STORE u0_3:4, x10_0:4 [m2 -> m3]
        0x00011140: 0xfeb42823  sw x11, -16(x8)
          INT_ADD u0_4:4 <- x8_1:4, const[0xfffffff0:4]
          STORE u0_4:4, x11_0:4 [m3 -> m4]
        0x00011144: 0x00000513  addi x10, x0, 0
          COPY x10_1:4 <- const[0x0:4]
        0x00011148: 0xfea42623  sw x10, -20(x8)
          INT_ADD u0_5:4 <- x8_1:4, const[0xffffffec:4]
          STORE u0_5:4, x10_1:4 [m4 -> m5]
        0x0001114c: 0xfea42423  sw x10, -24(x8)
          INT_ADD u0_6:4 <- x8_1:4, const[0xffffffe8:4]
          STORE u0_6:4, x10_1:4 [m5 -> m6]
        0x00011150: 0x0040006f  jal x0, 0x11154
          BRANCH const[0x11154:4]`,
        annotations: ["x10_0 typed: agg_8* (pointer to 8-byte struct)", "discovered: agg_8 { field_0: int32, field_4: int32 }"],
      },
      {
        address: "0x11154",
        ir: `        MEM_PHI m7 <- 0x1112c:m6, 0x111a8:m10
        PHI x10_2:4 <- 0x1112c:x10_1:4, 0x111a8:x10_14:4
        PHI x11_1:4 <- 0x1112c:x11_0:4, 0x111a8:x11_8:4
        0x00011154: 0xfe842503  lw x10, -24(x8)
          INT_ADD u0_7:4 <- x8_1:4, const[0xffffffe8:4]
          LOAD x10_3:4 <- u0_7:4 [m7]
        0x00011158: 0xff042583  lw x11, -16(x8)
          INT_ADD u0_8:4 <- x8_1:4, const[0xfffffff0:4]
          LOAD x11_2:4 <- u0_8:4 [m7]
        0x0001115c: 0x04b55e63  bge x10, x11, 0x111b8
          INT_SLESS u0_1:1 <- x10_3:4, x11_2:4
          BOOL_NEGATE u4_1:1 <- u0_1:1
          CBRANCH const[0x111b8:4], u4_1:1`,
        annotations: ["x10_2: agg_8* (loop iterator pointer)"],
      },
      {
        address: "0x111b8",
        ir: `        0x000111b8: 0xfec42503  lw x10, -20(x8)
          INT_ADD u0_9:4 <- x8_1:4, const[0xffffffec:4]
          LOAD x10_4:4 <- u0_9:4 [m7]
        0x000111bc: 0x01c12083  lw x1, 28(x2)
          INT_ADD u0_10:4 <- x2_1:4, const[0x1c:4]
          LOAD x1_1:4 <- u0_10:4 [m7]
        0x000111c0: 0x01812403  lw x8, 24(x2)
          INT_ADD u0_11:4 <- x2_1:4, const[0x18:4]
          LOAD x8_2:4 <- u0_11:4 [m7]
        0x000111c4: 0x02010113  addi x2, x2, 32
          INT_ADD x2_2:4 <- x2_1:4, const[0x20:4]
        0x000111c8: 0x00008067  jalr x0, 0(x1)
          COPY u0_12:4 <- x1_1:4
          INT_AND u4_1:4 <- u0_12:4, const[0xfffffffe:4]
          RETURN u4_1:4`,
        annotations: ["(no aggregate access)"],
      },
      {
        address: "0x11160",
        ir: `        0x00011160: 0x0040006f  jal x0, 0x11164
          BRANCH const[0x11164:4]`,
        annotations: ["(no aggregate access)"],
      },
      {
        address: "0x11164",
        ir: `        0x00011164: 0xff442503  lw x10, -12(x8)
          INT_ADD u0_13:4 <- x8_1:4, const[0xfffffff4:4]
          LOAD x10_5:4 <- u0_13:4 [m7]
        0x00011168: 0xfe842583  lw x11, -24(x8)
          INT_ADD u0_14:4 <- x8_1:4, const[0xffffffe8:4]
          LOAD x11_3:4 <- u0_14:4 [m7]
        0x0001116c: 0x00359593  slli x11, x11, 3
          INT_LEFT x11_4:4 <- x11_3:4, const[0x3:4]
        0x00011170: 0x00b50533  add x10, x10, x11
          INT_ADD x10_6:4 <- x10_5:4, x11_4:4
        0x00011174: 0x00052583  lw x11, 0(x10)
          COPY u0_15:4 <- x10_6:4
          LOAD x11_5:4 <- u0_15:4 [m7]
        0x00011178: 0xfec42503  lw x10, -20(x8)
          INT_ADD u0_16:4 <- x8_1:4, const[0xffffffec:4]
          LOAD x10_7:4 <- u0_16:4 [m7]
        0x0001117c: 0x00b50533  add x10, x10, x11
          INT_ADD x10_8:4 <- x10_7:4, x11_5:4
        0x00011180: 0xfea42623  sw x10, -20(x8)
          INT_ADD u0_17:4 <- x8_1:4, const[0xffffffec:4]
          STORE u0_17:4, x10_8:4 [m7 -> m8]
        0x00011184: 0xff442503  lw x10, -12(x8)
          INT_ADD u0_18:4 <- x8_1:4, const[0xfffffff4:4]
          LOAD x10_9:4 <- u0_18:4 [m8]
        0x00011188: 0xfe842583  lw x11, -24(x8)
          INT_ADD u0_19:4 <- x8_1:4, const[0xffffffe8:4]
          LOAD x11_6:4 <- u0_19:4 [m8]
        0x0001118c: 0x00359593  slli x11, x11, 3
          INT_LEFT x11_7:4 <- x11_6:4, const[0x3:4]
        0x00011190: 0x00b50533  add x10, x10, x11
          INT_ADD x10_10:4 <- x10_9:4, x11_7:4
        0x00011194: 0x00452583  lw x11, 4(x10)
          INT_ADD u0_20:4 <- x10_10:4, const[0x4:4]
          LOAD x11_8:4 <- u0_20:4 [m8]
        0x00011198: 0xfec42503  lw x10, -20(x8)
          INT_ADD u0_21:4 <- x8_1:4, const[0xffffffec:4]
          LOAD x10_11:4 <- u0_21:4 [m8]
        0x0001119c: 0x00b50533  add x10, x10, x11
          INT_ADD x10_12:4 <- x10_11:4, x11_8:4
        0x000111a0: 0xfea42623  sw x10, -20(x8)
          INT_ADD u0_22:4 <- x8_1:4, const[0xffffffec:4]
          STORE u0_22:4, x10_12:4 [m8 -> m9]
        0x000111a4: 0x0040006f  jal x0, 0x111a8
          BRANCH const[0x111a8:4]`,
        annotations: ["access pattern: *(x10_2 + 0):int32 → agg_8.field_0", "access pattern: *(x10_2 + 4):int32 → agg_8.field_4", "stride: x10_2 += 8 → sizeof(agg_8) = 8"],
      },
      {
        address: "0x111a8",
        ir: `        0x000111a8: 0xfe842503  lw x10, -24(x8)
          INT_ADD u0_23:4 <- x8_1:4, const[0xffffffe8:4]
          LOAD x10_13:4 <- u0_23:4 [m9]
        0x000111ac: 0x00150513  addi x10, x10, 1
          INT_ADD x10_14:4 <- x10_13:4, const[0x1:4]
        0x000111b0: 0xfea42423  sw x10, -24(x8)
          INT_ADD u0_24:4 <- x8_1:4, const[0xffffffe8:4]
          STORE u0_24:4, x10_14:4 [m9 -> m10]
        0x000111b4: 0xfa1ff06f  jal x0, 0x11154
          BRANCH const[0x11154:4]`,
        annotations: ["x10_14: agg_8* (next element = base + i*8)"],
      }
        ],
        edges: [
      { source: "0x1112c", target: "0x11154", type: "normal" },
      { source: "0x11154", target: "0x111b8", label: "taken: i >= n", type: "normal" },
      { source: "0x11154", target: "0x11160", label: "fall: i < n", type: "normal" },
      { source: "0x11160", target: "0x11164", type: "normal" },
      { source: "0x11164", target: "0x111a8", type: "normal" },
      { source: "0x111a8", target: "0x11154", label: "back edge", type: "back" },
        ],
      },
    },
  },

  /* ── 13: VARIABLES ──────────────────────────────────────────────── */
  {
    id: "variables",
    number: 13,
    name: "Variables",
    phase: "analysis",
    description: "Register-allocated SSA values are grouped back into high-level variables. main has 4 local variables (local_12_4 through local_24_4). parse_record has 2 parameters (arg_x10_4 as a pointer to the discovered aggregate, arg_x11_4 as an int) and 2 locals.",
    githubDir: "tiny_dec/analysis/highvars",
    viewMode: "cfg",
    content: `  root: 0x110e4
  order: 0x110e4, 0x1112c
  pending:
  invalidated:
  externals:
    <none>
  call_graph:
    0x110e4@0x11118 -> internal 0x1112c name=parse_record
  functions:
    function 0x110e4 name=main frame_size=32 dynamic_sp=no variables=4 pending=[]
    variables:
      variable local_24_4 kind=local size=4 binding=stack_slot -24 size=4 role=local type=int:4 partitions=1
      variable local_20_4 kind=local size=4 binding=stack_slot -20 size=4 role=local type=int:4 partitions=1
      variable local_16_4 kind=local size=4 binding=stack_slot -16 size=4 role=local type=int:4 partitions=1
      variable local_12_4 kind=local size=4 binding=stack_slot -12 size=4 role=local type=int:4 partitions=1
    function 0x1112c name=parse_record frame_size=32 dynamic_sp=no variables=4 pending=[]
    variables:
      variable arg_x11_4 kind=parameter size=4 binding=stack_slot -16 size=4 role=argument_home(x11) type=int:4 root=x11_0:4 partitions=1
      variable arg_x10_4 kind=parameter size=4 binding=stack_slot -12 size=4 role=argument_home(x10) type=pointer:4 root=x10_0:4 aggregate_fields=2 partitions=3
        aggregate pointer x10_0:4 stride=? fields=2
          field +0 size=4 type=int:4 partitions=[value x10_0:4 offset=+0 size=4]
          field +4 size=4 type=int:4 partitions=[value x10_0:4 offset=+4 size=4]
      variable local_24_4 kind=local size=4 binding=stack_slot -24 size=4 role=local type=int:4 partitions=1
      variable local_20_4 kind=local size=4 binding=stack_slot -20 size=4 role=local type=int:4 partitions=1`,
    cfg: {
      main: {
        blocks: [
      {
        address: "0x110e4",
        ir: `    0x000110e4: 0xfe010113  addi x2, x2, -32
      INT_ADD register[0x2:4] <- register[0x2:4], const[0xffffffe0:4]
    0x000110e8: 0x00112e23  sw x1, 28(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x1c:4]
      STORE unique[0x0:4], register[0x1:4]
    0x000110ec: 0x00812c23  sw x8, 24(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x18:4]
      STORE unique[0x0:4], register[0x8:4]
    0x000110f0: 0x02010413  addi x8, x2, 32
      INT_ADD register[0x8:4] <- register[0x2:4], const[0x20:4]
    0x000110f4: 0x01400513  addi x10, x0, 20
      COPY register[0xa:4] <- const[0x14:4]
    0x000110f8: 0xfea42a23  sw x10, -12(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff4:4]
      STORE unique[0x0:4], register[0xa:4]
    0x000110fc: 0x00200593  addi x11, x0, 2
      COPY register[0xb:4] <- const[0x2:4]
    0x00011100: 0xfeb42823  sw x11, -16(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff0:4]
      STORE unique[0x0:4], register[0xb:4]
    0x00011104: 0x00a00513  addi x10, x0, 10
      COPY register[0xa:4] <- const[0xa:4]
    0x00011108: 0xfea42623  sw x10, -20(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffec:4]
      STORE unique[0x0:4], register[0xa:4]
    0x0001110c: 0x00100513  addi x10, x0, 1
      COPY register[0xa:4] <- const[0x1:4]
    0x00011110: 0xfea42423  sw x10, -24(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffe8:4]
      STORE unique[0x0:4], register[0xa:4]
    0x00011114: 0xfe840513  addi x10, x8, -24
      INT_ADD register[0xa:4] <- register[0x8:4], const[0xffffffe8:4]
    0x00011118: 0x014000ef  jal x1, 0x1112c
      COPY register[0x1:4] <- const[0x1111c:4]
      CALL const[0x1112c:4]
    0x0001111c: 0x01c12083  lw x1, 28(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x1c:4]
      LOAD unique[0x4:4] <- unique[0x0:4]
      COPY register[0x1:4] <- unique[0x4:4]
    0x00011120: 0x01812403  lw x8, 24(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x18:4]
      LOAD unique[0x4:4] <- unique[0x0:4]
      COPY register[0x8:4] <- unique[0x4:4]
    0x00011124: 0x02010113  addi x2, x2, 32
      INT_ADD register[0x2:4] <- register[0x2:4], const[0x20:4]
    0x00011128: 0x00008067  jalr x0, 0(x1)
      COPY unique[0x0:4] <- register[0x1:4]
      INT_AND unique[0x4:4] <- unique[0x0:4], const[0xfffffffe:4]
      RETURN unique[0x4:4]`,
      },
        ],
        edges: [],
      },
      parse_record: {
        blocks: [
      {
        address: "0x1112c",
        ir: `        0x0001112c: 0xfe010113  addi x2, x2, -32
          INT_ADD x2_1:4 <- x2_0:4, const[0xffffffe0:4]
        0x00011130: 0x00112e23  sw x1, 28(x2)
          INT_ADD u0_1:4 <- x2_1:4, const[0x1c:4]
          STORE u0_1:4, x1_0:4 [m0 -> m1]
        0x00011134: 0x00812c23  sw x8, 24(x2)
          INT_ADD u0_2:4 <- x2_1:4, const[0x18:4]
          STORE u0_2:4, x8_0:4 [m1 -> m2]
        0x00011138: 0x02010413  addi x8, x2, 32
          INT_ADD x8_1:4 <- x2_1:4, const[0x20:4]
        0x0001113c: 0xfea42a23  sw x10, -12(x8)
          INT_ADD u0_3:4 <- x8_1:4, const[0xfffffff4:4]
          STORE u0_3:4, x10_0:4 [m2 -> m3]
        0x00011140: 0xfeb42823  sw x11, -16(x8)
          INT_ADD u0_4:4 <- x8_1:4, const[0xfffffff0:4]
          STORE u0_4:4, x11_0:4 [m3 -> m4]
        0x00011144: 0x00000513  addi x10, x0, 0
          COPY x10_1:4 <- const[0x0:4]
        0x00011148: 0xfea42623  sw x10, -20(x8)
          INT_ADD u0_5:4 <- x8_1:4, const[0xffffffec:4]
          STORE u0_5:4, x10_1:4 [m4 -> m5]
        0x0001114c: 0xfea42423  sw x10, -24(x8)
          INT_ADD u0_6:4 <- x8_1:4, const[0xffffffe8:4]
          STORE u0_6:4, x10_1:4 [m5 -> m6]
        0x00011150: 0x0040006f  jal x0, 0x11154
          BRANCH const[0x11154:4]`,
      },
      {
        address: "0x11154",
        ir: `        MEM_PHI m7 <- 0x1112c:m6, 0x111a8:m10
        PHI x10_2:4 <- 0x1112c:x10_1:4, 0x111a8:x10_14:4
        PHI x11_1:4 <- 0x1112c:x11_0:4, 0x111a8:x11_8:4
        0x00011154: 0xfe842503  lw x10, -24(x8)
          INT_ADD u0_7:4 <- x8_1:4, const[0xffffffe8:4]
          LOAD x10_3:4 <- u0_7:4 [m7]
        0x00011158: 0xff042583  lw x11, -16(x8)
          INT_ADD u0_8:4 <- x8_1:4, const[0xfffffff0:4]
          LOAD x11_2:4 <- u0_8:4 [m7]
        0x0001115c: 0x04b55e63  bge x10, x11, 0x111b8
          INT_SLESS u0_1:1 <- x10_3:4, x11_2:4
          BOOL_NEGATE u4_1:1 <- u0_1:1
          CBRANCH const[0x111b8:4], u4_1:1`,
      },
      {
        address: "0x111b8",
        ir: `        0x000111b8: 0xfec42503  lw x10, -20(x8)
          INT_ADD u0_9:4 <- x8_1:4, const[0xffffffec:4]
          LOAD x10_4:4 <- u0_9:4 [m7]
        0x000111bc: 0x01c12083  lw x1, 28(x2)
          INT_ADD u0_10:4 <- x2_1:4, const[0x1c:4]
          LOAD x1_1:4 <- u0_10:4 [m7]
        0x000111c0: 0x01812403  lw x8, 24(x2)
          INT_ADD u0_11:4 <- x2_1:4, const[0x18:4]
          LOAD x8_2:4 <- u0_11:4 [m7]
        0x000111c4: 0x02010113  addi x2, x2, 32
          INT_ADD x2_2:4 <- x2_1:4, const[0x20:4]
        0x000111c8: 0x00008067  jalr x0, 0(x1)
          COPY u0_12:4 <- x1_1:4
          INT_AND u4_1:4 <- u0_12:4, const[0xfffffffe:4]
          RETURN u4_1:4`,
      },
      {
        address: "0x11160",
        ir: `        0x00011160: 0x0040006f  jal x0, 0x11164
          BRANCH const[0x11164:4]`,
      },
      {
        address: "0x11164",
        ir: `        0x00011164: 0xff442503  lw x10, -12(x8)
          INT_ADD u0_13:4 <- x8_1:4, const[0xfffffff4:4]
          LOAD x10_5:4 <- u0_13:4 [m7]
        0x00011168: 0xfe842583  lw x11, -24(x8)
          INT_ADD u0_14:4 <- x8_1:4, const[0xffffffe8:4]
          LOAD x11_3:4 <- u0_14:4 [m7]
        0x0001116c: 0x00359593  slli x11, x11, 3
          INT_LEFT x11_4:4 <- x11_3:4, const[0x3:4]
        0x00011170: 0x00b50533  add x10, x10, x11
          INT_ADD x10_6:4 <- x10_5:4, x11_4:4
        0x00011174: 0x00052583  lw x11, 0(x10)
          COPY u0_15:4 <- x10_6:4
          LOAD x11_5:4 <- u0_15:4 [m7]
        0x00011178: 0xfec42503  lw x10, -20(x8)
          INT_ADD u0_16:4 <- x8_1:4, const[0xffffffec:4]
          LOAD x10_7:4 <- u0_16:4 [m7]
        0x0001117c: 0x00b50533  add x10, x10, x11
          INT_ADD x10_8:4 <- x10_7:4, x11_5:4
        0x00011180: 0xfea42623  sw x10, -20(x8)
          INT_ADD u0_17:4 <- x8_1:4, const[0xffffffec:4]
          STORE u0_17:4, x10_8:4 [m7 -> m8]
        0x00011184: 0xff442503  lw x10, -12(x8)
          INT_ADD u0_18:4 <- x8_1:4, const[0xfffffff4:4]
          LOAD x10_9:4 <- u0_18:4 [m8]
        0x00011188: 0xfe842583  lw x11, -24(x8)
          INT_ADD u0_19:4 <- x8_1:4, const[0xffffffe8:4]
          LOAD x11_6:4 <- u0_19:4 [m8]
        0x0001118c: 0x00359593  slli x11, x11, 3
          INT_LEFT x11_7:4 <- x11_6:4, const[0x3:4]
        0x00011190: 0x00b50533  add x10, x10, x11
          INT_ADD x10_10:4 <- x10_9:4, x11_7:4
        0x00011194: 0x00452583  lw x11, 4(x10)
          INT_ADD u0_20:4 <- x10_10:4, const[0x4:4]
          LOAD x11_8:4 <- u0_20:4 [m8]
        0x00011198: 0xfec42503  lw x10, -20(x8)
          INT_ADD u0_21:4 <- x8_1:4, const[0xffffffec:4]
          LOAD x10_11:4 <- u0_21:4 [m8]
        0x0001119c: 0x00b50533  add x10, x10, x11
          INT_ADD x10_12:4 <- x10_11:4, x11_8:4
        0x000111a0: 0xfea42623  sw x10, -20(x8)
          INT_ADD u0_22:4 <- x8_1:4, const[0xffffffec:4]
          STORE u0_22:4, x10_12:4 [m8 -> m9]
        0x000111a4: 0x0040006f  jal x0, 0x111a8
          BRANCH const[0x111a8:4]`,
      },
      {
        address: "0x111a8",
        ir: `        0x000111a8: 0xfe842503  lw x10, -24(x8)
          INT_ADD u0_23:4 <- x8_1:4, const[0xffffffe8:4]
          LOAD x10_13:4 <- u0_23:4 [m9]
        0x000111ac: 0x00150513  addi x10, x10, 1
          INT_ADD x10_14:4 <- x10_13:4, const[0x1:4]
        0x000111b0: 0xfea42423  sw x10, -24(x8)
          INT_ADD u0_24:4 <- x8_1:4, const[0xffffffe8:4]
          STORE u0_24:4, x10_14:4 [m9 -> m10]
        0x000111b4: 0xfa1ff06f  jal x0, 0x11154
          BRANCH const[0x11154:4]`,
      }
        ],
        edges: [
      { source: "0x1112c", target: "0x11154", type: "normal" },
      { source: "0x11154", target: "0x111b8", label: "taken: i >= n", type: "normal" },
      { source: "0x11154", target: "0x11160", label: "fall: i < n", type: "normal" },
      { source: "0x11160", target: "0x11164", type: "normal" },
      { source: "0x11164", target: "0x111a8", type: "normal" },
      { source: "0x111a8", target: "0x11154", label: "back edge", type: "back" },
        ],
      },
    },
  },

  /* ── 14: RANGE ANALYSIS ──────────────────────────────────────────────── */
  {
    id: "range",
    number: 14,
    name: "Range Analysis",
    phase: "analysis",
    description: "Range analysis computes bounds. In main, all locals are constants: local_12_4=[20,20], local_16_4=[2,2]. In parse_record, the loop counter local_24_4 ranges [0,+inf] and local_20_4 (accumulator) starts at [0,0].",
    githubDir: "tiny_dec/analysis/range",
    viewMode: "cfg",
    content: `  root: 0x110e4
  order: 0x110e4, 0x1112c
  pending:
  invalidated:
  externals:
    <none>
  call_graph:
    0x110e4@0x11118 -> internal 0x1112c name=parse_record
  functions:
    function 0x110e4 name=main frame_size=32 dynamic_sp=no value_ranges=5 variable_ranges=4 branch_refinements=0 pending=[]
    variables:
      variable local_12_4 range=[20, 20]
      variable local_16_4 range=[2, 2]
      variable local_20_4 range=[10, 10]
      variable local_24_4 range=[1, 1]
    values:
      value x1_1:4 range=[69916, 69916]
      value x10_1:4 range=[20, 20]
      value x10_2:4 range=[10, 10]
      value x10_3:4 range=[1, 1]
      value x11_1:4 range=[2, 2]
    branches:
      <none>
    function 0x1112c name=parse_record frame_size=32 dynamic_sp=no value_ranges=12 variable_ranges=2 branch_refinements=0 pending=[]
    variables:
      variable local_20_4 range=[0, 0]
      variable local_24_4 range=[0, +inf]
    values:
      value x10_1:4 range=[0, 0]
      value x10_2:4 range=[0, +inf]
      value x10_3:4 range=[0, +inf]
      value x10_4:4 range=[0, 0]
      value x10_7:4 range=[0, 0]
      value x10_11:4 range=[0, 0]
      value x10_13:4 range=[0, +inf]
      value x10_14:4 range=[1, +inf]
      value x11_3:4 range=[0, +inf]
      value x11_6:4 range=[0, +inf]
      value u0_1:1 range=[0, 1]
      value u4_1:1 range=[0, 1]
    branches:
      <none>`,
    cfg: {
      main: {
        blocks: [
      {
        address: "0x110e4",
        ir: `    0x000110e4: 0xfe010113  addi x2, x2, -32
      INT_ADD register[0x2:4] <- register[0x2:4], const[0xffffffe0:4]
    0x000110e8: 0x00112e23  sw x1, 28(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x1c:4]
      STORE unique[0x0:4], register[0x1:4]
    0x000110ec: 0x00812c23  sw x8, 24(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x18:4]
      STORE unique[0x0:4], register[0x8:4]
    0x000110f0: 0x02010413  addi x8, x2, 32
      INT_ADD register[0x8:4] <- register[0x2:4], const[0x20:4]
    0x000110f4: 0x01400513  addi x10, x0, 20
      COPY register[0xa:4] <- const[0x14:4]
    0x000110f8: 0xfea42a23  sw x10, -12(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff4:4]
      STORE unique[0x0:4], register[0xa:4]
    0x000110fc: 0x00200593  addi x11, x0, 2
      COPY register[0xb:4] <- const[0x2:4]
    0x00011100: 0xfeb42823  sw x11, -16(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff0:4]
      STORE unique[0x0:4], register[0xb:4]
    0x00011104: 0x00a00513  addi x10, x0, 10
      COPY register[0xa:4] <- const[0xa:4]
    0x00011108: 0xfea42623  sw x10, -20(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffec:4]
      STORE unique[0x0:4], register[0xa:4]
    0x0001110c: 0x00100513  addi x10, x0, 1
      COPY register[0xa:4] <- const[0x1:4]
    0x00011110: 0xfea42423  sw x10, -24(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffe8:4]
      STORE unique[0x0:4], register[0xa:4]
    0x00011114: 0xfe840513  addi x10, x8, -24
      INT_ADD register[0xa:4] <- register[0x8:4], const[0xffffffe8:4]
    0x00011118: 0x014000ef  jal x1, 0x1112c
      COPY register[0x1:4] <- const[0x1111c:4]
      CALL const[0x1112c:4]
    0x0001111c: 0x01c12083  lw x1, 28(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x1c:4]
      LOAD unique[0x4:4] <- unique[0x0:4]
      COPY register[0x1:4] <- unique[0x4:4]
    0x00011120: 0x01812403  lw x8, 24(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x18:4]
      LOAD unique[0x4:4] <- unique[0x0:4]
      COPY register[0x8:4] <- unique[0x4:4]
    0x00011124: 0x02010113  addi x2, x2, 32
      INT_ADD register[0x2:4] <- register[0x2:4], const[0x20:4]
    0x00011128: 0x00008067  jalr x0, 0(x1)
      COPY unique[0x0:4] <- register[0x1:4]
      INT_AND unique[0x4:4] <- unique[0x0:4], const[0xfffffffe:4]
      RETURN unique[0x4:4]`,
        annotations: ["constants: x10_4 = 20, x11_1 = 2"],
      },
        ],
        edges: [],
      },
      parse_record: {
        blocks: [
      {
        address: "0x1112c",
        ir: `        0x0001112c: 0xfe010113  addi x2, x2, -32
          INT_ADD x2_1:4 <- x2_0:4, const[0xffffffe0:4]
        0x00011130: 0x00112e23  sw x1, 28(x2)
          INT_ADD u0_1:4 <- x2_1:4, const[0x1c:4]
          STORE u0_1:4, x1_0:4 [m0 -> m1]
        0x00011134: 0x00812c23  sw x8, 24(x2)
          INT_ADD u0_2:4 <- x2_1:4, const[0x18:4]
          STORE u0_2:4, x8_0:4 [m1 -> m2]
        0x00011138: 0x02010413  addi x8, x2, 32
          INT_ADD x8_1:4 <- x2_1:4, const[0x20:4]
        0x0001113c: 0xfea42a23  sw x10, -12(x8)
          INT_ADD u0_3:4 <- x8_1:4, const[0xfffffff4:4]
          STORE u0_3:4, x10_0:4 [m2 -> m3]
        0x00011140: 0xfeb42823  sw x11, -16(x8)
          INT_ADD u0_4:4 <- x8_1:4, const[0xfffffff0:4]
          STORE u0_4:4, x11_0:4 [m3 -> m4]
        0x00011144: 0x00000513  addi x10, x0, 0
          COPY x10_1:4 <- const[0x0:4]
        0x00011148: 0xfea42623  sw x10, -20(x8)
          INT_ADD u0_5:4 <- x8_1:4, const[0xffffffec:4]
          STORE u0_5:4, x10_1:4 [m4 -> m5]
        0x0001114c: 0xfea42423  sw x10, -24(x8)
          INT_ADD u0_6:4 <- x8_1:4, const[0xffffffe8:4]
          STORE u0_6:4, x10_1:4 [m5 -> m6]
        0x00011150: 0x0040006f  jal x0, 0x11154
          BRANCH const[0x11154:4]`,
        annotations: ["x15_1 = 0 (loop counter init)", "range: x15_1 ∈ [0, 0]"],
      },
      {
        address: "0x11154",
        ir: `        MEM_PHI m7 <- 0x1112c:m6, 0x111a8:m10
        PHI x10_2:4 <- 0x1112c:x10_1:4, 0x111a8:x10_14:4
        PHI x11_1:4 <- 0x1112c:x11_0:4, 0x111a8:x11_8:4
        0x00011154: 0xfe842503  lw x10, -24(x8)
          INT_ADD u0_7:4 <- x8_1:4, const[0xffffffe8:4]
          LOAD x10_3:4 <- u0_7:4 [m7]
        0x00011158: 0xff042583  lw x11, -16(x8)
          INT_ADD u0_8:4 <- x8_1:4, const[0xfffffff0:4]
          LOAD x11_2:4 <- u0_8:4 [m7]
        0x0001115c: 0x04b55e63  bge x10, x11, 0x111b8
          INT_SLESS u0_1:1 <- x10_3:4, x11_2:4
          BOOL_NEGATE u4_1:1 <- u0_1:1
          CBRANCH const[0x111b8:4], u4_1:1`,
        annotations: ["range: x15_2 ∈ [0, x11_0)", "branch: x15_2 <s x11_0 → loop continues"],
      },
      {
        address: "0x111b8",
        ir: `        0x000111b8: 0xfec42503  lw x10, -20(x8)
          INT_ADD u0_9:4 <- x8_1:4, const[0xffffffec:4]
          LOAD x10_4:4 <- u0_9:4 [m7]
        0x000111bc: 0x01c12083  lw x1, 28(x2)
          INT_ADD u0_10:4 <- x2_1:4, const[0x1c:4]
          LOAD x1_1:4 <- u0_10:4 [m7]
        0x000111c0: 0x01812403  lw x8, 24(x2)
          INT_ADD u0_11:4 <- x2_1:4, const[0x18:4]
          LOAD x8_2:4 <- u0_11:4 [m7]
        0x000111c4: 0x02010113  addi x2, x2, 32
          INT_ADD x2_2:4 <- x2_1:4, const[0x20:4]
        0x000111c8: 0x00008067  jalr x0, 0(x1)
          COPY u0_12:4 <- x1_1:4
          INT_AND u4_1:4 <- u0_12:4, const[0xfffffffe:4]
          RETURN u4_1:4`,
        annotations: ["range: x15_2 = x11_0 (loop exit condition)"],
      },
      {
        address: "0x11160",
        ir: `        0x00011160: 0x0040006f  jal x0, 0x11164
          BRANCH const[0x11164:4]`,
        annotations: ["(pass-through)"],
      },
      {
        address: "0x11164",
        ir: `        0x00011164: 0xff442503  lw x10, -12(x8)
          INT_ADD u0_13:4 <- x8_1:4, const[0xfffffff4:4]
          LOAD x10_5:4 <- u0_13:4 [m7]
        0x00011168: 0xfe842583  lw x11, -24(x8)
          INT_ADD u0_14:4 <- x8_1:4, const[0xffffffe8:4]
          LOAD x11_3:4 <- u0_14:4 [m7]
        0x0001116c: 0x00359593  slli x11, x11, 3
          INT_LEFT x11_4:4 <- x11_3:4, const[0x3:4]
        0x00011170: 0x00b50533  add x10, x10, x11
          INT_ADD x10_6:4 <- x10_5:4, x11_4:4
        0x00011174: 0x00052583  lw x11, 0(x10)
          COPY u0_15:4 <- x10_6:4
          LOAD x11_5:4 <- u0_15:4 [m7]
        0x00011178: 0xfec42503  lw x10, -20(x8)
          INT_ADD u0_16:4 <- x8_1:4, const[0xffffffec:4]
          LOAD x10_7:4 <- u0_16:4 [m7]
        0x0001117c: 0x00b50533  add x10, x10, x11
          INT_ADD x10_8:4 <- x10_7:4, x11_5:4
        0x00011180: 0xfea42623  sw x10, -20(x8)
          INT_ADD u0_17:4 <- x8_1:4, const[0xffffffec:4]
          STORE u0_17:4, x10_8:4 [m7 -> m8]
        0x00011184: 0xff442503  lw x10, -12(x8)
          INT_ADD u0_18:4 <- x8_1:4, const[0xfffffff4:4]
          LOAD x10_9:4 <- u0_18:4 [m8]
        0x00011188: 0xfe842583  lw x11, -24(x8)
          INT_ADD u0_19:4 <- x8_1:4, const[0xffffffe8:4]
          LOAD x11_6:4 <- u0_19:4 [m8]
        0x0001118c: 0x00359593  slli x11, x11, 3
          INT_LEFT x11_7:4 <- x11_6:4, const[0x3:4]
        0x00011190: 0x00b50533  add x10, x10, x11
          INT_ADD x10_10:4 <- x10_9:4, x11_7:4
        0x00011194: 0x00452583  lw x11, 4(x10)
          INT_ADD u0_20:4 <- x10_10:4, const[0x4:4]
          LOAD x11_8:4 <- u0_20:4 [m8]
        0x00011198: 0xfec42503  lw x10, -20(x8)
          INT_ADD u0_21:4 <- x8_1:4, const[0xffffffec:4]
          LOAD x10_11:4 <- u0_21:4 [m8]
        0x0001119c: 0x00b50533  add x10, x10, x11
          INT_ADD x10_12:4 <- x10_11:4, x11_8:4
        0x000111a0: 0xfea42623  sw x10, -20(x8)
          INT_ADD u0_22:4 <- x8_1:4, const[0xffffffec:4]
          STORE u0_22:4, x10_12:4 [m8 -> m9]
        0x000111a4: 0x0040006f  jal x0, 0x111a8
          BRANCH const[0x111a8:4]`,
        annotations: ["range: x15_2 ∈ [0, x11_0-1] (in-loop guarantee)"],
      },
      {
        address: "0x111a8",
        ir: `        0x000111a8: 0xfe842503  lw x10, -24(x8)
          INT_ADD u0_23:4 <- x8_1:4, const[0xffffffe8:4]
          LOAD x10_13:4 <- u0_23:4 [m9]
        0x000111ac: 0x00150513  addi x10, x10, 1
          INT_ADD x10_14:4 <- x10_13:4, const[0x1:4]
        0x000111b0: 0xfea42423  sw x10, -24(x8)
          INT_ADD u0_24:4 <- x8_1:4, const[0xffffffe8:4]
          STORE u0_24:4, x10_14:4 [m9 -> m10]
        0x000111b4: 0xfa1ff06f  jal x0, 0x11154
          BRANCH const[0x11154:4]`,
        annotations: ["x15_9 = x15_2 + 1", "range: x15_9 ∈ [1, x11_0]"],
      }
        ],
        edges: [
      { source: "0x1112c", target: "0x11154", type: "normal" },
      { source: "0x11154", target: "0x111b8", label: "taken: i >= n", type: "normal" },
      { source: "0x11154", target: "0x11160", label: "fall: i < n", type: "normal" },
      { source: "0x11160", target: "0x11164", type: "normal" },
      { source: "0x11164", target: "0x111a8", type: "normal" },
      { source: "0x111a8", target: "0x11154", label: "back edge", type: "back" },
        ],
      },
    },
  },

  /* ── 15: INTERPROCEDURAL ──────────────────────────────────────────────── */
  {
    id: "interproc",
    number: 15,
    name: "Interprocedural",
    phase: "analysis",
    description: "Interprocedural analysis infers function signatures. main takes no parameters and returns x10. parse_record takes x10:pointer (arg_x10_4) and x11:int (arg_x11_4), returns x10, and reads indirectly through its pointer argument.",
    githubDir: "tiny_dec/analysis/interproc",
    viewMode: "cfg",
    content: `  root: 0x110e4
  order: 0x110e4, 0x1112c
  pending:
  invalidated:
  externals:
    <none>
  call_graph:
    0x110e4@0x11118 -> internal 0x1112c name=parse_record
  scheduler_invalidations:
    <none>
  functions:
    function 0x110e4 name=main frame_size=32 dynamic_sp=no params=0 returns=1 no_return=no globals_read=0 globals_written=0 pending=[]
    prototype:
      param <none>
      return x10:4
    effects:
      effects reads=[] writes=[] indirect_reads=no indirect_writes=no
    function 0x1112c name=parse_record frame_size=32 dynamic_sp=no params=2 returns=1 no_return=no globals_read=0 globals_written=0 pending=[]
    prototype:
      param x10:4 type=pointer:4 name=arg_x10_4
      param x11:4 type=int:4 name=arg_x11_4
      return x10:4
    effects:
      effects reads=[] writes=[] indirect_reads=yes indirect_writes=no`,
    cfg: {
      main: {
        blocks: [
      {
        address: "0x110e4",
        ir: `    0x000110e4: 0xfe010113  addi x2, x2, -32
      INT_ADD register[0x2:4] <- register[0x2:4], const[0xffffffe0:4]
    0x000110e8: 0x00112e23  sw x1, 28(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x1c:4]
      STORE unique[0x0:4], register[0x1:4]
    0x000110ec: 0x00812c23  sw x8, 24(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x18:4]
      STORE unique[0x0:4], register[0x8:4]
    0x000110f0: 0x02010413  addi x8, x2, 32
      INT_ADD register[0x8:4] <- register[0x2:4], const[0x20:4]
    0x000110f4: 0x01400513  addi x10, x0, 20
      COPY register[0xa:4] <- const[0x14:4]
    0x000110f8: 0xfea42a23  sw x10, -12(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff4:4]
      STORE unique[0x0:4], register[0xa:4]
    0x000110fc: 0x00200593  addi x11, x0, 2
      COPY register[0xb:4] <- const[0x2:4]
    0x00011100: 0xfeb42823  sw x11, -16(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff0:4]
      STORE unique[0x0:4], register[0xb:4]
    0x00011104: 0x00a00513  addi x10, x0, 10
      COPY register[0xa:4] <- const[0xa:4]
    0x00011108: 0xfea42623  sw x10, -20(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffec:4]
      STORE unique[0x0:4], register[0xa:4]
    0x0001110c: 0x00100513  addi x10, x0, 1
      COPY register[0xa:4] <- const[0x1:4]
    0x00011110: 0xfea42423  sw x10, -24(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffe8:4]
      STORE unique[0x0:4], register[0xa:4]
    0x00011114: 0xfe840513  addi x10, x8, -24
      INT_ADD register[0xa:4] <- register[0x8:4], const[0xffffffe8:4]
    0x00011118: 0x014000ef  jal x1, 0x1112c
      COPY register[0x1:4] <- const[0x1111c:4]
      CALL const[0x1112c:4]
    0x0001111c: 0x01c12083  lw x1, 28(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x1c:4]
      LOAD unique[0x4:4] <- unique[0x0:4]
      COPY register[0x1:4] <- unique[0x4:4]
    0x00011120: 0x01812403  lw x8, 24(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x18:4]
      LOAD unique[0x4:4] <- unique[0x0:4]
      COPY register[0x8:4] <- unique[0x4:4]
    0x00011124: 0x02010113  addi x2, x2, 32
      INT_ADD register[0x2:4] <- register[0x2:4], const[0x20:4]
    0x00011128: 0x00008067  jalr x0, 0(x1)
      COPY unique[0x0:4] <- register[0x1:4]
      INT_AND unique[0x4:4] <- unique[0x0:4], const[0xfffffffe:4]
      RETURN unique[0x4:4]`,
        annotations: ["call: parse_record(agg_8* x10_4, int32_t x11_1) → uint32_t x10_5", "caller sig: main() → int32_t"],
      },
        ],
        edges: [],
      },
      parse_record: {
        blocks: [
      {
        address: "0x1112c",
        ir: `        0x0001112c: 0xfe010113  addi x2, x2, -32
          INT_ADD x2_1:4 <- x2_0:4, const[0xffffffe0:4]
        0x00011130: 0x00112e23  sw x1, 28(x2)
          INT_ADD u0_1:4 <- x2_1:4, const[0x1c:4]
          STORE u0_1:4, x1_0:4 [m0 -> m1]
        0x00011134: 0x00812c23  sw x8, 24(x2)
          INT_ADD u0_2:4 <- x2_1:4, const[0x18:4]
          STORE u0_2:4, x8_0:4 [m1 -> m2]
        0x00011138: 0x02010413  addi x8, x2, 32
          INT_ADD x8_1:4 <- x2_1:4, const[0x20:4]
        0x0001113c: 0xfea42a23  sw x10, -12(x8)
          INT_ADD u0_3:4 <- x8_1:4, const[0xfffffff4:4]
          STORE u0_3:4, x10_0:4 [m2 -> m3]
        0x00011140: 0xfeb42823  sw x11, -16(x8)
          INT_ADD u0_4:4 <- x8_1:4, const[0xfffffff0:4]
          STORE u0_4:4, x11_0:4 [m3 -> m4]
        0x00011144: 0x00000513  addi x10, x0, 0
          COPY x10_1:4 <- const[0x0:4]
        0x00011148: 0xfea42623  sw x10, -20(x8)
          INT_ADD u0_5:4 <- x8_1:4, const[0xffffffec:4]
          STORE u0_5:4, x10_1:4 [m4 -> m5]
        0x0001114c: 0xfea42423  sw x10, -24(x8)
          INT_ADD u0_6:4 <- x8_1:4, const[0xffffffe8:4]
          STORE u0_6:4, x10_1:4 [m5 -> m6]
        0x00011150: 0x0040006f  jal x0, 0x11154
          BRANCH const[0x11154:4]`,
        annotations: ["callee sig: parse_record(agg_8* arg_x10, int32_t arg_x11) → uint32_t"],
      },
      {
        address: "0x11154",
        ir: `        MEM_PHI m7 <- 0x1112c:m6, 0x111a8:m10
        PHI x10_2:4 <- 0x1112c:x10_1:4, 0x111a8:x10_14:4
        PHI x11_1:4 <- 0x1112c:x11_0:4, 0x111a8:x11_8:4
        0x00011154: 0xfe842503  lw x10, -24(x8)
          INT_ADD u0_7:4 <- x8_1:4, const[0xffffffe8:4]
          LOAD x10_3:4 <- u0_7:4 [m7]
        0x00011158: 0xff042583  lw x11, -16(x8)
          INT_ADD u0_8:4 <- x8_1:4, const[0xfffffff0:4]
          LOAD x11_2:4 <- u0_8:4 [m7]
        0x0001115c: 0x04b55e63  bge x10, x11, 0x111b8
          INT_SLESS u0_1:1 <- x10_3:4, x11_2:4
          BOOL_NEGATE u4_1:1 <- u0_1:1
          CBRANCH const[0x111b8:4], u4_1:1`,
        annotations: ["(no interprocedural info)"],
      },
      {
        address: "0x111b8",
        ir: `        0x000111b8: 0xfec42503  lw x10, -20(x8)
          INT_ADD u0_9:4 <- x8_1:4, const[0xffffffec:4]
          LOAD x10_4:4 <- u0_9:4 [m7]
        0x000111bc: 0x01c12083  lw x1, 28(x2)
          INT_ADD u0_10:4 <- x2_1:4, const[0x1c:4]
          LOAD x1_1:4 <- u0_10:4 [m7]
        0x000111c0: 0x01812403  lw x8, 24(x2)
          INT_ADD u0_11:4 <- x2_1:4, const[0x18:4]
          LOAD x8_2:4 <- u0_11:4 [m7]
        0x000111c4: 0x02010113  addi x2, x2, 32
          INT_ADD x2_2:4 <- x2_1:4, const[0x20:4]
        0x000111c8: 0x00008067  jalr x0, 0(x1)
          COPY u0_12:4 <- x1_1:4
          INT_AND u4_1:4 <- u0_12:4, const[0xfffffffe:4]
          RETURN u4_1:4`,
        annotations: ["return: uint32_t (propagated to caller)"],
      },
      {
        address: "0x11160",
        ir: `        0x00011160: 0x0040006f  jal x0, 0x11164
          BRANCH const[0x11164:4]`,
        annotations: ["(no interprocedural info)"],
      },
      {
        address: "0x11164",
        ir: `        0x00011164: 0xff442503  lw x10, -12(x8)
          INT_ADD u0_13:4 <- x8_1:4, const[0xfffffff4:4]
          LOAD x10_5:4 <- u0_13:4 [m7]
        0x00011168: 0xfe842583  lw x11, -24(x8)
          INT_ADD u0_14:4 <- x8_1:4, const[0xffffffe8:4]
          LOAD x11_3:4 <- u0_14:4 [m7]
        0x0001116c: 0x00359593  slli x11, x11, 3
          INT_LEFT x11_4:4 <- x11_3:4, const[0x3:4]
        0x00011170: 0x00b50533  add x10, x10, x11
          INT_ADD x10_6:4 <- x10_5:4, x11_4:4
        0x00011174: 0x00052583  lw x11, 0(x10)
          COPY u0_15:4 <- x10_6:4
          LOAD x11_5:4 <- u0_15:4 [m7]
        0x00011178: 0xfec42503  lw x10, -20(x8)
          INT_ADD u0_16:4 <- x8_1:4, const[0xffffffec:4]
          LOAD x10_7:4 <- u0_16:4 [m7]
        0x0001117c: 0x00b50533  add x10, x10, x11
          INT_ADD x10_8:4 <- x10_7:4, x11_5:4
        0x00011180: 0xfea42623  sw x10, -20(x8)
          INT_ADD u0_17:4 <- x8_1:4, const[0xffffffec:4]
          STORE u0_17:4, x10_8:4 [m7 -> m8]
        0x00011184: 0xff442503  lw x10, -12(x8)
          INT_ADD u0_18:4 <- x8_1:4, const[0xfffffff4:4]
          LOAD x10_9:4 <- u0_18:4 [m8]
        0x00011188: 0xfe842583  lw x11, -24(x8)
          INT_ADD u0_19:4 <- x8_1:4, const[0xffffffe8:4]
          LOAD x11_6:4 <- u0_19:4 [m8]
        0x0001118c: 0x00359593  slli x11, x11, 3
          INT_LEFT x11_7:4 <- x11_6:4, const[0x3:4]
        0x00011190: 0x00b50533  add x10, x10, x11
          INT_ADD x10_10:4 <- x10_9:4, x11_7:4
        0x00011194: 0x00452583  lw x11, 4(x10)
          INT_ADD u0_20:4 <- x10_10:4, const[0x4:4]
          LOAD x11_8:4 <- u0_20:4 [m8]
        0x00011198: 0xfec42503  lw x10, -20(x8)
          INT_ADD u0_21:4 <- x8_1:4, const[0xffffffec:4]
          LOAD x10_11:4 <- u0_21:4 [m8]
        0x0001119c: 0x00b50533  add x10, x10, x11
          INT_ADD x10_12:4 <- x10_11:4, x11_8:4
        0x000111a0: 0xfea42623  sw x10, -20(x8)
          INT_ADD u0_22:4 <- x8_1:4, const[0xffffffec:4]
          STORE u0_22:4, x10_12:4 [m8 -> m9]
        0x000111a4: 0x0040006f  jal x0, 0x111a8
          BRANCH const[0x111a8:4]`,
        annotations: ["(no interprocedural info)"],
      },
      {
        address: "0x111a8",
        ir: `        0x000111a8: 0xfe842503  lw x10, -24(x8)
          INT_ADD u0_23:4 <- x8_1:4, const[0xffffffe8:4]
          LOAD x10_13:4 <- u0_23:4 [m9]
        0x000111ac: 0x00150513  addi x10, x10, 1
          INT_ADD x10_14:4 <- x10_13:4, const[0x1:4]
        0x000111b0: 0xfea42423  sw x10, -24(x8)
          INT_ADD u0_24:4 <- x8_1:4, const[0xffffffe8:4]
          STORE u0_24:4, x10_14:4 [m9 -> m10]
        0x000111b4: 0xfa1ff06f  jal x0, 0x11154
          BRANCH const[0x11154:4]`,
        annotations: ["(no interprocedural info)"],
      }
        ],
        edges: [
      { source: "0x1112c", target: "0x11154", type: "normal" },
      { source: "0x11154", target: "0x111b8", label: "taken: i >= n", type: "normal" },
      { source: "0x11154", target: "0x11160", label: "fall: i < n", type: "normal" },
      { source: "0x11160", target: "0x11164", type: "normal" },
      { source: "0x11164", target: "0x111a8", type: "normal" },
      { source: "0x111a8", target: "0x11154", label: "back edge", type: "back" },
        ],
      },
    },
  },

  /* ── 16: CONTROL FLOW STRUCTURING ──────────────────────────────────────────────── */
  {
    id: "structuring",
    number: 16,
    name: "Control Flow Structuring",
    phase: "backend",
    description: "The CFG is collapsed into high-level control structures. main is a simple block. parse_record has a while loop with header at 0x11154, body blocks at 0x11164 and 0x111a8, and exit at 0x111b8. No gotos needed.",
    githubDir: "tiny_dec/structuring",
    viewMode: "cfg",
    content: `  root: 0x110e4
  order: 0x110e4, 0x1112c
  pending:
  invalidated:
  externals:
    <none>
  call_graph:
    0x110e4@0x11118 -> internal 0x1112c name=parse_record
  scheduler_invalidations:
    <none>
  functions:
    function 0x110e4 name=main frame_size=32 dynamic_sp=no stmts=1 loops=0 ifs=0 switches=0 gotos=0 pending=[]
    body:
      block 0x110e4
    function 0x1112c name=parse_record frame_size=32 dynamic_sp=no stmts=5 loops=1 ifs=0 switches=0 gotos=0 pending=[]
    body:
      block 0x1112c
      while header=0x11154 body=0x11160 exit=0x111b8
      body:
        block 0x11164
        block 0x111a8
      block 0x111b8`,
    cfg: {
      main: {
        blocks: [
      {
        address: "0x110e4",
        ir: `    0x000110e4: 0xfe010113  addi x2, x2, -32
      INT_ADD register[0x2:4] <- register[0x2:4], const[0xffffffe0:4]
    0x000110e8: 0x00112e23  sw x1, 28(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x1c:4]
      STORE unique[0x0:4], register[0x1:4]
    0x000110ec: 0x00812c23  sw x8, 24(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x18:4]
      STORE unique[0x0:4], register[0x8:4]
    0x000110f0: 0x02010413  addi x8, x2, 32
      INT_ADD register[0x8:4] <- register[0x2:4], const[0x20:4]
    0x000110f4: 0x01400513  addi x10, x0, 20
      COPY register[0xa:4] <- const[0x14:4]
    0x000110f8: 0xfea42a23  sw x10, -12(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff4:4]
      STORE unique[0x0:4], register[0xa:4]
    0x000110fc: 0x00200593  addi x11, x0, 2
      COPY register[0xb:4] <- const[0x2:4]
    0x00011100: 0xfeb42823  sw x11, -16(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff0:4]
      STORE unique[0x0:4], register[0xb:4]
    0x00011104: 0x00a00513  addi x10, x0, 10
      COPY register[0xa:4] <- const[0xa:4]
    0x00011108: 0xfea42623  sw x10, -20(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffec:4]
      STORE unique[0x0:4], register[0xa:4]
    0x0001110c: 0x00100513  addi x10, x0, 1
      COPY register[0xa:4] <- const[0x1:4]
    0x00011110: 0xfea42423  sw x10, -24(x8)
      INT_ADD unique[0x0:4] <- register[0x8:4], const[0xffffffe8:4]
      STORE unique[0x0:4], register[0xa:4]
    0x00011114: 0xfe840513  addi x10, x8, -24
      INT_ADD register[0xa:4] <- register[0x8:4], const[0xffffffe8:4]
    0x00011118: 0x014000ef  jal x1, 0x1112c
      COPY register[0x1:4] <- const[0x1111c:4]
      CALL const[0x1112c:4]
    0x0001111c: 0x01c12083  lw x1, 28(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x1c:4]
      LOAD unique[0x4:4] <- unique[0x0:4]
      COPY register[0x1:4] <- unique[0x4:4]
    0x00011120: 0x01812403  lw x8, 24(x2)
      INT_ADD unique[0x0:4] <- register[0x2:4], const[0x18:4]
      LOAD unique[0x4:4] <- unique[0x0:4]
      COPY register[0x8:4] <- unique[0x4:4]
    0x00011124: 0x02010113  addi x2, x2, 32
      INT_ADD register[0x2:4] <- register[0x2:4], const[0x20:4]
    0x00011128: 0x00008067  jalr x0, 0(x1)
      COPY unique[0x0:4] <- register[0x1:4]
      INT_AND unique[0x4:4] <- unique[0x0:4], const[0xfffffffe:4]
      RETURN unique[0x4:4]`,
      },
        ],
        edges: [],
      },
      parse_record: {
        blocks: [
      {
        address: "0x1112c",
        ir: `        0x0001112c: 0xfe010113  addi x2, x2, -32
          INT_ADD x2_1:4 <- x2_0:4, const[0xffffffe0:4]
        0x00011130: 0x00112e23  sw x1, 28(x2)
          INT_ADD u0_0:4 <- x2_1:4, const[0x1c:4]
          STORE u0_0:4, x1_0:4 [m0 -> m1]
        0x00011134: 0x00812c23  sw x8, 24(x2)
          INT_ADD u0_1:4 <- x2_1:4, const[0x18:4]
          STORE u0_1:4, x8_0:4 [m1 -> m2]
        0x00011138: 0x02010413  addi x8, x2, 32
          INT_ADD x8_1:4 <- x2_1:4, const[0x20:4]
        0x0001113c: 0xfea42623  sw x10, -20(x8)
          INT_ADD u0_2:4 <- x8_1:4, const[0xffffffec:4]
          STORE u0_2:4, x10_0:4 [m2 -> m3]
        0x00011140: 0xfeb42423  sw x11, -24(x8)
          INT_ADD u0_3:4 <- x8_1:4, const[0xffffffe8:4]
          STORE u0_3:4, x11_0:4 [m3 -> m4]
        0x00011144: 0xfe042223  sw x0, -28(x8)
          INT_ADD u0_4:4 <- x8_1:4, const[0xffffffe4:4]
          STORE u0_4:4, const[0x0:4] [m4 -> m5]
        0x00011148: 0xfe042023  sw x0, -32(x8)
          INT_ADD u0_5:4 <- x8_1:4, const[0xffffffe0:4]
          STORE u0_5:4, const[0x0:4] [m5 -> m6]
        0x0001114c: 0x0080006f  jal x0, 0x11154
          BRANCH const[0x11154:4]`,
      },
      {
        address: "0x11154",
        label: "loop header",
        ir: `        0x00011154: 0xfe042503  lw x10, -32(x8)
          INT_ADD u0_6:4 <- x8_1:4, const[0xffffffe0:4]
          LOAD x10_1:4 <- u0_6:4 [m6]
        0x00011158: 0xfe842583  lw x11, -24(x8)
          INT_ADD u0_7:4 <- x8_1:4, const[0xffffffe8:4]
          LOAD x11_1:4 <- u0_7:4 [m6]
        0x0001115c: 0x00b54463  blt x10, x11, 0x11164
          INT_SLESS u0_8:1 <- x10_1:4, x11_1:4
          CBRANCH u0_8:1, const[0x11164:4]`,
      },
      {
        address: "0x111b8",
        ir: `        0x000111b8: 0xfec42503  lw x10, -20(x8)
          INT_ADD u0_9:4 <- x8_1:4, const[0xffffffec:4]
          LOAD x10_4:4 <- u0_9:4 [m7]
        0x000111bc: 0x01c12083  lw x1, 28(x2)
          INT_ADD u0_10:4 <- x2_1:4, const[0x1c:4]
          LOAD x1_1:4 <- u0_10:4 [m7]
        0x000111c0: 0x01812403  lw x8, 24(x2)
          INT_ADD u0_11:4 <- x2_1:4, const[0x18:4]
          LOAD x8_2:4 <- u0_11:4 [m7]
        0x000111c4: 0x02010113  addi x2, x2, 32
          INT_ADD x2_2:4 <- x2_1:4, const[0x20:4]
        0x000111c8: 0x00008067  jalr x0, 0(x1)
          COPY u0_12:4 <- x1_1:4
          INT_AND u4_1:4 <- u0_12:4, const[0xfffffffe:4]
          RETURN u4_1:4`,
      },
      {
        address: "0x11160",
        ir: `        0x00011160: 0x0040006f  jal x0, 0x11164
          BRANCH const[0x11164:4]`,
      },
      {
        address: "0x11164",
        ir: `        0x00011164: 0xff442503  lw x10, -12(x8)
          INT_ADD u0_13:4 <- x8_1:4, const[0xfffffff4:4]
          LOAD x10_5:4 <- u0_13:4 [m7]
        0x00011168: 0xfe842583  lw x11, -24(x8)
          INT_ADD u0_14:4 <- x8_1:4, const[0xffffffe8:4]
          LOAD x11_3:4 <- u0_14:4 [m7]
        0x0001116c: 0x00359593  slli x11, x11, 3
          INT_LEFT x11_4:4 <- x11_3:4, const[0x3:4]
        0x00011170: 0x00b50533  add x10, x10, x11
          INT_ADD x10_6:4 <- x10_5:4, x11_4:4
        0x00011174: 0x00052583  lw x11, 0(x10)
          COPY u0_15:4 <- x10_6:4
          LOAD x11_5:4 <- u0_15:4 [m7]
        0x00011178: 0xfec42503  lw x10, -20(x8)
          INT_ADD u0_16:4 <- x8_1:4, const[0xffffffec:4]
          LOAD x10_7:4 <- u0_16:4 [m7]
        0x0001117c: 0x00b50533  add x10, x10, x11
          INT_ADD x10_8:4 <- x10_7:4, x11_5:4
        0x00011180: 0xfea42623  sw x10, -20(x8)
          INT_ADD u0_17:4 <- x8_1:4, const[0xffffffec:4]
          STORE u0_17:4, x10_8:4 [m7 -> m8]
        0x00011184: 0xff442503  lw x10, -12(x8)
          INT_ADD u0_18:4 <- x8_1:4, const[0xfffffff4:4]
          LOAD x10_9:4 <- u0_18:4 [m8]
        0x00011188: 0xfe842583  lw x11, -24(x8)
          INT_ADD u0_19:4 <- x8_1:4, const[0xffffffe8:4]
          LOAD x11_6:4 <- u0_19:4 [m8]
        0x0001118c: 0x00359593  slli x11, x11, 3
          INT_LEFT x11_7:4 <- x11_6:4, const[0x3:4]
        0x00011190: 0x00b50533  add x10, x10, x11
          INT_ADD x10_10:4 <- x10_9:4, x11_7:4
        0x00011194: 0x00452583  lw x11, 4(x10)
          INT_ADD u0_20:4 <- x10_10:4, const[0x4:4]
          LOAD x11_8:4 <- u0_20:4 [m8]
        0x00011198: 0xfec42503  lw x10, -20(x8)
          INT_ADD u0_21:4 <- x8_1:4, const[0xffffffec:4]
          LOAD x10_11:4 <- u0_21:4 [m8]
        0x0001119c: 0x00b50533  add x10, x10, x11
          INT_ADD x10_12:4 <- x10_11:4, x11_8:4
        0x000111a0: 0xfea42623  sw x10, -20(x8)
          INT_ADD u0_22:4 <- x8_1:4, const[0xffffffec:4]
          STORE u0_22:4, x10_12:4 [m8 -> m9]
        0x000111a4: 0x0040006f  jal x0, 0x111a8
          BRANCH const[0x111a8:4]`,
      },
      {
        address: "0x111a8",
        ir: `        0x000111a8: 0xfe842503  lw x10, -24(x8)
          INT_ADD u0_23:4 <- x8_1:4, const[0xffffffe8:4]
          LOAD x10_13:4 <- u0_23:4 [m9]
        0x000111ac: 0x00150513  addi x10, x10, 1
          INT_ADD x10_14:4 <- x10_13:4, const[0x1:4]
        0x000111b0: 0xfea42423  sw x10, -24(x8)
          INT_ADD u0_24:4 <- x8_1:4, const[0xffffffe8:4]
          STORE u0_24:4, x10_14:4 [m9 -> m10]
        0x000111b4: 0xfa1ff06f  jal x0, 0x11154
          BRANCH const[0x11154:4]`,
      }
        ],
        edges: [
      { source: "0x1112c", target: "0x11154", type: "normal" },
      { source: "0x11154", target: "0x111b8", label: "taken: i >= n", type: "normal" },
      { source: "0x11154", target: "0x11160", label: "fall: i < n", type: "normal" },
      { source: "0x11160", target: "0x11164", type: "normal" },
      { source: "0x11164", target: "0x111a8", type: "normal" },
      { source: "0x111a8", target: "0x11154", label: "back edge", type: "back" },
        ],
        regions: [
      { type: "while", label: "while (i < count)", blocks: ["0x11154", "0x11160", "0x11164", "0x111a8"], color: "#a78bfa" },
        ],
      },
    },
  },

  /* ── 17: C LOWERING ──────────────────────────────────────────────── */
  {
    id: "c_lowering",
    number: 17,
    name: "C Lowering",
    phase: "backend",
    description: "The structured IR is lowered to C-like statements with typed variables. parse_record becomes: initialize locals, while (local_24_4 <s arg_x11_4) body with arg_x10_4[local_24_4].field_0 and .field_4 accesses, return accumulator.",
    githubDir: "tiny_dec/c_emit",
    viewMode: "text",
    content: `  root: 0x110e4
  order: 0x110e4, 0x1112c
  pending:
  invalidated:
  externals:
    <none>
  call_graph:
    0x110e4@0x11118 -> internal 0x1112c name=parse_record
  scheduler_invalidations:
    <none>
  functions:
    function 0x110e4 name=main frame_size=32 dynamic_sp=no params=0 locals=5 returns=1 stmts=7 pending=[]
    signature:
      <none>
    returns:
      return x10 word32_t
    locals:
      local int32_t local_24_4
      local int32_t local_20_4
      local int32_t local_16_4
      local int32_t local_12_4
      local word32_t ret_0x11118_x10_4
    body:
      local_12_4 = 20;
      local_16_4 = 2;
      local_20_4 = 10;
      local_24_4 = 1;
      parse_record(&local_24_4, 2);
      ret_0x11118_x10_4 = raw<x10_5:4>;
      return [x10=ret_0x11118_x10_4];
    function 0x1112c name=parse_record frame_size=32 dynamic_sp=no params=2 locals=2 returns=1 stmts=7 pending=[]
    signature:
      param x10 agg_8* arg_x10_4
      param x11 int32_t arg_x11_4
    returns:
      return x10 word32_t
    locals:
      local int32_t local_24_4
      local int32_t local_20_4
    body:
      local_20_4 = 0;
      local_24_4 = 0;
      while (local_24_4 <s arg_x11_4)
      body:
        local_20_4 = local_20_4 + arg_x10_4[local_24_4].field_0;
        local_20_4 = local_20_4 + arg_x10_4[local_24_4].field_4;
        local_24_4 = local_24_4 + 1;
      return [x10=local_20_4];`,
  },

  /* ── 18: FINAL C ──────────────────────────────────────────────── */
  {
    id: "c",
    number: 18,
    name: "Final C",
    phase: "backend",
    description: "The final rendered C includes a typedef struct agg_8 with two int32_t fields, forward declarations, and two complete function bodies. parse_record iterates an array of structs, summing both fields. From 232 bytes to readable C.",
    githubDir: "tiny_dec/pipeline",
    viewMode: "text",
    content: `/* root: 0x110e4 */
/* scheduled_roots: 0x110e4 */
/* pending: none */
/* invalidated: none */
/* scheduler_invalidations: none */

#include <stdint.h>

typedef struct agg_8 {
  int32_t field_0;
  int32_t field_4;
} agg_8;

static uint32_t main(void);
static uint32_t parse_record(agg_8* arg_x10_4, int32_t arg_x11_4);

static uint32_t main(void) {
  int32_t local_24_4;
  int32_t local_20_4;
  int32_t local_16_4;
  int32_t local_12_4;
  uint32_t call_0x11118_ret;

  local_12_4 = 20;
  local_16_4 = 2;
  local_20_4 = 10;
  local_24_4 = 1;
  call_0x11118_ret = parse_record(&local_24_4, 2);
  return call_0x11118_ret;
}

static uint32_t parse_record(agg_8* arg_x10_4, int32_t arg_x11_4) {
  int32_t local_24_4;
  int32_t local_20_4;

  local_20_4 = 0;
  local_24_4 = 0;
  while (local_24_4 <s arg_x11_4) {
    local_20_4 = local_20_4 + arg_x10_4[local_24_4].field_0;
    local_20_4 = local_20_4 + arg_x10_4[local_24_4].field_4;
    local_24_4 = local_24_4 + 1;
  }
  return local_20_4;
}`,
  },
];

export default STAGES;

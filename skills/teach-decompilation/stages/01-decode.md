# Stage 01: Decode

## What It Does
The decoder reads raw 32-bit instruction words from the loaded binary and turns each one into a structured Python object. Every RV32I instruction is exactly 4 bytes — the decoder reads those bytes, extracts the opcode, registers, and immediates, and creates an `Instruction` object.

**Analogy:** Decoding is like parsing a sentence — the raw bytes are just letters, but the decoder identifies the verb (opcode), subject (destination register), and objects (source registers, immediates).

## Key Concepts
- **Instruction encoding**: RV32I has a few encoding formats (R-type, I-type, S-type, B-type, U-type, J-type) that pack opcode, registers, and immediates into 32 bits in different ways.
- **Opcode extraction**: The lowest 7 bits of every instruction identify the instruction type.
- **Immediate decoding**: Immediates are scattered across different bit positions depending on the format — the decoder reassembles them.

## Source Files
- `tiny_dec/decode/decoder.py` — `decode_rv32i()` is the main entry point. It dispatches on opcode to format-specific decoders.
- `tiny_dec/decode/` — Look at how each format (R, I, S, B, U, J) extracts fields from the instruction word.

Start with `decode_rv32i()` and trace how it handles one instruction type (e.g., `addi`).

## CLI Demonstration

```bash
# Decode the basic fixture
tiny-dec decompile tests/fixtures/bin/fixture_basic_O0_nopie.elf --stage decode --func main
```

Each line shows one decoded instruction: mnemonic, destination, sources, immediate. Compare this with what you know the C code does (`tests/fixtures/src/fixture_basic.c`).

## Quiz

**Q1:** RV32I instructions are always 4 bytes. Why is this significant for decoding, compared to x86 where instructions vary from 1-15 bytes?

<details>
<summary>Answer</summary>
Fixed-width instructions mean the decoder always knows where the next instruction starts — just add 4 to the current address. Variable-length encodings (x86) require the decoder to fully parse each instruction before knowing where the next one begins, which makes parallel decoding and disassembly much harder.
</details>

**Q2:** What are the source and destination registers in `addi x10, x0, 7`? What does this instruction compute?

<details>
<summary>Answer</summary>
Source: x0 (the hard-wired zero register). Destination: x10. This computes x10 = 0 + 7, which is just loading the constant 7 into x10. This is a common RISC-V idiom — `addi rd, x0, imm` is how you load a small constant.
</details>

## Dynamic Exercise

Look at the decode output for `fixture_loop_O0_nopie.elf`:
```bash
tiny-dec decompile tests/fixtures/bin/fixture_loop_O0_nopie.elf --stage decode --func sum_to_n
```
"Find the branch instruction that controls the loop. What register comparison does it make? Can you guess which C variable each register holds?"

## Advanced Exercise (Modification)

```bash
git checkout -b learn/stage-01-decode
```
Open `tiny_dec/decode/decoder.py`. Find where `addi` is decoded (opcode `0x13`, funct3 `0x0`). The RISC-V pseudo-instruction `li rd, imm` (load immediate) is really just `addi rd, x0, imm`. Add a special case: when the source register is x0, change the decoded mnemonic from `addi` to a new `li` pseudo-mnemonic. Run on `fixture_basic_O0_nopie.elf --stage decode --func main` and see if your `li` instructions appear where you'd expect constant loads.

**Why this matters:** Real disassemblers (objdump, Ghidra) display pseudo-mnemonics for readability. This is your first taste of making raw output more human-friendly.

**Test idea:** Decode an instruction word for `addi x10, x0, 7`. Assert the mnemonic is `li` and the immediate is 7.

When done: `git checkout main`

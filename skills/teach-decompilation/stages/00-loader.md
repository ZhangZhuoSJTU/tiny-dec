# Stage 00: Loader

## What It Does
The loader is the front door of the decompiler. It reads a raw ELF binary file and extracts the metadata needed to start analysis: where the code lives in memory, what symbols (function names) exist, and where `main` is.

**Analogy:** The loader is like opening a book's table of contents — you haven't read the chapters yet, but you know what's there and where to find it.

## Key Concepts
- **ELF format**: The standard binary format on Linux. Contains headers, sections (.text for code, .data for globals), and a symbol table.
- **Symbol resolution**: Matching names like `main`, `helper`, `malloc` to their memory addresses.
- **Main discovery**: Finding the entry point. The ELF header points to `_start`, but tiny-dec first checks the symbol table, then falls back to a heuristic that scans `_start` for the `__libc_start_main` call and extracts its first argument.

## Source Files
- `tiny_dec/loader/program_view.py` — The main `ProgramView` class that wraps ELF loading
- `tiny_dec/loader/api.py` — `read_bytes()` reads raw bytes from the binary image
- `tiny_dec/loader/main_locator.py` — Heuristics for finding `main` when symbols are stripped
- `tiny_dec/loader/models.py` — Data models for sections, symbols, and binary metadata

Walk through `program_view.py` first — it's the entry point. Then look at `main_locator.py` for the interesting heuristic logic.

## CLI Demonstration

```bash
# Show all loader-visible metadata
tiny-dec info tests/fixtures/bin/fixture_basic_O0_nopie.elf

# Show just the loader stage output
tiny-dec decompile tests/fixtures/bin/fixture_basic_O0_nopie.elf --stage loader --func main
```

Compare the info output with what you see in the source code of `ProgramView.__init__`.

## Quiz

**Q1:** What information does the ELF header provide that the loader needs before it can start decoding instructions?

<details>
<summary>Answer</summary>
The ELF header provides: the architecture (RISC-V), the bitness (32-bit), the endianness (little-endian), the entry point address, and pointers to the section and program header tables. The loader needs to know where the code section (.text) lives in memory and what the entry address is before it can start finding functions.
</details>

**Q2:** Why does tiny-dec need a special heuristic to find `main` instead of just reading it from the symbol table?

<details>
<summary>Answer</summary>
Stripped binaries have no symbol table — function names are removed. Even in non-stripped binaries, the ELF entry point is `_start` (the C runtime setup), not `main`. The loader scans `_start` for the call to `__libc_start_main`, then looks backward from that call to find the `a0` register setup — because the first argument to `__libc_start_main` is the address of `main`.
</details>

## Dynamic Exercise

Run `tiny-dec info` on two different fixtures and compare:
```bash
tiny-dec info tests/fixtures/bin/fixture_basic_O0_nopie.elf
tiny-dec info tests/fixtures/bin/fixture_basic_O2_pie.elf
```
Before running the second command, **predict:** PIE (position-independent) binaries can be loaded at any address. How do you think that affects the addresses you'll see? Now compare — what differences do you notice? Why are the addresses different?

## Advanced Exercise (Modification)

```bash
git checkout -b learn/stage-00-loader
```
Open `tiny_dec/loader/main_locator.py`. Find the heuristic that scans for `main`. Try changing the scan window size and re-running `tiny-dec info` on a fixture. What happens when the window is too small?

**Note:** The provided fixtures all have symbols, so the heuristic path is never triggered — `main` is resolved directly from the symbol table. To actually exercise the heuristic, you'd need a stripped binary (compile your own with `strip` or use the Docker environment).

When done: `git checkout main`

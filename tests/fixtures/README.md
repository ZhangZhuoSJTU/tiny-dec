# Fixture Binaries

This directory contains controlled C fixtures used by post-based test suites.

- Source files: `tests/fixtures/src/`
- Generated binaries: `tests/fixtures/bin/`
- Build script: `scripts/build_fixtures.sh`

## Goal
Generate **Linux ELF32 RISC-V (pure RV32I)** binaries.

Pure RV32I means no `M/A/C` (or other) ISA extensions in the final ELF.
In practice, startup/runtime objects from libc can silently add extensions even
if your compile flags include `-march=rv32i`, so always validate output.

Expected output naming:
- `<fixture>_O0_nopie.elf`
- `<fixture>_O2_nopie.elf`
- `<fixture>_O2_pie.elf`

## Build

```bash
cd tiny_dec
./scripts/build_fixtures.sh
```

The script defaults to:
- `-march=rv32i -mabi=ilp32`
- compiler auto-detection: `riscv64-linux-gnu-gcc` then `riscv64-unknown-linux-gnu-gcc`
- strict ISA check enabled: `STRICT_RV32I=1`

Strict check behavior:
- Reads `Tag_RISCV_arch` from the generated ELF.
- Accepts only base `rv32i` (optionally with `zicsr` / `zifencei`).
- Fails if extensions like `m`, `a`, `c`, `zca`, etc. appear.

Override example:

```bash
CC=riscv64-unknown-linux-gnu-gcc TARGET_CFLAGS="-march=rv32i -mabi=ilp32" ./scripts/build_fixtures.sh
```

Temporary escape hatch (not pure RV32I):

```bash
STRICT_RV32I=0 ./scripts/build_fixtures.sh
```

## Verify output ISA

Check one binary:

```bash
readelf -A tests/fixtures/bin/fixture_basic_O0_nopie.elf | grep Tag_RISCV_arch
```

Expected to look like:
- `rv32i...`
- optionally `_zicsr...` and/or `_zifencei...`
- must **not** contain `_m`, `_a`, `_c`, `_zc*`

## Toolchain Installation

### Option A (Recommended): Build the official GNU RISC-V toolchain with multilib
This is the most reliable way to ensure `rv32i/ilp32` is available.

Ubuntu/Debian prerequisites (from upstream toolchain README):

```bash
sudo apt-get update
sudo apt-get install -y \
  autoconf automake autotools-dev curl python3 python3-tomli \
  libmpc-dev libmpfr-dev libgmp-dev gawk build-essential bison flex texinfo gperf \
  libtool patchutils bc zlib1g-dev libexpat-dev ninja-build git cmake libglib2.0-dev
```

macOS prerequisites (from upstream toolchain README):

```bash
brew install python3 gawk gnu-sed gmp mpfr libmpc isl zlib expat texinfo flock libslirp
```

```bash
git clone https://github.com/riscv-collab/riscv-gnu-toolchain
cd riscv-gnu-toolchain
./configure --prefix=/opt/riscv --enable-multilib
make linux -j"$(nproc)"
```

Then add to `PATH`:

```bash
export PATH=/opt/riscv/bin:$PATH
```

Notes:
- On macOS, upstream notes case-sensitive filesystem requirements when building from source.

### Option B: Use a Linux container on macOS
If you do not want to install a native cross toolchain on macOS, run the build inside a Linux container and mount this repo.

## Troubleshooting
- If the script says multilib support is missing, your compiler does not provide `rv32i/ilp32`.
- Rebuild/install a toolchain with `--enable-multilib`.
- If the script fails strict ISA verification, your libc/startup multilib is not
  truly RV32I (common with distro cross toolchains). Use a toolchain/sysroot
  that provides pure `rv32i/ilp32` runtime objects.

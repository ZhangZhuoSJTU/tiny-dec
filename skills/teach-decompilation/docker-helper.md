# Docker Helper — Custom Code Compilation

This guide is for when users want to compile their own C code to RV32I and decompile it with tiny-dec.

## Prerequisites Check

Run these checks in order:

1. **Docker available?**
   ```bash
   docker --version
   ```
   If this fails, tell the user: "Docker isn't installed or not in PATH. You can still learn with the 13 pre-built fixture binaries in `tests/fixtures/bin/`. If you'd like to try your own code later, install Docker and come back."

2. **Dev image built?**
   ```bash
   docker images tiny-dec-dev --format "{{.Repository}}"
   ```
   If empty, build it:
   ```bash
   docker build -t tiny-dec-dev -f docker/Dockerfile.dev .
   ```
   This takes 2-3 minutes. The image is based on `silkeh/clang:21-trixie` and includes clang with RISC-V support, lld, and Python.

## Compiling User Code

When a user provides C code:

1. **Write to a temp file** in the repo root:
   ```bash
   cat > user_code.c << 'CEOF'
   <user's C code here>
   CEOF
   ```

2. **Compile inside the container.** Three variants are available:

   **Unoptimized (recommended for learning — predictable stack layout):**
   ```bash
   docker run --rm -v "$(pwd):/workspace" tiny-dec-dev \
     clang --target=riscv32-unknown-elf \
     -march=rv32i -mabi=ilp32 \
     -std=c11 -ffreestanding -fno-builtin \
     -fuse-ld=lld -nostdlib \
     -Wl,-e,main -Wl,--unresolved-symbols=ignore-all \
     -O0 -fno-pie \
     /workspace/user_code.c -o /workspace/user_code.elf
   ```

   **Optimized (tests register allocation recovery):**
   ```bash
   docker run --rm -v "$(pwd):/workspace" tiny-dec-dev \
     clang --target=riscv32-unknown-elf \
     -march=rv32i -mabi=ilp32 \
     -std=c11 -ffreestanding -fno-builtin \
     -fuse-ld=lld -nostdlib \
     -Wl,-e,main -Wl,--unresolved-symbols=ignore-all \
     -O2 -fno-pie \
     /workspace/user_code.c -o /workspace/user_code.elf
   ```

   **Position-independent (tests GOT/PLT handling):**
   ```bash
   docker run --rm -v "$(pwd):/workspace" tiny-dec-dev \
     clang --target=riscv32-unknown-elf \
     -march=rv32i -mabi=ilp32 \
     -std=c11 -ffreestanding -fno-builtin \
     -fuse-ld=lld -nostdlib \
     -Wl,-e,main -Wl,--unresolved-symbols=ignore-all \
     -O2 -fpie -Wl,-pie \
     /workspace/user_code.c -o /workspace/user_code.elf
   ```

3. **Decompile:**
   ```bash
   tiny-dec decompile user_code.elf --stage <stage> --func main
   ```

4. **Clean up** when done:
   ```bash
   rm -f user_code.c user_code.elf
   ```

## Code Requirements

User C code must follow these constraints for tiny-dec:
- Entry point must be named `main`
- No standard library (use `-ffreestanding -fno-builtin -nostdlib`)
- External functions can be declared but won't be linked (uses `--unresolved-symbols=ignore-all`)
- RV32I only — no floating point, no atomics, no compressed instructions
- Use `int` (32-bit) types; avoid `long long` or 64-bit types

**Good starter example to suggest:**
```c
static int factorial(int n) {
    int result = 1;
    for (int i = 2; i <= n; i++) {
        result *= i;
    }
    return result;
}

int main(void) {
    return factorial(5);
}
```

## Comparison Exercise

A powerful learning exercise: have the user write C code, compile at -O0 and -O2, then compare how tiny-dec decompiles each:

```bash
# Compile both variants
docker run --rm -v "$(pwd):/workspace" tiny-dec-dev \
  clang --target=riscv32-unknown-elf -march=rv32i -mabi=ilp32 \
  -std=c11 -ffreestanding -fno-builtin -fuse-ld=lld -nostdlib \
  -Wl,-e,main -Wl,--unresolved-symbols=ignore-all \
  -O0 -fno-pie /workspace/user_code.c -o /workspace/user_code_O0.elf

docker run --rm -v "$(pwd):/workspace" tiny-dec-dev \
  clang --target=riscv32-unknown-elf -march=rv32i -mabi=ilp32 \
  -std=c11 -ffreestanding -fno-builtin -fuse-ld=lld -nostdlib \
  -Wl,-e,main -Wl,--unresolved-symbols=ignore-all \
  -O2 -fno-pie /workspace/user_code.c -o /workspace/user_code_O2.elf

# Compare at any stage
tiny-dec decompile user_code_O0.elf --stage ssa --func main
tiny-dec decompile user_code_O2.elf --stage ssa --func main
```

Ask the user: "What differences do you notice? Why does the optimizer change things?"

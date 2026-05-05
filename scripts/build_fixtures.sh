#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC_DIR="$ROOT_DIR/tests/fixtures/src"
BIN_DIR="$ROOT_DIR/tests/fixtures/bin"

CC="${CC:-clang}"
READELF="${READELF:-readelf}"
OBJDUMP="${OBJDUMP:-llvm-objdump}"

TARGET_TRIPLE="${TARGET_TRIPLE:-riscv32-unknown-elf}"
TARGET_ARCH="${TARGET_ARCH:-rv32i}"
TARGET_ABI="${TARGET_ABI:-ilp32}"
LINKER_IMPL="${LINKER_IMPL:-lld}"

CFLAGS_COMMON="${CFLAGS_COMMON:--std=c11 -Wall -Wextra -g -ffreestanding -fno-builtin}"
TARGET_CFLAGS="${TARGET_CFLAGS:--march=${TARGET_ARCH} -mabi=${TARGET_ABI}}"
LDFLAGS_COMMON="${LDFLAGS_COMMON:--fuse-ld=${LINKER_IMPL} -nostdlib -Wl,-e,main -Wl,--unresolved-symbols=ignore-all}"
LDFLAGS_EXTRA="${LDFLAGS_EXTRA:-}"

STRICT_RV32I="${STRICT_RV32I:-1}"
STRICT_NO_COMPRESSED="${STRICT_NO_COMPRESSED:-1}"

# shellcheck disable=SC2206
COMMON_FLAGS=($CFLAGS_COMMON)
# shellcheck disable=SC2206
TARGET_FLAGS=($TARGET_CFLAGS)
# shellcheck disable=SC2206
LINK_FLAGS=($LDFLAGS_COMMON)
# shellcheck disable=SC2206
EXTRA_LDFLAGS=($LDFLAGS_EXTRA)

require_command() {
    local cmd="$1"
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "error: required command not found: $cmd" >&2
        exit 1
    fi
}

extract_riscv_arch_attr() {
    local bin="$1"
    "$READELF" -A "$bin" 2>/dev/null | sed -n 's/.*Tag_RISCV_arch: "\(.*\)"/\1/p' | head -n1
}

is_strict_rv32i_arch() {
    local arch="$1"
    local part
    local -a parts

    arch="${arch,,}"
    IFS="_" read -r -a parts <<<"$arch"

    # Accept base rv32i (with optional ISA version suffix like rv32i2p1).
    if [[ ! "${parts[0]}" =~ ^rv32i([0-9].*)?$ ]]; then
        return 1
    fi

    # Toolchains may materialize these as separate mandatory extensions.
    for part in "${parts[@]:1}"; do
        if [[ "$part" =~ ^zicsr([0-9].*)?$ ]] || [[ "$part" =~ ^zifencei([0-9].*)?$ ]]; then
            continue
        fi
        return 1
    done

    return 0
}

verify_no_compressed_instructions() {
    local bin="$1"
    local disasm_file
    disasm_file="$(mktemp)"

    "$OBJDUMP" -d "$bin" >"$disasm_file"
    if grep -Eq '^[[:space:]]*[0-9a-f]+:[[:space:]]+[0-9a-f]+[[:space:]]+c\.' "$disasm_file"; then
        echo "error: compressed instruction detected in $bin" >&2
        grep -En '^[[:space:]]*[0-9a-f]+:[[:space:]]+[0-9a-f]+[[:space:]]+c\.' "$disasm_file" | head -n5 >&2
        rm -f "$disasm_file"
        return 1
    fi

    rm -f "$disasm_file"
}

verify_elf() {
    local bin="$1"

    if command -v file >/dev/null 2>&1; then
        local info
        info="$(file "$bin")"
        if [[ "$info" != *"ELF 32-bit"* ]] || [[ "$info" != *"RISC-V"* ]]; then
            echo "error: output is not ELF32 RISC-V: $bin" >&2
            echo "detail: $info" >&2
            return 1
        fi
    fi

    local class machine
    class="$("$READELF" -h "$bin" | awk -F: '/Class:/ {gsub(/^ +/, "", $2); print $2}')"
    machine="$("$READELF" -h "$bin" | awk -F: '/Machine:/ {gsub(/^ +/, "", $2); print $2}')"

    if [[ "$class" != "ELF32" ]] || [[ "$machine" != "RISC-V" ]]; then
        echo "error: unexpected ELF header for $bin (Class=$class, Machine=$machine)" >&2
        return 1
    fi

    # EF_RISCV_RVC is bit 0x1 in e_flags. This must stay clear for RV32I-only output.
    local flags_hex flags_value
    flags_hex="$("$READELF" -h "$bin" | awk -F: '/Flags:/ {gsub(/^ +/, "", $2); split($2, a, ","); print a[1]; exit}')"
    flags_value=$((flags_hex))
    if ((flags_value & 0x1)); then
        echo "error: ELF flags indicate RVC/compressed instructions are enabled in $bin (Flags=$flags_hex)." >&2
        return 1
    fi

    if [[ "$STRICT_RV32I" == "1" ]]; then
        local arch_attr
        arch_attr="$(extract_riscv_arch_attr "$bin")"

        if [[ -z "$arch_attr" ]]; then
            echo "warning: unable to read Tag_RISCV_arch for $bin; skipping strict ISA verification." >&2
        elif ! is_strict_rv32i_arch "$arch_attr"; then
            echo "error: $bin is not pure RV32I (Tag_RISCV_arch=$arch_attr)." >&2
            return 1
        fi
    fi

    if [[ "$STRICT_NO_COMPRESSED" == "1" ]]; then
        verify_no_compressed_instructions "$bin"
    fi
}

compile_one() {
    local src="$1"
    local out="$2"
    shift 2

    "$CC" \
        "--target=${TARGET_TRIPLE}" \
        "${COMMON_FLAGS[@]}" \
        "${TARGET_FLAGS[@]}" \
        "${LINK_FLAGS[@]}" \
        "$@" \
        "${EXTRA_LDFLAGS[@]}" \
        "$src" \
        -o "$out"

    verify_elf "$out"
}

main() {
    if [[ ! -d "$SRC_DIR" ]]; then
        echo "error: source directory not found: $SRC_DIR" >&2
        exit 1
    fi

    require_command "$CC"
    require_command "$READELF"
    require_command "$OBJDUMP"

    mkdir -p "$BIN_DIR"

    local built=0
    shopt -s nullglob
    for src in "$SRC_DIR"/*.c; do
        local name
        name="$(basename "$src" .c)"

        compile_one "$src" "$BIN_DIR/${name}_O0_nopie.elf" -O0 -fno-pie
        compile_one "$src" "$BIN_DIR/${name}_O2_nopie.elf" -O2 -fno-pie
        compile_one "$src" "$BIN_DIR/${name}_O2_pie.elf" -O2 -fpie -Wl,-pie

        built=$((built + 3))
    done
    shopt -u nullglob

    if [[ "$built" -eq 0 ]]; then
        echo "error: no fixture source files found in $SRC_DIR" >&2
        exit 1
    fi

    echo "Built $built RV32I ELF binaries in: $BIN_DIR"
    echo "Compiler: $CC"
    echo "Target triple: $TARGET_TRIPLE"
    echo "Target flags: ${TARGET_FLAGS[*]}"
    echo "Link flags: ${LINK_FLAGS[*]}"
    echo "Strict RV32I verification: $STRICT_RV32I"
    echo "No-compressed-instruction verification: $STRICT_NO_COMPRESSED"
}

main "$@"

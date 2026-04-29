#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
POETRY_VERSION="${POETRY_VERSION:-2.3.2}"
CC="${CC:-clang}"

if [[ "${EUID}" -ne 0 ]]; then
    APT_PREFIX=(sudo)
else
    APT_PREFIX=()
fi

"${APT_PREFIX[@]}" apt-get update
"${APT_PREFIX[@]}" apt-get install -y \
    binutils \
    build-essential \
    ca-certificates \
    clang \
    cmake \
    file \
    git \
    lld \
    llvm \
    pkg-config \
    python3 \
    python3-pip \
    python3-venv

python3 -m pip install --break-system-packages --no-cache-dir "poetry==${POETRY_VERSION}"

cd "${ROOT_DIR}"
"${CC}" --version | head -n1
llvm-objdump --version | head -n1
readelf --version | head -n1
poetry --version

CC="${CC}" ./scripts/build_fixtures.sh

echo "LLVM-based RV32I fixture toolchain is ready."
echo "Fixtures rebuilt with strict no-compressed-instruction verification."

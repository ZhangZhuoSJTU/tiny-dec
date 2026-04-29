#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE_NAME="${TINY_DEC_DEV_IMAGE:-rv32i-llvm:latest}"
DOCKER_PLATFORM="${DOCKER_PLATFORM:-linux/amd64}"
CONTAINER_HOME="${ROOT_DIR}/.container-home"

mkdir -p "${CONTAINER_HOME}"

docker build --platform "${DOCKER_PLATFORM}" -f "${ROOT_DIR}/docker/Dockerfile.dev" -t "${IMAGE_NAME}" "${ROOT_DIR}"

DOCKER_ARGS=(
    --rm
    --platform "${DOCKER_PLATFORM}"
    --user "$(id -u):$(id -g)"
    -e HOME=/tmp/tinydec-home
    -e POETRY_CACHE_DIR=/tmp/tinydec-home/.cache/pypoetry
    -e PIP_CACHE_DIR=/tmp/tinydec-home/.cache/pip
    -v "${ROOT_DIR}:/workspace"
    -v "${CONTAINER_HOME}:/tmp/tinydec-home"
    -w /workspace
)

if [[ "$#" -eq 0 ]]; then
    docker run -it "${DOCKER_ARGS[@]}" "${IMAGE_NAME}" bash
else
    docker run "${DOCKER_ARGS[@]}" "${IMAGE_NAME}" bash -lc "$*"
fi

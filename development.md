# tiny_dec Development Plan

## Scope
`tiny_dec` is an educational decompiler pipeline for Linux ELF inputs, currently
implemented through `post_18_c_printer_pipeline`.

The current implemented architecture lives in `implementation.md`.
This file is the working development guide: environment, workflow, ownership,
validation rhythm, and the staged implementation plan.

Target pipeline:

`ELF bytes -> instruction decode -> semantic p-code -> disasm (basic blocks + CFG) -> IR containers -> analysis -> structuring -> C-like output -> rendered C`

Constraints:
- Input format: Linux ELF, with RV32I-focused fixtures.
- Loader backend: `pwntools`.
- Teaching-first design: explicit stages, deterministic debug dumps, and small
  typed data structures.
- Only implemented stages should expose public APIs and CLI stage stops.
- Later analyses may re-discover functions or CFG edges, so the architecture
  must support re-invocation of earlier stages through explicit worklists.

## Development Environment (Linux-First)

`tiny_dec` should be developed inside Linux. On macOS, especially Apple
Silicon, `pwntools` dependencies may fail to build cleanly natively.

Use the repository-provided Docker workflow instead of relying on host-native
tooling.

### Prerequisites
- Docker Desktop, Colima, or another Docker-compatible runtime.
- A working shell with access to the repository root.

### Recommended Workflow (macOS -> Linux container)

Build the development image and open an interactive Linux shell:
```bash
cd /workspace
./scripts/dev_linux.sh
```

Run one command inside the Linux environment without entering a shell:
```bash
cd /workspace
./scripts/dev_linux.sh "poetry install"
./scripts/dev_linux.sh "poetry run pytest -q tests/posts/post_18_c_printer_pipeline/test_c_printer_pipeline_e2e_harness.py"
```

The helper script:
- builds `docker/Dockerfile.dev`
- mounts the repository at `/workspace`
- stores Poetry and pip caches in `.container-home/`
- runs container commands as the host UID/GID to avoid root-owned files

### VS Code Workflow (host editor + container runtime)

This repository includes `.devcontainer/devcontainer.json` so VS Code can run
all Python and toolchain work inside the Linux container.

Prerequisites:
- VS Code extension: `Dev Containers` (`ms-vscode-remote.remote-containers`)
- Docker runtime available on the host

Open in container:
1. Open the repository in VS Code.
2. Run `Dev Containers: Reopen in Container`.
3. Wait for the host-side `linux/amd64` image build and `postCreateCommand` to finish.

After attach:
- terminal commands run inside Linux
- Python tooling runs inside Linux
- source files stay in the host checkout
- fixture builds and tests use Linux-compatible dependencies

Useful commands:
- `Dev Containers: Rebuild and Reopen in Container` after changing Dockerfile
  or dependency inputs
- the devcontainer prebuilds `tiny-dec-devcontainer:latest` on the host before
  attach so Apple Silicon hosts do not hit the temporary `buildx --load` image
  mismatch
- `poetry run pytest -q tests/posts/post_18_c_printer_pipeline/test_c_printer_pipeline_e2e_harness.py`
- `poetry run ruff check tiny_dec tests/posts/post_18_c_printer_pipeline`
- `poetry run mypy tiny_dec`

### Inside the Linux shell

Install dependencies:
```bash
cd /workspace
poetry install
```

Run the current stage harness:
```bash
cd /workspace
poetry run pytest -q tests/posts/post_18_c_printer_pipeline/test_c_printer_pipeline_e2e_harness.py
```

Run all staged tests:
```bash
cd /workspace
poetry run pytest -q tests/posts
```

Build fixture binaries when ELFs are missing or intentionally regenerated:
```bash
cd /workspace
./scripts/build_fixtures.sh
```

Notes:
- The cross-compiler is required for fixture generation, not for most Python
  edits.
- If fixture ELFs already exist under `tests/fixtures/bin/`, most development
  work does not require rebuilding them.

## Blog-Aligned Module Plan
This section maps the 19 posts to their module ownership. All 19 posts are
implemented.

1. Post 00: loader harness, ELF access, symbol lookup, and loader CLI utilities.
Module: `loader/`

2. Post 01: RV32I instruction decoding.
Module: `decode/`

3. Post 02: semantic instruction lifting to p-code.
Module: `ir/` (`pcode.py`, `lift_rv32i.py`)

4. Post 03: recursive disassembly, p-code basic blocks, and CFG construction.
Module: `disasm/`

5. Post 04: durable program/function IR containers.
Module: `ir/` (`program_ir.py`, `function_ir.py`)

6. Post 05: simplification and canonicalization.
Module: `analysis/simplify/`

7. Post 06: core dataflow and target recovery.
Module: `analysis/dataflow/`

8. Post 07: SSA construction.
Module: `analysis/ssa/`

9. Post 08: call modeling.
Module: `analysis/calls/`

10. Post 09: stack and frame recovery.
Module: `analysis/stack/`

11. Post 10: memory modeling.
Module: `analysis/memory/`

12. Post 11: scalar type recovery.
Module: `analysis/types/`

13. Post 12: aggregate type recovery.
Module: `analysis/types/`

14. Post 13: variable recovery.
Module: `analysis/highvars/`

15. Post 14: range and predicate refinement.
Module: `analysis/range/`

16. Post 15: interprocedural summaries and prototype inference.
Module: `analysis/interproc/`

17. Post 16: control-structure recovery.
Module: `structuring/`

18. Post 17: IR-to-C lowering.
Module: `c_emit/`

19. Post 18: C printing and full pipeline driver.
Module: `c_emit/`, `pipeline/`

## Package Layout
```text
tiny_dec/
    loader/
    decode/
    ir/
    disasm/
    analysis/
      simplify/
      dataflow/
      ssa/
      calls/
      stack/
      memory/
      types/
      highvars/
      range/
      interproc/
    structuring/
    c_emit/
    pipeline/
    cli.py
```

Package ownership rules:
- `disasm/` is the stage-3 owner and contains CFG construction as part of
  disassembly.
- Each stage directory exposes only its own typed public API.

## Cross-Module Contracts
- Function identity is a virtual address.
- Program identity is the loaded ELF plus loader-resolved metadata.
- Post 02 uses semantic p-code, not raw machine-shaped control flow.
- Stage 3 consumes p-code semantics directly; it should not recover call or
  return meaning by inspecting decoded mnemonics.
- Every stage output must be deterministic and diff-friendly.
- Every stage must provide a stable text dump before any optional structured
  export format.
- `ProgramIR` owns global worklists and invalidation state once post 04 exists.
- Later analyses may enqueue new functions or request CFG rebuilds, but those
  requests must flow through explicit scheduler state rather than hidden
  recursion.

## CLI Design
- Stable entrypoint: `tiny-dec decompile <binary> [--func ...] [--stage ...]`
- Binary metadata lives under `tiny-dec info <binary>`
- Stage debugging lives under `tiny-dec decompile <binary> --stage <stage>`
- Final rendered-C output lives under `tiny-dec decompile <binary>` or
  `tiny-dec decompile <binary> --stage c`
- Public stage-stop contract should expose only implemented stages:
  `loader|decode|pcode|disasm|ir|simplify|dataflow|ssa|calls|stack|memory|scalar_types|aggregate_types|variables|range|interproc|structuring|c_lowering|c`
- Later stage stops should be added only when the corresponding stage produces a
  real typed artifact and a deterministic debug dump

## Testing Plan

### Test Layout
```text
tests/
  fixtures/
    src/          # controlled C inputs
    bin/          # compiled ELF fixtures
  posts/
    post_00_loader/
    post_01_decode/
    post_02_lift_pcode/
    post_03_disasm/
    post_04_ir_containers/
    post_05_simplify/
    post_06_dataflow/
    post_07_ssa/
    post_08_calls/
    post_09_stack/
    post_10_memory/
    post_11_scalar_types/
    post_12_aggregate_types/
    post_13_variables/
    post_14_range/
    post_15_interproc/
    post_16_structuring/
    post_17_c_lowering/
    post_18_c_printer_pipeline/
```

Run one stage:
```bash
cd /workspace
poetry run pytest -q tests/posts/post_18_c_printer_pipeline
```

Run all staged tests:
```bash
cd /workspace
poetry run pytest -q tests/posts
```

### Fixture Build (Linux)
```bash
cd /workspace
./scripts/build_fixtures.sh
```

Optional explicit toolchain:
```bash
cd /workspace
CC=clang TARGET_TRIPLE=riscv32-unknown-elf TARGET_CFLAGS="-march=rv32i -mabi=ilp32" ./scripts/build_fixtures.sh
```

Toolchain installation notes live in `tests/fixtures/README.md`.

### Coverage Expectations by Post
- Post 00: loader models, `ProgramView`, symbol and main resolution, loader CLI.
- Post 01: instruction model and decoder contract tests.
- Post 02: p-code datamodel, semantic lift rules, and p-code pretty-printers.
- Post 03: recursive disassembly, basic blocks, CFG edges, direct call
  discovery, and deterministic stage-3 formatting.
- Post 04: durable `FunctionIR` and `ProgramIR` containers, deterministic
  container pretty-printers, direct-call classification, and the `ir` CLI.
- Post 05+: add tests only when a stage has a real contract and real data
  structures; do not keep placeholder `NotImplementedError` tests as standing
  stage coverage.

## Exercise-First Workflow
- Work on one post at a time.
- For each post, follow the repo order: design doc, data structures,
  pretty-printers, transform scaffold, tests, implementation, consistency pass.
- Keep code and docs synchronized in the same working session.
- Prefer small, reviewable diffs that fully advance the current stage.
- Use the current stage harness and deterministic pretty-prints as the main
  debugging surface.

## Delivery Gates
- A stage is not complete until it has a written contract, typed data
  structures, deterministic pretty-print output, and post-scoped tests.
- After every meaningful step, run the current e2e harness, `ruff`, and `mypy`
  on the narrowest relevant targets.
- Do not expose stage APIs before the stage has a real contract.
- Do not soften or delete tests just to get green results.
- Keep the repository truthful: every exposed stage must be backed by real
  typed data structures and deterministic pretty-print output.

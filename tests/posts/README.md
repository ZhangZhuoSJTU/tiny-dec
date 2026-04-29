# Post-Based Test Suites

Each implemented post has a dedicated test folder so development can stay scoped to
one stage at a time.

Run one post:

```bash
cd /workspace
poetry run pytest -q tests/posts/post_18_c_printer_pipeline
```

Run all post suites:

```bash
cd /workspace
poetry run pytest -q tests/posts
```

Current folder mapping:

- `post_00_loader`
- `post_01_decode`
- `post_02_lift_pcode`
- `post_03_disasm`
- `post_04_ir_containers`
- `post_05_simplify`
- `post_06_dataflow`
- `post_07_ssa`
- `post_08_calls`
- `post_09_stack`
- `post_10_memory`
- `post_11_scalar_types`
- `post_12_aggregate_types`
- `post_13_variables`
- `post_14_range`
- `post_15_interproc`
- `post_16_structuring`
- `post_17_c_lowering`
- `post_18_c_printer_pipeline`

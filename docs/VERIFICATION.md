# Verification contract

Run `python3 verify.py` from the repository root. Its exit code and newly written
`out/verification/results.json` are the result of that run. A RUNNING or FAIL manifest
is not a pass. `source_sha256` identifies the exact code, testbench and workflow bytes
checked, even when the run occurred before a commit. `base_commit` is the Git HEAD at
run time; the hashes identify any subsequent uncommitted changes used by that run.

## What the levels mean

1. **Python:** reference-model, boundary, failure and replay-export tests.
2. **RTL simulation:** compiled Icarus Verilog with deterministic reference comparisons,
   invalid input and backpressure. Integrated tests exercise actual module connections.
3. **Generic synthesis:** Yosys `synth` followed by `check -assert`, for each documented top.
   No vendor placement, routing, device resource estimate or timing closure is implied.
4. **Board:** not performed. This requires the actual board, exact device and constraints,
   power/voltage checks, vendor build tools and recorded physical measurements.

The verifier captures each command's stdout/stderr and returns failure on nonzero exit
or timeout. GitHub Actions invokes the same entry point. Account billing blocked hosted
jobs at the audit date, so the retained local evidence is the relevant passing record.
Do not interpret a configured workflow or a green model demo as a hardware pass.

`evidence/local-verification/` is a retained run. It is not rewritten automatically by
future verification. Older `evidence/standalone-verification.json` and other original logs
remain historical records. A later edit requires a new verification run.

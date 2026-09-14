# Provenance

This repository separates FeedGuard FPGA from the earlier combined learning lab at
`JavaJaiden/narby`, commit `f82a0f0127c6d2c4a394f4f00706604d8d47ef1d`.
Its application and RTL source files are unchanged by the split. The Python tests,
HDL harness, workflow and documentation have been separated for standalone use.
The original MIT notice is retained. The implementation was developed with AI assistance.

The source archive was checked against all 24 source/workflow Git blob hashes before
splitting. Split-baseline verification was recorded in `evidence/standalone-verification.json`;
previous combined-lab counts are not presented as new standalone results.

References:

- HKEX OMD-C resources: https://www.hkex.com.hk/Services/Market-Data-Services/Real-Time-Data-Services/HKEX-Orion-Market-Data-Platform/Infrastructure?sc_lang=en
- SnowElowen, FPGA_HKEX-OMD-C_40ns-Lab: https://github.com/SnowElowen/FPGA_HKEX-OMD-C_40ns-Lab

FeedGuard is an independent educational implementation. It does not contain
SnowElowen's production RTL, captures, images, or performance results. It is not
a port of that private implementation and does not claim its latency.

## Local hardening and showcase release

Subsequent commits add integrated tests, reproducible generic synthesis and shareable
demos. Current audit evidence is in `evidence/local-verification/results.json`.
The original split logs remain historical; physical board operation is still unverified.

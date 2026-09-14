# FeedGuard FPGA

A streaming UDP-payload envelope validator and message-sequence guard, with
independent Python references and SystemVerilog implementations.

This standalone repository has no dependency on Rally or the previous combined
repository. It starts at the UDP application payload, not the Ethernet PHY.

## Run

Python 3.10 or newer is required. The reference has no third-party packages.

```sh
python3 -m unittest -v
python3 feedguard.py --output out/feedguard.json
```

The demo includes first packets, heartbeats, duplicates, a gap, repair by
re-offering missing data, a partially overlapping range, and malformed input.

## Data path

```text
Payload bytes -> complete-envelope validation -> sequence-state guard
                    invalid -> no sequence advance
                    gap     -> keep expected sequence
```

The envelope validator checks packet size, message count, nested lengths and
truncation. Message bodies are opaque. It publishes metadata only after the
complete payload has arrived. The sequence guard classifies in-order ranges,
duplicates, overlaps, gaps, heartbeats and session-reset requirements. Output
metadata remains stable while the consumer is stalled.

The integrated `feedguard_top` connects the envelope and sequence modules.
Accepted metadata is not a forwarded payload; buffering or replay of message
bodies belongs to a later integration stage. The maximum payload capacity is
1500 bytes in this laboratory contract, not an asserted exchange requirement.

## Verification

```sh
# Requires Icarus Verilog and vvp; missing tools cause failure.
python3 sim/check_rtl.py
```

The harness generates deterministic envelope and sequence vectors, compares
real RTL with the references, and checks output stalls and session resets.
The workflow also performs generic Yosys structural checks for `omdc_envelope`,
`sequence_guard`, and `feedguard_top`. The current local results are under
`evidence/`; no synthesis, routed timing or hardware pass is implied by the
presence of the workflow.

## Scope

This is an educational OMD-C-style envelope lab, not a current-version exchange
certification. There is no Ethernet MAC/PCS, live feed, retransmission client,
order book, optical interface or trade submission. The byte-wide input is not
a demonstrated 10 Gb/s implementation. No nanosecond latency is claimed.

Inspired by SnowElowen's research, but independently implemented without the
upstream production source or measurement files. See [PROVENANCE.md](PROVENANCE.md)
and [LICENSE](LICENSE).

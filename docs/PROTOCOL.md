# FeedGuard interface contract

## Packet layout

Synthetic OMD-C-style UDP application payloads use little-endian fields. This is a lab
contract, not a current exchange specification or conformance claim.

| Offset | Bytes | Header field |
| --- | --- | --- |
| 0 | 2 | Total packet length, including header |
| 2 | 1 | Message count (0–255) |
| 3 | 1 | Reserved filler, ignored |
| 4 | 4 | First message sequence |
| 8 | 8 | Timestamp, retained as opaque metadata |

Each message has a two-byte length including its four-byte message header, two-byte
type, and opaque body. All nested message boundaries must exactly fill the packet and
match the advertised count. Heartbeats have zero messages and a 16-byte packet length.
Capacity is 1,500 bytes. Empty packets cannot be represented on the byte-stream RTL
interface; the Python parser rejects an empty byte string.

## Ready/valid signals

`in_data` and `in_last` are sampled only on a rising clock with both `in_valid` and
`in_ready` asserted. The producer must hold them stable while valid is high and ready
is low. `in_last` terminates the current packet; input gaps do not. If packet termination
is lost, the upstream adapter must assert reset to abandon the partial packet.

An output is consumed only when `out_valid && out_ready`. It remains valid and stable
under backpressure. Both stages contain one pending result slot; the connected pipeline
can hold results and stall input when capacity is exhausted. This is not payload storage.

Synchronous active-high `rst` clears partial input, pending outputs and sequence state.
Reset abandons that work. Use it between logical sessions, after draining if those
outputs must be retained. Redundant feeds for one channel must arbitrate into the same
guard. Independent channels need independent guard instances.

## Results

The envelope stage emits sequence, count, timestamp, first message type and a four-bit
error bitmap: SHORT=1, SIZE=2, MESSAGE=4, OVERSIZE=8. Error bits can combine. Only zero
error permits commit; metadata for rejected packets is not meaningful. Exact combined
error-bit patterns are not required to match between reference and RTL after parsing
has already failed; acceptance/rejection is the shared contract.

`feedguard_top` emits `out_kind`, `out_skip`, `out_take`, and 33-bit `out_expected`.
Kind values 0–7 are bootstrap, in_order, overlap, duplicate, gap, heartbeat, malformed,
and reset_required. `skip` counts an already-seen prefix; `take` counts newly accepted
messages. These counts refer to bodies the upstream system must retain or replay.

`expected` is the next sequence after the accepted range. It may equal 2^32 after the
last legal message. Another data packet then requires explicit reset; it never wraps
silently. An uninitialized RTL guard reports expected=0; the reference uses `None`.
Heartbeats do not initialize state, even at the sequence limit. Bootstrap is not a snapshot
or proof that earlier data has been recovered. Gaps and malformed packets do not advance.

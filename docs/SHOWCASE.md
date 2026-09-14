# Two-minute FeedGuard demonstration

1. Open `docs/demo.html`. Begin with packet 1: sequence 100 with three messages establishes
   expected=103. Packet 2 is a heartbeat; packet 3 is a duplicate. Neither advances state.
2. Select packet 4: sequence 106 exposes a gap. Expected stays at 103. Packet 5 re-offers
   the missing range; packet 6 can then be accepted. This demonstrates caller-driven repair,
   not a built-in retransmission client.
3. Packet 7 overlaps an earlier range. Skip the duplicate prefix and accept only the new
   suffix. Packet 8 is malformed and cannot change sequence state.
4. Show the byte-stream → envelope → guard diagram and the retained local verification.
   The HTML shows the Python reference; the 438-packet integrated HDL test separately
   checks real connected RTL with producer and consumer stalls and reset flushing.

## Talking points

- Packet-level validation prevents a bad trailing message from committing earlier metadata.
- Sequence state belongs to a logical channel, not independently to each redundant wire.
- Backpressure must preserve results; resets must discard partial packets and pending results.
- Metadata alone is not the message payload. A feed handler needs buffering, body decoding,
  live-feed integration and a recovery design; this project deliberately demonstrates the guard.

## Rebuild the retained demo

```sh
python3 verify.py
python3 replay.py --trace out/feedguard.json --output out/feedguard-replay.html
```

The page digest identifies the retained `docs/demo-trace.json`. No exchange access is needed.

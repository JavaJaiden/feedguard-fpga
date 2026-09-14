"""FeedGuard: OMD-C envelope validation and single-channel sequence arbitration.

Input is a UDP payload, NOT Ethernet, XGMII, or a raw transceiver stream.
Message bodies remain opaque. This is not an order book or a trading system.
"""
from __future__ import annotations
import argparse
import json
import struct
from dataclasses import dataclass
from pathlib import Path

HEADER = struct.Struct('<HBBIQ')
MESSAGE = struct.Struct('<HH')
MAX_BYTES = 1500
SHORT, SIZE, MESSAGE_ERROR, OVERSIZE = 1, 2, 4, 8
NAMES = ('bootstrap', 'in_order', 'overlap', 'duplicate', 'gap', 'heartbeat', 'malformed', 'reset_required')


@dataclass(frozen=True)
class Envelope:
    seq: int
    count: int
    timestamp: int
    first_type: int
    error: int


def encode(seq: int, messages: list[tuple[int, bytes]], timestamp: int = 0) -> bytes:
    """Generate synthetic OMD-C envelopes; opaque bodies are not spec-validated."""
    if not 0 <= seq <= 0xFFFFFFFF or not 0 <= timestamp < 1 << 64:
        raise ValueError('sequence or timestamp is out of range')
    if len(messages) > 255:
        raise ValueError('message count exceeds 255')
    bodies = []
    for kind, payload in messages:
        if not 0 <= kind <= 65535 or len(payload) > 65531:
            raise ValueError('message type or length is out of range')
        bodies.append(MESSAGE.pack(4 + len(payload), kind) + payload)
    body = b''.join(bodies)
    if len(body) + HEADER.size > MAX_BYTES:
        raise ValueError('packet exceeds configured lab capacity')
    return HEADER.pack(16 + len(body), len(messages), 0, seq, timestamp) + body


def inspect(data: bytes) -> Envelope:
    """Validate the entire packet before returning commit-eligible metadata."""
    if len(data) < HEADER.size:
        # Other malformed metadata is unspecified; SHORT is authoritative here.
        return Envelope(0, 0, 0, 0, SHORT | (SIZE if len(data) >= 2 and int.from_bytes(data[:2], 'little') != len(data) else 0))
    size, count, _filler, seq, sent = HEADER.unpack_from(data)
    error = (SIZE if size != len(data) else 0) | (OVERSIZE if len(data) > MAX_BYTES else 0)
    offset, seen, first = 16, 0, 0
    while offset < len(data):
        if len(data) - offset < 4:
            error |= MESSAGE_ERROR
            break
        length, kind = MESSAGE.unpack_from(data, offset)
        if not seen:
            first = kind
        if length < 4 or offset + length > len(data):
            error |= MESSAGE_ERROR
            break
        offset += length
        seen += 1
    if seen != count or offset != len(data):
        error |= MESSAGE_ERROR
    return Envelope(seq, count, sent, first, error)


def messages(data: bytes) -> list[tuple[int, bytes]]:
    env = inspect(data)
    if env.error:
        raise ValueError(f'malformed envelope: error bitmap 0x{env.error:x}')
    result, offset = [], 16
    for _ in range(env.count):
        length, kind = MESSAGE.unpack_from(data, offset)
        result.append((kind, data[offset + 4:offset + length]))
        offset += length
    return result


class SequenceGuard:
    """One instance per logical channel, shared by redundant A/B packet inputs.

A gap never advances expected. The caller must buffer/replay future packets.
Explicit session_reset is required across sessions. Bootstrap is NOT a snapshot.
"""
    def __init__(self) -> None:
        self.expected: int | None = None

    def reset(self) -> None:
        self.expected = None

    def accept(self, env: Envelope) -> dict:
        skip = take = 0
        if env.error:
            kind = 6
        elif env.count == 0:
            kind = 5
        else:
            end = env.seq + env.count
            if end > 1 << 32 or self.expected == 1 << 32:
                kind = 7
            elif self.expected is None:
                kind, take, self.expected = 0, env.count, end
            elif env.seq > self.expected:
                kind = 4
            elif end <= self.expected:
                kind = 3
            elif env.seq < self.expected:
                kind, skip, take = 2, self.expected - env.seq, end - self.expected
                self.expected = end
            else:
                kind, take, self.expected = 1, env.count, end
        return dict(kind=kind, classification=NAMES[kind], skip=skip, take=take,
                    expected=self.expected, packet_seq=env.seq, packet_count=env.count,
                    error=env.error)


def demo() -> list[dict]:
    guard = SequenceGuard()
    fixture = [(100, 3), (102, 0), (100, 3), (106, 2), (103, 3), (106, 2), (107, 3)]
    rows = []
    for seq, count in fixture:
        # Type 0xF001 is a lab-only synthetic body, not an exchange message claim.
        wire = encode(seq, [(0xF001, b'LAB') for _ in range(count)])
        rows.append(guard.accept(inspect(wire)))
    damaged = bytearray(encode(110, [(0xF001, b'LAB')]))
    damaged[16:18] = b'\xff\xff'
    rows.append(guard.accept(inspect(bytes(damaged))))
    return rows


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('out/feedguard.json'))
    args = parser.parse_args()
    rows = demo()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(rows, indent=2) + '\n', encoding='utf-8')
    for row in rows:
        print(f"seq={row['packet_seq']:3} count={row['packet_count']} "
              f"{row['classification']:14} skip={row['skip']} take={row['take']} expected={row['expected']}")

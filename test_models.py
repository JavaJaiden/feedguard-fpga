"""Deterministic tests for FeedGuard FPGA."""
import random
import struct
import unittest
import feedguard as f

class FeedTests(unittest.TestCase):
    def test_header_endianness(self):
        p=f.encode(0x44332211,[],0x0807060504030201)
        self.assertEqual(p.hex(),'10000000112233440102030405060708')
        self.assertEqual(f.inspect(p),f.Envelope(0x44332211,0,0x0807060504030201,0,0))

    def test_messages_random(self):
        rng=random.Random(112)
        for _ in range(1000):
            msgs=[(rng.randrange(65536),rng.randbytes(rng.randrange(40))) for _ in range(rng.randrange(20))]
            wire=f.encode(rng.randrange(1<<32),msgs,rng.randrange(1<<64))
            env=f.inspect(wire)
            self.assertEqual(env.error,0); self.assertEqual(env.count,len(msgs))
            self.assertEqual(f.messages(wire),msgs)

    def test_each_truncation_rejected(self):
        p=f.encode(1,[(0xF001,b'0123456789'),(0xF002,b'abcdef')])
        for n in range(len(p)):
            self.assertNotEqual(f.inspect(p[:n]).error,0)

    def test_bad_message_length_and_count(self):
        base=f.encode(1,[(0xF001,b'abcdef')])
        for size in [0,1,2,3,9,11,65535]:
            p=bytearray(base); struct.pack_into('<H',p,16,size)
            self.assertNotEqual(f.inspect(p).error,0)
        p=bytearray(base); p[2]=2
        self.assertTrue(f.inspect(p).error & f.MESSAGE_ERROR)
        p=bytearray(base); p[0]^=1
        self.assertTrue(f.inspect(p).error & f.SIZE)

    def test_capacity_and_unknown_types(self):
        p=f.encode(7,[(0xFEED,b'x'*1480)])
        self.assertEqual(len(p),1500); self.assertEqual(f.inspect(p).error,0)
        p=bytearray(p+b'x'); struct.pack_into('<H',p,0,len(p)); struct.pack_into('<H',p,16,1485)
        self.assertTrue(f.inspect(p).error & f.OVERSIZE)
        with self.assertRaises(ValueError): f.encode(7,[(0xFEED,b'x'*1481)])
        with self.assertRaises(ValueError): f.encode(7,[(0,b'')]*256)

    def test_gap_duplicate_overlap_and_repair(self):
        rows=f.demo()
        self.assertEqual([x['classification'] for x in rows],['bootstrap','heartbeat','duplicate','gap','in_order','in_order','overlap','malformed'])
        self.assertEqual([x['expected'] for x in rows],[103,103,103,103,106,108,110,110])
        self.assertEqual((rows[6]['skip'],rows[6]['take']),(1,2))

    def test_heartbeat_never_seeds_or_advances(self):
        g=f.SequenceGuard(); e=f.inspect(f.encode(500,[]))
        self.assertIsNone(g.accept(e)['expected'])
        g.accept(f.inspect(f.encode(7,[(1,b'')])) )
        self.assertEqual(g.accept(e)['expected'],8)

    def test_session_reset_and_overflow(self):
        g=f.SequenceGuard()
        self.assertEqual(g.accept(f.Envelope(0xFFFFFFFF,2,0,0,0))['classification'],'reset_required')
        self.assertIsNone(g.expected)
        self.assertEqual(g.accept(f.Envelope(0xFFFFFFFF,1,0,0,0))['expected'],1<<32)
        self.assertEqual(g.accept(f.Envelope(0,1,0,0,0))['classification'],'reset_required')
        g.reset()
        self.assertEqual(g.accept(f.Envelope(1,1,0,0,0))['classification'],'bootstrap')

    def test_malformed_packet_never_commits(self):
        g=f.SequenceGuard(); g.accept(f.Envelope(10,3,0,0,0))
        for error in range(1,16):
            self.assertEqual(g.accept(f.Envelope(13,5,0,0,error))['expected'],13)

if __name__ == "__main__":
    unittest.main(verbosity=2)

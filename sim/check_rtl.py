"""Compile this project's RTL and compare it with its Python reference.

Missing tools are an error, not a passing or skipped HDL result.
"""
from __future__ import annotations
import json
from pathlib import Path
import random
import shutil
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import feedguard as f
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'out' / 'rtl'

def simulate(name: str, text: str, sources: list[str]) -> str:
    tb=OUT/f'{name}.sv'; tb.write_text(text,encoding='utf-8')
    subprocess.run(['iverilog','-g2012','-s',name,'-o',str(OUT/name),str(tb),
                    *[str(ROOT/s) for s in sources]],check=True,timeout=60)
    run=subprocess.run(['vvp',str(OUT/name)],cwd=OUT,text=True,capture_output=True,timeout=90)
    (OUT/f'{name}.log').write_text(run.stdout+run.stderr,encoding='utf-8')
    if run.returncode or 'PASS' not in run.stdout:
        raise RuntimeError(f'{name}: {run.stdout}\n{run.stderr}')
    print(run.stdout.strip())
    return run.stdout

def envelope_check() -> int:
    rng=random.Random(73)
    packets=[f.encode(0,[]), f.encode(0xffffffff,[(0xF001,b'')],0xffffffffffffffff),
             f.encode(7,[(0xFEED,b'x'*1480)])]
    for _ in range(180):
        msgs=[(rng.randrange(65536),rng.randbytes(rng.randrange(20))) for _ in range(rng.randrange(10))]
        packets.append(f.encode(rng.randrange(1<<32),msgs,rng.randrange(1<<64)))
    base=f.encode(100,[(0xF001,b'0123456789'),(0xF002,b'abcdef')])
    packets += [base[:n] for n in range(1,len(base))]
    for size in [0,1,2,3,9,11,65535]:
        damaged=bytearray(base); damaged[16:18]=size.to_bytes(2,'little'); packets.append(bytes(damaged))
    for _ in range(180):
        damaged=bytearray(rng.choice(packets[:183])); index=rng.randrange(len(damaged))
        damaged[index]^=1<<rng.randrange(8); packets.append(bytes(damaged))
    oversized=bytearray(f.encode(7,[(0xFEED,b'x'*1480)])+b'x')
    oversized[0:2]=(1501).to_bytes(2,'little'); oversized[16:18]=(1485).to_bytes(2,'little')
    packets.append(bytes(oversized))
    rows=[]
    for p in packets:
        e=f.inspect(p)
        rows.append(f'{len(p)} {p.hex()} {int(bool(e.error))} {e.seq:x} {e.count:x} {e.timestamp:x} {e.first_type:x}')
    (OUT/'envelopes.txt').write_text('\n'.join(rows)+'\n',encoding='utf-8')
    simulate('envelope_tb',r'''
`timescale 1ns/1ps
module envelope_tb;
reg clk=0,rst=1,in_valid=0,in_last=0,out_ready=0;
reg [7:0] in_data=0;
wire in_ready,out_valid;
wire [31:0] out_seq;
wire [7:0] out_count;
wire [63:0] out_timestamp;
wire [15:0] out_first_type;
wire [3:0] out_error;
omdc_envelope dut(.*);
always #5 clk=~clk;
reg [16383:0] packet;
reg [31:0] seq;
reg [7:0] count;
reg [63:0] stamp;
reg [15:0] kind;
reg [123:0] held;
integer fd,rc,n,bad,i,test_count=0;
initial begin
 repeat(4) @(negedge clk); rst=0;
 fd=$fopen("envelopes.txt","r"); if(!fd) $fatal(1,"missing vectors");
 while(!$feof(fd)) begin
  rc=$fscanf(fd,"%d %h %d %h %h %h %h",n,packet,bad,seq,count,stamp,kind);
  if(rc==7) begin
   for(i=n-1;i>=0;i=i-1) begin
    @(negedge clk); in_valid=1; in_data=packet[i*8 +:8]; in_last=(i==0);
    while(!in_ready) @(negedge clk);
    @(negedge clk); in_valid=0; in_last=0;
    if(i%5==0) @(negedge clk);
   end
   if(!out_valid) $fatal(1,"no result %0d",test_count);
   if((out_error!=0)!=(bad!=0)) $fatal(1,"error mismatch %0d got %h",test_count,out_error);
   if(!bad && {out_seq,out_count,out_timestamp,out_first_type} !== {seq,count,stamp,kind})
    $fatal(1,"metadata mismatch %0d",test_count);
   held={out_seq,out_count,out_timestamp,out_first_type,out_error};
   repeat(3) begin
    @(negedge clk);
    if(!out_valid || in_ready || held !== {out_seq,out_count,out_timestamp,out_first_type,out_error})
      $fatal(1,"backpressure violation");
   end
   out_ready=1; @(negedge clk); out_ready=0;
   test_count=test_count+1;
  end
 end
 $display("PASS envelope: %0d vectors, input gaps and output stalls",test_count); $finish;
end
initial begin #100000000; $fatal(1,"timeout"); end
endmodule
''',['rtl/feedguard.sv'])
    return len(packets)

def sequence_check() -> int:
    rng=random.Random(104); guard=f.SequenceGuard(); rows=[]
    cases=[(1,500,0,0),(0,100,3,0),(0,100,3,0),(0,106,2,0),(0,103,3,0),
           (0,106,2,0),(0,107,3,0),(0,110,8,1),(1,0xffffffff,2,0),
           (0,0xffffffff,1,0),(0,0,1,0),(0,0,0,0),(1,1,1,0)]
    for _ in range(1000):
        cases.append((int(rng.random()<.025),rng.randrange(1,180),rng.randrange(8),int(rng.random()<.1)))
    for reset,seq,count,bad in cases:
        if reset: guard.reset()
        result=guard.accept(f.Envelope(seq,count,0,0,bad))
        rows.append(f'{reset} {seq:x} {count:x} {bad} {result["kind"]} {result["skip"]:x} {result["take"]:x} {(result["expected"] or 0):x}')
    (OUT/'sequences.txt').write_text('\n'.join(rows)+'\n',encoding='utf-8')
    simulate('sequence_tb',r'''
`timescale 1ns/1ps
module sequence_tb;
reg clk=0,rst=1,in_valid=0,out_ready=0,in_bad=0;
reg [31:0] in_seq=0;
reg [7:0] in_count=0;
wire in_ready,out_valid;
wire [2:0] out_kind;
wire [7:0] out_skip,out_take;
wire [32:0] out_expected;
sequence_guard dut(.*);
always #5 clk=~clk;
integer fd,rc,reset_flag,bad,kind,test_count=0;
reg [31:0] seq;
reg [7:0] count,skip,take;
reg [32:0] expected;
reg [51:0] held;
initial begin
 repeat(4) @(negedge clk); rst=0;
 fd=$fopen("sequences.txt","r"); if(!fd) $fatal(1,"missing vectors");
 while(!$feof(fd)) begin
  rc=$fscanf(fd,"%d %h %h %d %d %h %h %h",reset_flag,seq,count,bad,kind,skip,take,expected);
  if(rc==8) begin
   if(reset_flag) begin @(negedge clk); rst=1; @(negedge clk); rst=0; end
   @(negedge clk); in_valid=1; in_seq=seq; in_count=count; in_bad=(bad!=0);
   while(!in_ready) @(negedge clk);
   @(negedge clk); in_valid=0;
   if(!out_valid || out_kind !== kind[2:0] || {out_skip,out_take,out_expected} !== {skip,take,expected})
    $fatal(1,"sequence mismatch %0d kind %0d expected %0d",test_count,out_kind,out_expected);
   held={out_kind,out_skip,out_take,out_expected};
   repeat(3) begin
    @(negedge clk);
    if(!out_valid || in_ready || held !== {out_kind,out_skip,out_take,out_expected}) $fatal(1,"unstable output");
   end
   out_ready=1; @(negedge clk); out_ready=0;
   test_count=test_count+1;
  end
 end
 $display("PASS sequence: %0d vectors, session resets and output stalls",test_count); $finish;
end
initial begin #10000000; $fatal(1,"timeout"); end
endmodule
''',['rtl/feedguard.sv'])
    return len(cases)

def main() -> None:
    for tool in ('iverilog', 'vvp'):
        if not shutil.which(tool):
            raise SystemExit(f'{tool} is required; RTL verification NOT RUN')
    OUT.mkdir(parents=True, exist_ok=True)
    counts = {'envelope_vectors': envelope_check(), 'sequence_vectors': sequence_check()}
    result = {'status': 'PASS', 'engine': 'Icarus Verilog',
              'counts': counts, 'hardware_tested': False}
    (OUT / 'results.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result))

if __name__ == '__main__':
    main()

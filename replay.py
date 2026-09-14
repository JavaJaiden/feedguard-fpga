"""Build a self-contained packet walkthrough from the Python demo's recorded JSON."""
from __future__ import annotations
import argparse
import hashlib
import html
import json
from pathlib import Path


def export(trace: Path, output: Path) -> None:
    raw=trace.read_bytes()
    rows=json.loads(raw)
    if not isinstance(rows,list) or not rows:
        raise ValueError('expected a nonempty packet trace')
    names={'bootstrap','in_order','overlap','duplicate','gap','heartbeat','malformed','reset_required'}
    for row in rows:
        if row.get('classification') not in names:
            raise ValueError('unknown classification')
        for key in ('packet_seq','packet_count','skip','take','error'):
            if type(row.get(key)) is not int or row[key]<0:
                raise ValueError('invalid packet counters')
        if row.get('expected') is not None and (type(row['expected']) is not int or row['expected']<0):
            raise ValueError('invalid expected sequence')
    data=json.dumps(rows,separators=(',',':')).replace('<','\\u003c')
    page=TEMPLATE.replace('__DATA__',data).replace('__SHA__',hashlib.sha256(raw).hexdigest())
    page=page.replace('__NAME__',html.escape(trace.name))
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(page,encoding='utf-8')
    print(f'Wrote {len(rows)} packets to {output}')


TEMPLATE=r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>FeedGuard — Packet inspection lab</title>
<style>
:root{color-scheme:dark;--bg:#0c1420;--panel:#141f2d;--line:#2b3b4e;--muted:#a8b9cc;--accent:#7cddce}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:#edf3fa;font:16px/1.55 system-ui,sans-serif}
main{max-width:1120px;margin:auto;padding:38px 28px 60px}nav{display:flex;justify-content:space-between;gap:20px;border-bottom:1px solid var(--line);padding-bottom:20px;font-size:12px;letter-spacing:.12em}.brand{font-weight:800;color:var(--accent)}
.tag{color:var(--muted)}h1{font-size:clamp(34px,5vw,62px);letter-spacing:-.045em;line-height:1.06;margin:44px 0 20px;max-width:780px}h1 span{color:var(--accent)}.lede{max-width:700px;color:var(--muted);font-size:18px;margin-bottom:32px}.grid{display:grid;grid-template-columns:1.3fr 1fr;gap:20px}.panel{border:1px solid var(--line);border-radius:14px;padding:24px;background:var(--panel)}h2{font-size:13px;text-transform:uppercase;letter-spacing:.1em;color:var(--muted);margin:0 0 20px}.pipeline{display:flex;gap:10px;align-items:center;margin-bottom:24px}.stage{border:1px solid var(--line);padding:12px;border-radius:8px;flex:1;font-size:13px}.stage strong{display:block;color:var(--accent)}.result{font-size:32px;font-weight:700;letter-spacing:-.02em;color:var(--accent)}#why{min-height:86px;color:var(--muted)}.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.stat{padding:16px 10px;background:#0c1420;border-radius:8px;font-size:12px;color:var(--muted)}.stat b{display:block;font-size:28px;color:#fff}.controls{display:flex;align-items:center;gap:12px;margin-top:20px;flex-wrap:wrap}button{font:inherit;color:#0c1420;background:var(--accent);padding:10px 20px;border:0;border-radius:7px;cursor:pointer}button:disabled{opacity:.4;cursor:default}button.secondary{background:var(--panel);border:1px solid var(--line);color:#fff}input{accent-color:var(--accent);flex:1;min-width:100px}button:focus-visible,input:focus-visible{outline:3px solid #fff;outline-offset:4px}.table-wrap{overflow:auto;margin-top:24px}table{width:100%;border-collapse:collapse;font-size:14px}th{text-align:left;color:var(--muted);font-weight:500}td,th{padding:13px 14px;border-bottom:1px solid var(--line)}tr.current{background:#1a3940;color:#a6f3e6}tbody tr{cursor:pointer}tbody tr:hover{background:#203044}.foot{font-size:13px;color:var(--muted);margin-top:30px;max-width:920px;overflow-wrap:anywhere}.stamp{color:var(--accent);font-size:12px;letter-spacing:.1em}.mono{font-family:ui-monospace,monospace}@media(max-width:720px){main{padding:24px 16px}.grid{grid-template-columns:1fr}.pipeline{flex-wrap:wrap}.tag{max-width:150px;text-align:right}h1{margin-top:30px}.panel{padding:20px}}
</style></head><body><main>
<nav><span class="brand">FEEDGUARD / FPGA LAB</span><span class="tag">RECORDED PYTHON REFERENCE</span></nav>
<h1>Check the whole packet.<br><span>Then advance the sequence.</span></h1>
<p class="lede">A packet inspection and recovery walkthrough. Follow duplicates, missing messages and repaired ranges through a streaming envelope validator and sequence guard.</p>
<div class="pipeline" aria-label="Architecture"><div class="stage"><strong>01 / Payload</strong>UDP application bytes</div><span aria-hidden="true">→</span><div class="stage"><strong>02 / Validate</strong>Size &amp; message boundaries</div><span aria-hidden="true">→</span><div class="stage"><strong>03 / Classify</strong>Commit eligible metadata</div></div>
<div class="grid"><section class="panel"><h2 id="packet">Packet 1</h2><div class="result" id="kind" aria-live="polite"></div><p id="why"></p><div class="controls"><button id="prev" class="secondary">Previous</button><button id="next">Next packet →</button><input id="position" type="range" min="0" value="0" aria-label="Packet position"></div></section>
<section class="panel"><h2>Sequence state after this packet</h2><div class="stats"><div class="stat">Next expected<b id="expected"></b></div><div class="stat">Skip prefix<b id="skip"></b></div><div class="stat">Accept count<b id="take"></b></div></div><p id="range" class="mono"></p><p class="foot">A gap leaves the next expected sequence unchanged. Recovery is demonstrated by explicitly re-offering the missing data.</p></section></div>
<div class="table-wrap"><table><caption style="text-align:left;margin-bottom:10px;color:var(--muted)">Recorded packets · select a row or use the controls above</caption><thead><tr><th>#</th><th>Sequence</th><th>Count</th><th>Classification</th><th>Expected after</th></tr></thead><tbody id="rows"></tbody></table></div>
<p class="foot"><span class="stamp">EVIDENCE BOUNDARY</span><br>This page replays Python reference output. The repository separately tests actual SystemVerilog, including both connected stages under backpressure and reset. Accepted metadata does not contain the message bodies; downstream delivery needs buffering or replay. No live exchange feed, order book, nanosecond latency, routed timing or board operation is shown here.</p>
<p class="foot mono">Trace: __NAME__<br>SHA-256: __SHA__</p>
</main><script>
'use strict';const packets=__DATA__;let index=0;
const explanations={bootstrap:'The first valid data packet establishes the next expected sequence. This is a starting point, not a market snapshot.',in_order:'This packet starts exactly where the previous accepted range ended. Accept all messages and advance.',overlap:'The beginning of this range was already accepted. Skip the duplicate prefix and accept only the new suffix.',duplicate:'All messages in this packet were already accepted. Discard the duplicate without changing sequence state.',gap:'Earlier messages are missing. Do not advance: the sender or caller must replay the missing range first.',heartbeat:'This packet carries no messages. It neither initializes nor advances the sequence state.',malformed:'Envelope validation failed. No message may commit and sequence state stays unchanged.',reset_required:'The 32-bit sequence range is exhausted or this packet crosses it. An explicit session reset is required.'};
const body=document.getElementById('rows');packets.forEach((p,i)=>{const tr=document.createElement('tr');[i+1,p.packet_seq,p.packet_count,p.classification,p.expected===null?'Unset':p.expected].forEach(v=>{const td=document.createElement('td');td.textContent=v;tr.appendChild(td)});tr.onclick=()=>{index=i;draw()};body.appendChild(tr)});
const slider=document.getElementById('position');slider.max=packets.length-1;
function draw(){const p=packets[index];document.getElementById('packet').textContent='Packet '+(index+1)+' of '+packets.length;document.getElementById('kind').textContent=p.classification.replaceAll('_',' ');document.getElementById('why').textContent=explanations[p.classification];for(const key of ['expected','skip','take'])document.getElementById(key).textContent=p[key]===null?'Unset':p[key];document.getElementById('range').textContent='Incoming range ['+p.packet_seq+', '+(p.packet_seq+p.packet_count)+')';Array.from(body.children).forEach((tr,i)=>tr.classList.toggle('current',i===index));document.getElementById('prev').disabled=index===0;document.getElementById('next').disabled=index===packets.length-1;slider.value=index}
document.getElementById('prev').onclick=()=>{if(index>0)index--;draw()};document.getElementById('next').onclick=()=>{if(index<packets.length-1)index++;draw()};slider.oninput=()=>{index=Number(slider.value);draw()};draw();
</script></body></html>'''

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trace',type=Path,default=Path('out/feedguard.json'))
    parser.add_argument('--output',type=Path,default=Path('out/feedguard-replay.html'))
    args=parser.parse_args()
    export(args.trace,args.output)

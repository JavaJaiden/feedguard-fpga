"""Reproducible local checks. No successful manifest survives a failed run."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'out' / 'verification'
TOPS = ['omdc_envelope', 'sequence_guard', 'feedguard_top']
SOURCES = ['rtl/feedguard.sv']


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    report = {'status': 'RUNNING', 'started_utc': datetime.now(timezone.utc).isoformat(),
              'levels': {}, 'commands': [], 'physical_board_tested': False,
              'routed_timing_verified': False}
    def save():
        (OUT / 'results.json').write_text(json.dumps(report, indent=2)+'\n')
    def run(name, command, timeout=180):
        print(f'Running {name}...', flush=True)
        path = OUT / (name+'.log')
        with path.open('w') as log:
            try:
                result = subprocess.run(command, cwd=ROOT, stdout=log,
                                        stderr=subprocess.STDOUT, timeout=timeout)
            except subprocess.TimeoutExpired:
                report['commands'].append({'name': name, 'command': command, 'exit_code': 'timeout'})
                raise RuntimeError(f'{name} timed out; see {path}')
        report['commands'].append({'name': name, 'command': command, 'exit_code': result.returncode})
        if result.returncode:
            raise RuntimeError(f'{name} failed; see {path}\n'+path.read_text()[-3000:])
        return path.read_text()
    save()
    try:
        # Include new files as well as committed ones; ignore generated outputs.
        names = subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard'],
                                        cwd=ROOT,text=True).splitlines()
        report['source_sha256'] = {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
            for name in sorted(set(names)) if Path(name).suffix in {'.py','.sv','.tcl','.xdc'}
            or name.startswith('.github/')}
        report['base_commit'] = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
        report['python'] = sys.version
        run('python-tests', [sys.executable,'-m','unittest','-v'])
        report['levels']['python'] = 'PASS'
        for tool in ('iverilog','vvp'):
            if not shutil.which(tool): raise RuntimeError(f'{tool} is required; RTL NOT RUN')
        report['iverilog'] = run('iverilog-version',['iverilog','-V']).splitlines()[0]
        run('rtl-tests', [sys.executable,'sim/check_rtl.py'])
        report['levels']['rtl_simulation'] = json.loads((ROOT/'out/rtl/results.json').read_text())
        run('demo',[sys.executable,'feedguard.py','--output','out/feedguard.json'])
        run('replay',[sys.executable,'replay.py','--trace','out/feedguard.json','--output','out/feedguard-replay.html'])
        report['levels']['demo']={'status':'PASS','backend':'Python reference','packets':8}
        yosys = os.environ.get('YOSYS') or shutil.which('yosys') or shutil.which('yowasp-yosys')
        if not yosys: raise RuntimeError('Install yosys or yowasp-yosys, or set YOSYS to its executable; synthesis NOT RUN')
        report['yosys'] = run('yosys-version',[yosys,'-V']).strip()
        for top in TOPS:
            run('synthesis-'+top,[yosys,'-Q','-T','-p',
                'read_verilog -sv '+' '.join(SOURCES)+'; synth -top '+top+'; check -assert; stat'])
        report['levels']['generic_synthesis'] = {'status':'PASS','tops':TOPS}
        report['status'] = 'PASS'
    except Exception as exc:
        report['status'] = 'FAIL'
        report['error'] = str(exc)
        raise
    finally:
        report['finished_utc'] = datetime.now(timezone.utc).isoformat()
        save()
    print(json.dumps(report['levels'],indent=2))
    print('Logs and source hashes: '+str(OUT))
    print('No routed timing or physical-board result is implied.')


if __name__ == '__main__':
    main()

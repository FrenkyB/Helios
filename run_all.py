"""HEL-1: one command regenerates the .blend model and preview renders.

Run with Python 3.10+ outside Blender. No third-party Python packages needed.
"""
from pathlib import Path
import argparse
import os
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parent

def find_blender(explicit):
    candidates=[explicit,os.environ.get('BLENDER_EXE'),shutil.which('blender')]
    for base in [Path(os.environ.get('ProgramFiles','C:/Program Files'))/'Blender Foundation',Path('/Applications')]:
        if base.exists():
            candidates.extend(str(p) for p in sorted(base.glob('Blender */blender.exe'),reverse=True) if 'out_of_service' not in str(p))
    candidates.append('/Applications/Blender.app/Contents/MacOS/Blender')
    for p in candidates:
        if p and Path(p).is_file():return str(Path(p).resolve())
    raise SystemExit('Blender not found. Use python run_all.py --blender "C:/path/to/blender.exe"')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--blender',help='Path to Blender 4.2+ executable')
    p.add_argument('--skip-render',action='store_true',help='Generate .blend and validation only')
    p.add_argument('--views',default='hero,side,front,top,rear,engine,nose')
    p.add_argument('--draft',action='store_true',help='Faster 60%% previews')
    p.add_argument('--exterior-only',action='store_true',help='Skip the optional interior study scenes')
    p.add_argument('--correct-cockpit',action='store_true',help='Correct cockpit glazing in the existing model, preserving all other objects')
    p.add_argument('--helios-livery',action='store_true',help='Apply Helios 5B-DBY livery to the saved corrected model')
    p.add_argument('--source',help='Input .blend for --correct-cockpit')
    a=p.parse_args()
    blender=find_blender(a.blender)
    (ROOT/'logs').mkdir(exist_ok=True)
    if a.helios_livery:
        cmd=[blender,'--background','--factory-startup','--python-exit-code','1','--python',str(ROOT/'scripts'/'apply_helios_livery.py'),'--']
        if a.source:cmd.extend(['--source',str(Path(a.source).resolve())])
        if a.skip_render:cmd.append('--skip-render')
        if a.draft:cmd.append('--draft')
        with (ROOT/'logs'/'helios_livery.log').open('w',encoding='utf-8') as log:
            result=subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        if result.returncode:raise SystemExit('Helios livery failed. Read logs/helios_livery.log')
        print('Livery saved and verified:',ROOT/'models'/'Boeing_737-300_Helios_Livery.blend')
        return
    if a.correct_cockpit:
        cmd=[blender,'--background','--factory-startup','--python-exit-code','1','--python',str(ROOT/'scripts'/'correct_cockpit_windows.py'),'--']
        if a.source:cmd.extend(['--source',str(Path(a.source).resolve())])
        if a.skip_render:cmd.append('--skip-render')
        if a.draft:cmd.append('--draft')
        with (ROOT/'logs'/'cockpit_correction.log').open('w',encoding='utf-8') as log:
            result=subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        if result.returncode:raise SystemExit('Cockpit correction failed. Read logs/cockpit_correction.log')
        verify=[blender,'--background','--factory-startup','--python-exit-code','1','--python',str(ROOT/'scripts'/'verify_cockpit_correction.py')]
        with (ROOT/'logs'/'cockpit_preservation.log').open('w',encoding='utf-8') as log:
            result=subprocess.run(verify,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        if result.returncode:raise SystemExit('Cockpit preservation check failed. Read logs/cockpit_preservation.log')
        print('Corrected and verified:',ROOT/'models'/'Boeing_737-300.blend')
        return
    cmd=[blender,'--background','--factory-startup','--python-exit-code','1','--python',str(ROOT/'scripts'/'build_aircraft.py'),'--','--views',a.views]
    if a.skip_render:cmd.append('--skip-render')
    if a.draft:cmd.append('--draft')
    if a.exterior_only:cmd.append('--exterior-only')
    with (ROOT/'logs'/'run_all.log').open('w',encoding='utf-8') as log:
        print('Blender:',blender,flush=True)
        with subprocess.Popen(cmd,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,encoding='utf-8',errors='replace') as process:
            for line in process.stdout:
                log.write(line);log.flush()
                if any(t in line for t in ['VALIDATION','RENDER','COMPLETE','Error','Traceback','Saved','Render device']):print(line.rstrip(),flush=True)
            code=process.wait()
        if code:raise SystemExit(f'Blender failed ({code}). Read logs/run_all.log')
    verify_cmd=[blender,'--background','--factory-startup','--python-exit-code','1','--python',str(ROOT/'scripts'/'verify_saved.py')]
    with (ROOT/'logs'/'verification.log').open('w',encoding='utf-8') as log:
        result=subprocess.run(verify_cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
    if result.returncode:raise SystemExit('Saved file verification failed. Read logs/verification.log')
    print('Saved .blend reopened and verified.')
    print('Finished:',ROOT/'models'/'HEL-1_Boeing_737-300.blend')

if __name__=='__main__':main()

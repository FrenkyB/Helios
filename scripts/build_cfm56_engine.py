"""Append engine to the current final project; verify before publishing candidate."""
import argparse
import datetime
import json
from pathlib import Path
import shutil
import sys

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import cfm56_engine as engine
from verify_cfm56_engine import protected_state, inventory, verify


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source',default=str(ROOT/'models'/'Boeing_737-300_Helios_Livery.blend'))
    parser.add_argument('--skip-render',action='store_true')
    parser.add_argument('--draft',action='store_true')
    options = parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    for folder in ('reports','renders/cfm56','logs'):
        (ROOT/folder).mkdir(parents=True,exist_ok=True)
    source = Path(options.source).resolve()
    bpy.ops.wm.open_mainfile(filepath=str(source))
    active = bpy.context.window.scene.name
    print('CFM56: Snapshot all existing scenes, including pressurization panel',flush=True)
    before = protected_state()
    print('CFM56: Build centreline, shafts, stages, shells and controls',flush=True)
    engine.build()
    if protected_state()!=before:
        raise RuntimeError('Engine build changed unrelated project content')
    first = inventory()
    print('CFM56: Rebuild to verify ownership cleanup and stable inventory',flush=True)
    engine.build()
    if first!=inventory() or protected_state()!=before:
        raise RuntimeError('Engine rebuild is not idempotent or changed existing content')
    pending = ROOT/'reports'/'CFM56_pending.blend'
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(pending))
    report = verify(pending,before)
    report['checks']['idempotent_datablock_inventory'] = True
    # Verification animation leaves only orphaned test actions; remove owned ones.
    for action in list(bpy.data.actions):
        if action.get(engine.OWNER) and action.users==0:
            bpy.data.actions.remove(action)
    scene = bpy.data.scenes[engine.SCENE]
    scene.render.filepath = str(ROOT/'renders'/'cfm56'/'technical_cutaway.png')
    # Keep the project's in-file launcher current as well as its disk source.
    launcher = bpy.data.texts.get('run_all.py') or bpy.data.texts.new('run_all.py')
    launcher.clear()
    launcher.write((ROOT/'run_all.py').read_text(encoding='utf-8'))
    launcher.filepath = str(ROOT/'run_all.py')
    if active in bpy.data.scenes:
        bpy.context.window.scene = bpy.data.scenes[active]
    output = ROOT/'models'/'Boeing_737-300_Helios_Livery.blend'
    if output.exists():
        backup = ROOT/'reports'/'backups'/('cfm56_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
        backup.mkdir(parents=True)
        shutil.copy2(output,backup/output.name)
    bpy.ops.wm.save_as_mainfile(filepath=str(output))
    report['file'] = str(output)
    (ROOT/'reports'/'cfm56_engine_verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    pending.unlink(missing_ok=True)
    if not options.skip_render:
        scene.render.resolution_percentage = 65 if options.draft else 100
        scene.cycles.samples = 20 if options.draft else 48
        bpy.ops.render.render(write_still=True,scene=scene.name)
    print('COMPLETE CFM56 engine',output,flush=True)


if __name__=='__main__':
    main()

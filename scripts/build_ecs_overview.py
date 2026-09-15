"""Append the phase-1 overview; publish only after preservation/reopen checks."""
import argparse
import datetime
import json
from pathlib import Path
import shutil
import sys

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import ecs_overview as overview
from verify_ecs_overview import protected_state, inventory, verify


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source',default=str(ROOT/'models'/'Boeing_737-300_Helios_Livery.blend'))
    parser.add_argument('--skip-render',action='store_true')
    parser.add_argument('--draft',action='store_true')
    options = parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    for folder in ('reports','renders/ecs_overview','logs'):
        (ROOT/folder).mkdir(parents=True,exist_ok=True)
    source = Path(options.source).resolve()
    bpy.ops.wm.open_mainfile(filepath=str(source))
    active = bpy.context.window.scene.name
    print('ECS: Snapshot all existing scenes and source assets',flush=True)
    before = protected_state()
    overview.build()
    if protected_state()!=before:
        raise RuntimeError('Overview build changed unrelated project content')
    first = inventory()
    print('ECS: Rebuild to check owned cleanup and stable inventory',flush=True)
    overview.build()
    if first!=inventory() or protected_state()!=before:
        raise RuntimeError('Overview rebuild is not idempotent or changed existing content')
    pending = ROOT/'reports'/'ECS_Overview_pending.blend'
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(pending))
    report = verify(pending,before)
    report['checks']['idempotent_datablock_inventory'] = True
    scene = bpy.data.scenes[overview.SCENE]
    scene.render.filepath = str(ROOT/'renders'/'ecs_overview'/'wide.png')
    launcher = bpy.data.texts.get('run_all.py') or bpy.data.texts.new('run_all.py')
    launcher.clear()
    launcher.write((ROOT/'run_all.py').read_text(encoding='utf-8'))
    launcher.filepath = str(ROOT/'run_all.py')
    if active in bpy.data.scenes:
        bpy.context.window.scene = bpy.data.scenes[active]
    output = ROOT/'models'/'Boeing_737-300_Helios_Livery.blend'
    if output.exists():
        backup = ROOT/'reports'/'backups'/('ecs_overview_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
        backup.mkdir(parents=True)
        shutil.copy2(output,backup/output.name)
    bpy.ops.wm.save_as_mainfile(filepath=str(output))
    report['file'] = str(output)
    (ROOT/'reports'/'ecs_overview_verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    pending.unlink(missing_ok=True)
    if not options.skip_render:
        scene.render.resolution_percentage = 65 if options.draft else 100
        scene.cycles.samples = 20 if options.draft else 48
        bpy.ops.render.render(write_still=True,scene=scene.name)
    print('COMPLETE ECS overview',output,flush=True)


if __name__=='__main__':
    main()

"""Extend the saved overview; publish to the same project after preservation tests."""
import argparse
import datetime
import json
from pathlib import Path
import shutil
import sys

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import ecs_phase2 as phase2
from verify_ecs_phase2 import protected_state, inventory, verify


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', default=str(ROOT/'models'/'Boeing_737-300_Helios_Livery.blend'))
    parser.add_argument('--skip-render', action='store_true')
    parser.add_argument('--draft', action='store_true')
    options = parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    for folder in ('reports', 'renders/ecs_phase2', 'logs'):
        (ROOT/folder).mkdir(parents=True, exist_ok=True)
    source = Path(options.source).resolve()
    bpy.ops.wm.open_mainfile(filepath=str(source))
    active = bpy.context.window.scene.name
    print('ECS Phase 2: Protect all original scenes and Phase 1 state', flush=True)
    before = protected_state()
    phase2.build()
    if protected_state() != before:
        raise RuntimeError('Phase 2 changed existing project or Phase 1 content')
    first = inventory()
    print('ECS Phase 2: Rebuild only owned resources and compare inventory', flush=True)
    phase2.build()
    if first != inventory() or protected_state() != before:
        raise RuntimeError('Phase 2 rebuild changed inventory or protected content')
    pending = ROOT/'reports'/'ECS_Phase2_pending.blend'
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(pending))
    report = verify(pending, before)
    report['checks']['idempotent_datablock_inventory'] = True
    if active in bpy.data.scenes:
        bpy.context.window.scene = bpy.data.scenes[active]
    output = ROOT/'models'/'Boeing_737-300_Helios_Livery.blend'
    if output.exists():
        backup = ROOT/'reports'/'backups'/('ecs_phase2_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
        backup.mkdir(parents=True)
        shutil.copy2(output, backup/output.name)
    bpy.ops.wm.save_as_mainfile(filepath=str(output))
    report['file'] = str(output)
    (ROOT/'reports'/'ecs_phase2_verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    pending.unlink(missing_ok=True)
    if not options.skip_render:
        scene = bpy.data.scenes[phase2.SCENE]
        scene.camera = bpy.data.objects['CAM_ECS_PHASE2_LEFT']
        scene.render.filepath = str(ROOT/'renders'/'ecs_phase2'/'left.png')
        scene.render.resolution_percentage = 65 if options.draft else 100
        scene.cycles.samples = 20 if options.draft else 48
        bpy.ops.render.render(write_still=True, scene=scene.name)
    print('COMPLETE ECS Phase 2', output, flush=True)


if __name__ == '__main__':
    main()

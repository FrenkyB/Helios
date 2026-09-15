"""Update installed-engine presentation and publish the existing final project."""
import argparse
import datetime
import json
from pathlib import Path
import shutil
import sys

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import ecs_engine_presentation as presentation
from verify_ecs_engine_presentation import protected_state, inventory, owned_state, verify


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', default=str(ROOT / 'models' / 'Boeing_737-300_Helios_Livery.blend'))
    parser.add_argument('--skip-render', action='store_true')
    parser.add_argument('--draft', action='store_true')
    options = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    for folder in ('reports', 'renders/ecs_engine_presentation', 'logs'):
        (ROOT / folder).mkdir(parents=True, exist_ok=True)
    source = Path(options.source).resolve()
    bpy.ops.wm.open_mainfile(filepath=str(source))
    active = bpy.context.window.scene.name
    print('ECS engine presentation: protect original project and both ECS phases', flush=True)
    before = protected_state()
    presentation.build()
    if protected_state() != before:
        raise RuntimeError('Engine presentation changed protected project content')
    first_inventory, first_state = inventory(), owned_state()
    print('ECS engine presentation: rebuild owned resources and compare exact state', flush=True)
    presentation.build()
    if inventory() != first_inventory or owned_state() != first_state:
        raise RuntimeError('Engine presentation rebuild changed generated inventory or state')
    if protected_state() != before:
        raise RuntimeError('Engine presentation rebuild changed protected project content')
    pending = ROOT / 'reports' / 'ECS_Engine_Presentation_pending.blend'
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(pending))
    report = verify(pending, before)
    report['checks']['idempotent_datablock_inventory'] = True
    report['checks']['idempotent_generated_state'] = True
    if active in bpy.data.scenes:
        bpy.context.window.scene = bpy.data.scenes[active]
    output = ROOT / 'models' / 'Boeing_737-300_Helios_Livery.blend'
    if output.exists():
        backup = ROOT / 'reports' / 'backups' / ('ecs_engine_presentation_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
        backup.mkdir(parents=True)
        shutil.copy2(output, backup / output.name)
    bpy.ops.wm.save_as_mainfile(filepath=str(output))
    report['file'] = str(output)
    (ROOT / 'reports' / 'ecs_engine_presentation_verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    pending.unlink(missing_ok=True)
    if not options.skip_render:
        scene = bpy.data.scenes[presentation.SCENE]
        scene.camera = bpy.data.objects['CAM_OVERVIEW_ENGINE_STUDY']
        scene.render.filepath = str(ROOT / 'renders' / 'ecs_engine_presentation' / 'engine_study.png')
        scene.render.resolution_percentage = 65 if options.draft else 100
        scene.cycles.samples = 20 if options.draft else 48
        bpy.ops.render.render(write_still=True, scene=scene.name)
    print('COMPLETE ECS engine presentation', output, flush=True)


if __name__ == '__main__':
    main()

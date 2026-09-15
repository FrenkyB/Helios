"""Append the independent panel, verify a reopened candidate, then save delivery."""
import argparse
import datetime
import json
from pathlib import Path
import shutil
import sys

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import pressurization_panel as panel
from verify_pressurization_panel import protected_state, verify


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',default=str(ROOT/'models'/'Boeing_737-300_Helios_Livery.blend'))
    parser.add_argument('--skip-render',action='store_true')
    parser.add_argument('--draft',action='store_true')
    options=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    source=Path(options.source).resolve()
    for folder in ('models','reports','renders','logs'):
        (ROOT/folder).mkdir(exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(source))
    active_scene=bpy.context.window.scene.name
    print('PRESS: Snapshot existing aircraft and airport',flush=True)
    before=protected_state()
    print('PRESS: Build panel geometry and drivers',flush=True)
    panel.build()
    print('PRESS: Check existing scene preservation',flush=True)
    if protected_state()!=before:
        raise RuntimeError('Panel build changed existing aircraft or airport data')
    pending=ROOT/'reports'/'Pressurization_pending.blend'
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(pending))
    print('PRESS: Reopen candidate and exercise all controls',flush=True)
    report=verify(pending,before)
    scene=bpy.data.scenes[panel.SCENE]
    scene.render.filepath=str(ROOT/'renders'/'pressurization_panel.png')
    # Restore the main airport view; the asset is available through the scene menu.
    if active_scene in bpy.data.scenes:
        bpy.context.window.scene=bpy.data.scenes[active_scene]
    output=ROOT/'models'/'Boeing_737-300_Helios_Livery.blend'
    if output.exists():
        backup=ROOT/'reports'/'backups'/('pressurization_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
        backup.mkdir(parents=True)
        shutil.copy2(output,backup/output.name)
    bpy.ops.wm.save_as_mainfile(filepath=str(output))
    report['file']=str(output)
    (ROOT/'reports'/'pressurization_panel_verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    pending.unlink()
    if not options.skip_render:
        scene.render.resolution_percentage=70 if options.draft else 100
        scene.cycles.samples=24 if options.draft else 48
        bpy.ops.render.render(write_still=True,scene=scene.name)
    print('COMPLETE Pressurization panel',output,flush=True)


if __name__=='__main__':
    main()

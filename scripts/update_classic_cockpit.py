"""Upgrade only cockpit interior; keep every exterior and passenger object."""
import argparse
import json
from pathlib import Path
import sys

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import classic_cockpit
from verify_classic_cockpit import protected_state, verify


def render(draft=False):
    scene = bpy.data.scenes[classic_cockpit.SCENE]
    directory = ROOT / 'renders' / 'cockpit'
    directory.mkdir(parents=True, exist_ok=True)
    for name in ['overview', 'instruments', 'overhead', 'seats_and_door']:
        scene.camera = bpy.data.objects[classic_cockpit.PREFIX + 'Camera ' + name]
        scene.render.resolution_percentage = 65 if draft else 100
        scene.cycles.samples = 24 if draft else 64
        scene.render.filepath = str(directory / f'{name}.png')
        print('RENDER cockpit', name, flush=True)
        bpy.ops.render.render(write_still=True, scene=scene.name)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', default=str(ROOT / 'models' / 'Boeing_737-300_Helios_Livery.blend'))
    parser.add_argument('--skip-render', action='store_true')
    parser.add_argument('--draft', action='store_true')
    parser.add_argument('--render-only', action='store_true')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    bpy.ops.wm.open_mainfile(filepath=str(Path(args.source).resolve()))
    if args.render_only:
        render(args.draft)
        return
    before = protected_state()
    bpy.context.window.scene = bpy.data.scenes['HEL-1 | Boeing 737-300']
    old = bpy.data.collections.get(classic_cockpit.COLLECTION)
    objects = set(old.all_objects) if old else set()
    collections = {old, *old.children_recursive} if old else set()
    scenes = [s for s in bpy.data.scenes if s.name.startswith('02 |')]
    for scene in scenes:
        objects.update(scene.objects)
        collections.update(scene.collection.children_recursive)
    for scene in scenes:
        bpy.data.scenes.remove(scene)
    for obj in objects:
        data, kind = obj.data, obj.type
        bpy.data.objects.remove(obj, do_unlink=True)
        if data is not None and data.users == 0:
            container = {'MESH': bpy.data.meshes, 'CURVE': bpy.data.curves, 'FONT': bpy.data.curves,
                         'CAMERA': bpy.data.cameras, 'LIGHT': bpy.data.lights}.get(kind)
            if container is not None:
                container.remove(data)
    for col in collections:
        bpy.data.collections.remove(col)
    for mat in list(bpy.data.materials):
        if mat.name.startswith(classic_cockpit.PREFIX) and not mat.users:
            bpy.data.materials.remove(mat)
    classic_cockpit.build()
    if before != protected_state():
        raise RuntimeError('An object, material or scene outside the cockpit changed before saving')
    readme = bpy.data.texts.get('CLASSIC_FLIGHT_DECK_README') or bpy.data.texts.new('CLASSIC_FLIGHT_DECK_README')
    readme.clear()
    readme.write('737 CLASSIC FLIGHT DECK\n\nScene 02: fitted cockpit interior with four inspection cameras.\n'
                 'The cockpit collection is also linked to the aircraft scene.\n'
                 'Panel geometry follows 737-300_cockpit overview and enlarged reference boards.\n'
                 'Classic EADI/EHSI, analog standby instruments, MCP, throttle, overhead and crew seats.\n'
                 'Exterior skin and glazing, livery and passenger cabin are preserved.\n'
                 'The exterior shell remains closed; use scene 02 for interior inspection.\n'
                 'Packed source-image UV regions carry labels/displays; controls and panel housings are editable 3D.\nVisual reconstruction, not functional avionics or an exact Helios equipment fit.\n'
                 'Rebuild cockpit only: python run_all.py --cockpit-interior\n')
    output = ROOT / 'models' / 'Boeing_737-300_Helios_Livery.blend'
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(output))
    verify(output, before=before)
    if not args.skip_render:
        render(args.draft)


if __name__ == '__main__':
    main()

"""Replace only passenger collections, preserving the saved cockpit and exterior."""
import argparse
import json
from pathlib import Path
import sys
import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import passenger_cabin
from correct_cockpit_windows import fingerprint
from verify_passenger_cabin import update_scenes, material_state, verify
from render_passenger_cabin import render


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', default=str(ROOT / 'models' / 'Boeing_737-300_Helios_Livery.blend'))
    parser.add_argument('--skip-render', action='store_true')
    parser.add_argument('--draft', action='store_true')
    options = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    bpy.ops.wm.open_mainfile(filepath=str(Path(options.source).resolve()))
    update_scenes()
    old_root = bpy.data.collections.get(passenger_cabin.CABIN_COLLECTION)
    removable = set(old_root.all_objects) if old_root else set()
    scenes = [s for s in bpy.data.scenes if s.name.startswith(('03 | Cabin', '03 | Passenger cabin', '04 | Passenger cabin'))]
    collections = set()
    if old_root:
        collections.add(old_root)
        collections.update(old_root.children_recursive)
    for scene in scenes:
        removable.update(scene.objects)
        collections.update(scene.collection.children_recursive)
    before = {o.name: fingerprint(o) for o in bpy.data.objects if o not in removable}
    used_mats = {m for o in bpy.data.objects if o not in removable and hasattr(o.data, 'materials') for m in o.data.materials if m}
    before_mats = {m.name: material_state(m) for m in used_mats}
    bpy.context.window.scene = bpy.data.scenes['HEL-1 | Boeing 737-300']
    for scene in scenes:
        bpy.data.scenes.remove(scene)
    for obj in removable:
        data, kind = obj.data, obj.type
        bpy.data.objects.remove(obj, do_unlink=True)
        if data is not None and data.users == 0:
            container = {'MESH': bpy.data.meshes, 'CURVE': bpy.data.curves,
                         'FONT': bpy.data.curves, 'LIGHT': bpy.data.lights,
                         'CAMERA': bpy.data.cameras}.get(kind)
            if container is not None:
                container.remove(data)
    for col in collections:
        bpy.data.collections.remove(col)
    for mat in list(bpy.data.materials):
        if mat.name.startswith('Passenger | ') and not mat.users:
            bpy.data.materials.remove(mat)
    cfg = json.loads((ROOT / 'config' / 'aircraft.json').read_text())['cabin']
    passenger_cabin.build(cfg)
    update_scenes()
    if any(fingerprint(bpy.data.objects[name]) != value for name, value in before.items()):
        raise RuntimeError('A non-passenger object changed before saving')
    output = ROOT / 'models' / 'Boeing_737-300_Helios_Livery.blend'
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(output))
    verify(output)
    preserved = all(fingerprint(bpy.data.objects[name]) == value for name, value in before.items())
    mats_preserved = all(material_state(bpy.data.materials[name]) == value for name, value in before_mats.items())
    report = {'all_non_passenger_objects_preserved': preserved,
              'all_non_passenger_materials_preserved': mats_preserved,
              'preserved_objects': len(before), 'passed': preserved and mats_preserved}
    (ROOT / 'reports' / 'passenger_preservation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('PASSENGER_PRESERVATION_VERIFIED', json.dumps(report), flush=True)
    if not report['passed']:
        raise RuntimeError('Saved passenger-only preservation check failed')
    if not options.skip_render:
        render(options.draft)


if __name__ == '__main__':
    main()

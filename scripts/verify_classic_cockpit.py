"""Saved cockpit geometry, major forms, fit and non-cockpit preservation checks."""
import argparse
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import exterior
from classic_cockpit import COLLECTION, SCENE, PREFIX, REAR
from correct_cockpit_windows import fingerprint
from verify_passenger_cabin import material_state, update_scenes


def protected_state():
    update_scenes()
    cockpit = bpy.data.collections.get(COLLECTION)
    excluded = set(cockpit.all_objects) if cockpit else set()
    for scene in bpy.data.scenes:
        if scene.name.startswith('02 |'):
            excluded.update(scene.objects)
    objects = [obj for obj in bpy.data.objects if obj not in excluded]
    mats = {mat for obj in objects if hasattr(obj.data, 'materials') for mat in obj.data.materials if mat}
    return {'objects': {obj.name: fingerprint(obj) for obj in objects},
            'materials': {mat.name: material_state(mat) for mat in mats},
            'scenes': {s.name: {'camera': s.camera.name if s.camera else None,
                              'objects': sorted(o.name for o in s.objects if o not in excluded)}
                       for s in bpy.data.scenes if not s.name.startswith('02 |')}}


def verify(path, baseline=None, before=None):
    if baseline:
        bpy.ops.wm.open_mainfile(filepath=str(baseline))
        before = protected_state()
    bpy.ops.wm.open_mainfile(filepath=str(path))
    scene = bpy.data.scenes['HEL-1 | Boeing 737-300']
    bpy.context.window.scene = scene
    update_scenes()
    collection = bpy.data.collections[COLLECTION]
    objects = list(collection.all_objects)
    names = {obj.name for obj in objects}
    required = ['Main instrument panel', 'MCP housing', 'Glareshield padded lip',
                'Captain cushion', 'First officer cushion', 'Captain classic control yoke',
                'First officer classic control yoke', 'Center pedestal base', 'Throttle quadrant',
                'Side console -1', 'Side console 1', 'Overhead structural tray',
                'Observer jumpseat folded cushion', 'Cockpit door', 'Rear cockpit boundary']
    outside, nonfinite = [], []
    clearance = float('inf')
    bounds = []
    depsgraph = bpy.context.evaluated_depsgraph_get()
    for obj in objects:
        if obj.type not in {'MESH', 'CURVE', 'FONT'}:
            continue
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        for v in mesh.vertices:
            point = evaluated.matrix_world @ v.co
            x, y, z = point
            if not all(math.isfinite(c) for c in point):
                nonfinite.append(obj.name)
                break
            ry, bottom, top = exterior.profile(x)
            center, rz = (bottom + top) / 2, (top - bottom) / 2
            radial = math.sqrt((y / ry) ** 2 + ((z - center) / rz) ** 2)
            clearance = min(clearance, (1 - radial) * min(ry, rz))
            if radial > 1.002 or x < .9 or x > REAR + .01:
                outside.append(obj.name)
                break
            bounds.append(tuple(point))
        evaluated.to_mesh_clear()
    checks = {
        'saved_file_reopened': True,
        'major_cockpit_components_present': all(PREFIX + name in names for name in required),
        'flight_deck_shared_with_aircraft': all(o.name in scene.objects for o in objects),
        'flight_deck_inspection_scene': SCENE in bpy.data.scenes,
        'six_aligned_inner_windshields': sum(o.name.startswith(PREFIX + 'Inner windshield ') for o in objects) == 6,
        'classic_analog_instruments': sum(o.get('instrument_kind') is not None for o in objects) >= 25,
        'both_pilots_have_classic_EADI_EHSI': all(PREFIX + tag + ' ' + role in names
                                               for tag in ['CAPT', 'FO'] for role in ['EADI', 'EHSI']),
        'two_narrow_engine_indicator_stacks': sum(o.get('display_role') == 'classic_engine_indicators' for o in objects) == 2,
        'reference_images_packed': all(bpy.data.images.get(name) and bpy.data.images[name].packed_file
                                       for name in ['cockpit_1.jpg', 'cockpit_2.jpg', 'cockpit_4.jpg', 'upper_panel.jpg']),
        'distinct_overhead_groups': len({o.get('overhead_group') for o in objects if o.get('overhead_group')}) == 16,
        'pressurization_controls_present': all(PREFIX + name in names for name in
                                               ['FLT ALT digits', 'LAND ALT digits', 'Pressurization mode selector']),
        'inside_preserved_fuselage': not outside,
        'finite_geometry': not nonfinite,
        'existing_138_passenger_seats': sum(o.name.startswith('Seat_') and o.name.endswith(' cushion') for o in bpy.data.objects) == 138,
    }
    after = protected_state()
    changes = []
    if before is not None:
        changes = sorted(name for name in set(before['objects']) | set(after['objects'])
                         if before['objects'].get(name) != after['objects'].get(name))
        checks['all_non_cockpit_objects_identical'] = not changes
        checks['all_non_cockpit_materials_identical'] = before['materials'] == after['materials']
        checks['all_other_scenes_preserved'] = before['scenes'] == after['scenes']
    report = {'passed': all(checks.values()), 'file': str(path), 'checks': checks,
              'cockpit_objects': len(objects), 'preserved_objects': len(after['objects']),
              'outside_objects': sorted(set(outside)), 'nonfinite_objects': nonfinite,
              'changed_non_cockpit_objects': changes, 'minimum_skin_clearance_m': clearance,
              'bounds_min': [min(p[i] for p in bounds) for i in range(3)],
              'bounds_max': [max(p[i] for p in bounds) for i in range(3)],
              'scope': '737 Classic EFIS cockpit matching the user-supplied 737-300_cockpit overview/detail boards; visual model.'}
    (ROOT / 'reports').mkdir(exist_ok=True)
    (ROOT / 'reports' / 'classic_cockpit_verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('CLASSIC_COCKPIT_VERIFIED', json.dumps(report), flush=True)
    if not report['passed']:
        raise RuntimeError('Classic cockpit verification failed; see reports/classic_cockpit_verification.json')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', default=str(ROOT / 'models' / 'Boeing_737-300_Helios_Livery.blend'))
    parser.add_argument('--baseline')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    verify(Path(args.source).resolve(), Path(args.baseline).resolve() if args.baseline else None)

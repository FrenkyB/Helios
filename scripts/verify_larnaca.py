"""Reopen scenery, check scale/orientation and preserve every aircraft object."""
import argparse
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from correct_cockpit_windows import fingerprint
from verify_passenger_cabin import material_state, update_scenes
import larnaca


def protected_state():
    update_scenes()
    objects = [o for o in bpy.data.objects if not o.name.startswith(larnaca.PREFIX)]
    materials = {m for o in objects if hasattr(o.data, 'materials') for m in o.data.materials if m}
    return {
        'objects': {o.name: fingerprint(o) for o in objects},
        'materials': {m.name: material_state(m) for m in materials},
        'scenes': {s.name: {'objects': sorted(o.name for o in s.objects),
                            'camera': s.camera.name if s.camera else None}
                   for s in bpy.data.scenes if s.name != larnaca.SCENE},
    }


def verify(path, before=None, baseline=None):
    if baseline:
        bpy.ops.wm.open_mainfile(filepath=str(baseline))
        before = protected_state()
    bpy.ops.wm.open_mainfile(filepath=str(path))
    cfg = json.loads((ROOT / 'config' / 'larnaca.json').read_text())
    scene = bpy.data.scenes[larnaca.SCENE]
    bpy.context.window.scene = scene
    update_scenes()
    root = bpy.data.collections[larnaca.COLLECTION]
    objects = list(root.all_objects)
    runway = bpy.data.objects[larnaca.PREFIX + 'Runway 04-22 asphalt']
    # Mesh extents are independent of the airport's world rotation.
    extents = [max(v.co[i] for v in runway.data.vertices)-min(v.co[i] for v in runway.data.vertices)
               for i in range(3)]
    direction = runway.matrix_world.to_3x3() @ Vector((1, 0, 0))
    bearing = math.degrees(math.atan2(direction.x, direction.y)) % 360
    aircraft = bpy.data.objects[larnaca.PREFIX + 'Helios 737-300 - stand ' + cfg['helios_stand']]
    assembly = aircraft.instance_collection
    source_exterior = bpy.data.collections['B737_300_EXTERIOR']
    placement = bpy.data.objects[larnaca.PREFIX+'Stand '+cfg['helios_stand']+' aircraft nose']
    tire_objects = [o for o in source_exterior.all_objects
                    if o.name.startswith(('Main tire_', 'Nose tire_'))
                    and not any(s in o.name for s in ['hub','axle','tread'])]
    tire_floor = min((aircraft.matrix_world @ o.matrix_world @ Vector(corner)).z
                     for o in tire_objects for corner in o.bound_box)
    # Screen out invalid coordinates and accidental zero-area scenery faces.
    nonfinite, degenerate = [], []
    for obj in objects:
        if obj.type != 'MESH':
            continue
        if any(not all(math.isfinite(c) for c in v.co) for v in obj.data.vertices):
            nonfinite.append(obj.name)
        if any(p.area < 1e-10 for p in obj.data.polygons):
            degenerate.append(obj.name)
    checks = {
        'saved_file_reopened': True,
        'runway_2994_by_45_m': abs(extents[0]-2994) < .001 and abs(extents[1]-45) < .001,
        'runway_true_orientation': abs(bearing-cfg['runway_true_bearing']) < .001,
        'threshold_04': abs(bpy.data.objects[larnaca.PREFIX+'Threshold 04'].location.x-cfg['threshold_04_offset']) < .001,
        'threshold_22': abs(bpy.data.objects[larnaca.PREFIX+'Threshold 22'].location.x-(2994-cfg['threshold_22_displacement'])) < .001,
        'terminal_northwest_of_runway': bpy.data.objects[larnaca.PREFIX+'Terminal pier structure'].location.y > 400,
        'tower_northeast_of_terminal': cfg['tower_uv'][0] > cfg['terminal_u'],
        'ten_contact_stands': sum(o.name.startswith(larnaca.PREFIX+'Stand ') and o.name.endswith(' aircraft nose') for o in objects) == 10,
        'ten_boarding_bridges': sum(' accordion' in o.name for o in objects) == 10,
        'seven_inspection_cameras': sum(o.get('airport_camera') is not None for o in objects) == 7,
        'aircraft_is_reusable_instance': aircraft.instance_type == 'COLLECTION' and source_exterior.name in assembly.children,
        'helios_decals_instanced': '08_HELIOS_Livery' in assembly.children,
        'paint_follows_aircraft_instance': all(bpy.data.objects[n].data.attributes.get('Helios_rest_position') is not None
                                             for n in ['Fuselage | continuous quad loft','Vertical fin with dorsal fillet','Rudder']),
        'aircraft_at_selected_stand': (aircraft.location-placement.location).length < .01,
        'six_tires_touch_apron': len(tire_objects) == 6 and abs(tire_floor-(cfg['apron_height']+.005)) < .015,
        'aircraft_normal_scale': all(abs(s-1) < 1e-6 for s in aircraft.scale),
        'airport_separate_from_study': not any(o.name.startswith(larnaca.PREFIX) for o in bpy.data.scenes['HEL-1 | Boeing 737-300'].objects),
        'finite_mesh_coordinates': not nonfinite,
        'no_zero_area_mesh_faces': not degenerate,
    }
    changes = []
    if before is not None:
        after = protected_state()
        changes = [n for n in set(before['objects']) | set(after['objects'])
                   if before['objects'].get(n) != after['objects'].get(n)]
        checks['every_original_object_preserved'] = not changes
        checks['every_original_material_preserved'] = before['materials'] == after['materials']
        checks['every_original_scene_preserved'] = before['scenes'] == after['scenes']
    report = {'passed': all(checks.values()), 'file': str(path), 'checks': checks,
              'scenery_objects': len(objects), 'unique_meshes': len({o.data for o in objects if o.type == 'MESH'}),
              'runway_local_dimensions_m': extents, 'runway_true_bearing': bearing,
              'tires_ground_z': tire_floor, 'changed_original_objects': sorted(changes),
              'nonfinite_objects': nonfinite, 'degenerate_objects': degenerate,
              'limitations': cfg['accuracy_notes']}
    (ROOT/'reports').mkdir(exist_ok=True)
    (ROOT/'reports'/'larnaca_verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('LARNACA_VERIFIED', json.dumps(report), flush=True)
    if not report['passed']:
        raise RuntimeError('Larnaca verification failed; see reports/larnaca_verification.json')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', default=str(ROOT/'models'/'Boeing_737-300_Helios_Livery.blend'))
    parser.add_argument('--baseline')
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    verify(Path(args.source), baseline=Path(args.baseline) if args.baseline else None)

"""Reopen the result and check seat layout, fuselage fit and cockpit preservation."""
import argparse
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import exterior
from correct_cockpit_windows import fingerprint
from passenger_cabin import CABIN_COLLECTION, LAYOUT_SCENE, row_stations


def update_scenes():
    for scene in bpy.data.scenes:
        for layer in scene.view_layers:
            layer.update()


def material_state(material):
    nodes, links = [], []
    if material.node_tree:
        for node in material.node_tree.nodes:
            inputs = []
            for socket in node.inputs:
                if hasattr(socket, 'default_value'):
                    value = socket.default_value
                    try:
                        value = tuple(value)
                    except TypeError:
                        pass
                    inputs.append((socket.identifier, str(value)))
            nodes.append((node.name, node.bl_idname, inputs))
        links = sorted((link.from_node.name, link.from_socket.identifier,
                        link.to_node.name, link.to_socket.identifier) for link in material.node_tree.links)
    return str((tuple(material.diffuse_color), nodes, links))


def cockpit_state():
    update_scenes()
    collection = bpy.data.collections.get('B737_300_COCKPIT_STUDY')
    objects = set(collection.all_objects) if collection else set()
    objects.update(o for o in bpy.data.objects if o.name.startswith(('Cockpit pane_', 'Cockpit frame_', 'Wiper_')))
    mats = {mat for obj in objects if hasattr(obj.data, 'materials') for mat in obj.data.materials if mat}
    return {'objects': {obj.name: fingerprint(obj) for obj in objects},
            'materials': {mat.name: material_state(mat) for mat in mats}}


def verify(path, baseline=None):
    old_cockpit = None
    if baseline:
        bpy.ops.wm.open_mainfile(filepath=str(baseline))
        old_cockpit = cockpit_state()
    bpy.ops.wm.open_mainfile(filepath=str(path))
    aircraft = bpy.data.scenes['HEL-1 | Boeing 737-300']
    bpy.context.window.scene = aircraft
    update_scenes()
    cfg = json.loads((ROOT / 'config' / 'aircraft.json').read_text())['cabin']
    collection = bpy.data.collections[CABIN_COLLECTION]
    seats = [obj for obj in collection.all_objects if obj.name.startswith('Seat_') and obj.name.endswith(' cushion')]
    expected_ids = {f'{row:02}{letter}' for row in range(1, cfg['rows'] + 1) for letter in 'ABCDEF'}
    stations = row_stations(cfg)
    layout_ok = True
    for obj in seats:
        row, letter = obj['row'], obj['seat_letter']
        index = 'CBA'.index(letter) if letter in 'ABC' else 'DEF'.index(letter)
        side = -1 if letter in 'ABC' else 1
        expected_y = side * (cfg['aisle_width'] / 2 + .025 + (index + .5) * cfg['seat_cell_width'])
        layout_ok &= abs(obj.location.x + .025 - stations[row - 1]) < 1e-5
        layout_ok &= abs(obj.location.y - expected_y) < 1e-5
        layout_ok &= abs(obj.location.z - (cfg['floor_z'] + .44)) < 1e-5
    # Use evaluated geometry so bevels and object transforms participate in fit checks.
    depsgraph = bpy.context.evaluated_depsgraph_get()
    windows_visible = True
    for side, name in [(-1, 'Passenger sidewall port'), (1, 'Passenger sidewall starboard')]:
        wall = bpy.data.objects[name]
        tree = BVHTree.FromObject(wall, depsgraph)
        for window in [o for o in collection.all_objects if o.name.startswith(f'Passenger window {side} ')]:
            center = sum((window.matrix_world @ v.co for v in window.data.vertices), Vector()) / len(window.data.vertices)
            hit, normal, index, distance = tree.ray_cast(Vector((center.x, 0, center.z)), Vector((0, side, 0)), 3)
            windows_visible &= hit is not None and distance > abs(center.y)
    outside, nonfinite = [], []
    minimum_skin_clearance = float('inf')
    for obj in collection.all_objects:
        if obj.type not in {'MESH', 'CURVE', 'FONT'}:
            continue
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        for vertex in mesh.vertices:
            x, y, z = evaluated.matrix_world @ vertex.co
            if not all(math.isfinite(c) for c in (x, y, z)):
                nonfinite.append(obj.name)
                break
            ry, bottom, top = exterior.profile(x)
            rz, center = (top - bottom) / 2, (top + bottom) / 2
            radial = math.sqrt((y / ry) ** 2 + ((z - center) / rz) ** 2)
            minimum_skin_clearance = min(minimum_skin_clearance, (1 - radial) * min(ry, rz))
            if radial > 1.001 or x < cfg['front_x'] - .05 or x > cfg['rear_x'] + .05:
                outside.append(obj.name)
                break
        evaluated.to_mesh_clear()
    # Clear aisle is measured between the actual armrest bounds.
    arms = [obj for obj in collection.all_objects if obj.name.startswith('Bench_') and obj.name.endswith(' armrest')]
    port_edge = max((obj.matrix_world @ Vector(v)).y for obj in arms if obj.location.y < 0 for v in obj.bound_box)
    starboard_edge = min((obj.matrix_world @ Vector(v)).y for obj in arms if obj.location.y > 0 for v in obj.bound_box)
    exit_forward = stations[cfg['exit_after_row'] - 1] + .40
    exit_aft = stations[cfg['exit_after_row']] - .255
    checks = {
        'file_reopened': True,
        'configured_seat_count': len(seats) == cfg['rows'] * 6,
        'unique_correct_seat_labels': {o['passenger_seat'] for o in seats} == expected_ids,
        'six_seats_per_row_at_configured_stations': bool(layout_ok),
        'all_passenger_geometry_in_aircraft': all(o.name in aircraft.objects for o in collection.all_objects),
        'all_seats_in_layout_scene': all(o.name in bpy.data.scenes[LAYOUT_SCENE].objects for o in seats),
        'clear_aisle_matches_configuration': abs(starboard_edge - port_edge - cfg['aisle_width']) < 1e-5,
        'overwing_passage_clear': exit_forward < 14.65 - .255 and exit_aft > 14.65 + .255,
        'no_passenger_geometry_outside_fuselage': not outside,
        'finite_geometry': not nonfinite,
        'windows_in_front_of_sidewall_not_hidden_by_chords': bool(windows_visible),
        'no_missing_external_libraries': all(Path(bpy.path.abspath(lib.filepath)).exists() for lib in bpy.data.libraries),
        'all_images_packed_or_generated': all(image.packed_file or image.source in {'GENERATED', 'VIEWER'} for image in bpy.data.images),
    }
    if old_cockpit is not None:
        checks['cockpit_identical_to_baseline'] = old_cockpit == cockpit_state()
    report = {'file': str(path), 'baseline': str(baseline) if baseline else None,
              'checks': checks, 'passed': all(checks.values()), 'seat_count': len(seats),
              'clear_aisle_m': starboard_edge - port_edge,
              'row_stations_m': stations, 'minimum_skin_clearance_m': minimum_skin_clearance,
              'outside_fuselage_objects': sorted(set(outside)), 'nonfinite_objects': nonfinite,
              'layout_scope': cfg['reference']}
    (ROOT / 'reports').mkdir(exist_ok=True)
    (ROOT / 'reports' / 'passenger_cabin_verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('PASSENGER_VERIFIED', json.dumps(report), flush=True)
    if not report['passed']:
        raise RuntimeError('Passenger cabin verification failed; read reports/passenger_cabin_verification.json')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', default=str(ROOT / 'models' / 'Boeing_737-300_Helios_Livery.blend'))
    parser.add_argument('--baseline')
    options = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    verify(Path(options.source).resolve(), Path(options.baseline).resolve() if options.baseline else None)

"""Saved-file tests for the additive pneumatic / pack extension of ECS overview.

Protection deliberately includes Phase 1. Only Phase 2-owned resources are
excluded, and the three embedded launcher/help/sidebar texts may be extended.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from types import SimpleNamespace

import bpy
from mathutils import Vector
from mathutils.geometry import interpolate_bezier
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import ecs_overview as overview
from verify_ecs_overview import (
    EXPECTED_SCENES, action_state, animation_state, color_matches, color_state,
    controller_state, evaluated_surface, geometry_fingerprint, material_state,
    plain_value, pointers, scalar_state, update_scenes, vertical_surface_span,
    world_state,
)

OWNER = 'ecs_phase2_asset'
CONTROLLER = 'CTRL_ECS_PHASE2'
COLLECTION = 'ECS_PHASE2'
GROUPS = ('PNEUMATIC_DUCTS', 'PRECOOLERS', 'PACKS', 'PHASE2_AIRFLOW', 'PHASE2_HELPERS')
SIDES = ('LEFT', 'RIGHT')
FLOW_KINDS = ('HOT_BLEED', 'PRECOOLED', 'PACK_OUTPUT')
SWITCHES = ('SHOW_DUCTS', 'SHOW_PRECOOLERS', 'SHOW_PACKS', 'SHOW_AIRFLOW', 'SHOW_LEFT', 'SHOW_RIGHT')
EDITABLE_TEXTS = {'ECS_OVERVIEW_CONTROL.py', 'ECS_OVERVIEW_README', 'ECS_OVERVIEW_README.md', 'run_all.py'}


def properties(data):
    return {str(key): plain_value(value) for key, value in data.items()}


def property_ui(data):
    result = {}
    for key in data.keys():
        try:
            result[key] = plain_value(data.id_properties_ui(key).as_dict())
        except (KeyError, TypeError):
            pass
    return result


def protected_state(raw=False):
    """Fingerprint original project and all Phase 1 state, including its wires."""
    update_scenes()
    # Object.users_collection scans the entire project for each object. Invert
    # direct memberships once, including scene master collections; retain list
    # entries because distinct scene roots can have the same display name.
    memberships = {obj: [] for obj in bpy.data.objects}
    for col in list(bpy.data.collections) + [scene.collection for scene in bpy.data.scenes]:
        for obj in col.objects:
            memberships[obj].append(col.name)
    result = {key: {} for key in ('objects', 'geometry', 'materials', 'scenes',
                                  'collections', 'actions', 'worlds', 'texts', 'node_groups')}
    for category in ('meshes', 'curves', 'cameras', 'lights'):
        for data in getattr(bpy.data, category):
            if not data.get(OWNER):
                key = data.bl_rna.identifier + ' | ' + data.name
                result['geometry'][key] = [geometry_fingerprint(data), properties(data), animation_state(data)]
    for obj in bpy.data.objects:
        if obj.get(OWNER):
            continue
        result['objects'][obj.name] = [
            obj.type, obj.data.name if obj.data else None, scalar_state(obj),
            [list(row) for row in obj.matrix_world],
            [list(row) for row in obj.matrix_parent_inverse],
            obj.parent.name if obj.parent else None,
            sorted(memberships[obj]),
            [(slot.link, slot.material.name if slot.material else None) for slot in obj.material_slots],
            [(scalar_state(mod), pointers(mod)) for mod in obj.modifiers],
            [(scalar_state(con), pointers(con)) for con in obj.constraints],
            properties(obj), property_ui(obj), animation_state(obj),
        ]
    for mat in bpy.data.materials:
        if not mat.get(OWNER):
            result['materials'][mat.name] = [material_state(mat), scalar_state(mat), properties(mat),
                animation_state(mat), animation_state(mat.node_tree) if mat.node_tree else None]
    for col in bpy.data.collections:
        if not col.get(OWNER):
            result['collections'][col.name] = [scalar_state(col), properties(col),
                sorted(obj.name for obj in col.objects if not obj.get(OWNER)),
                sorted(child.name for child in col.children if not child.get(OWNER))]
    for scene in bpy.data.scenes:
        result['scenes'][scene.name] = [
            sorted(obj.name for obj in scene.objects if not obj.get(OWNER)),
            sorted(col.name for col in scene.collection.children if not col.get(OWNER)),
            scene.camera.name if scene.camera else None, scene.world.name if scene.world else None,
            scalar_state(scene.render), scalar_state(scene.view_settings), scalar_state(scene.unit_settings),
            scalar_state(scene.cycles), scene.frame_current, scene.frame_subframe,
            scene.frame_start, scene.frame_end, properties(scene), animation_state(scene),
        ]
    for world in bpy.data.worlds:
        if not world.get(OWNER):
            result['worlds'][world.name] = [scalar_state(world), properties(world), world_state(world),
                animation_state(world), animation_state(world.node_tree) if world.node_tree else None]
    for action in bpy.data.actions:
        if not action.get(OWNER):
            result['actions'][action.name] = action_state(action)
    for text in bpy.data.texts:
        if not text.get(OWNER) and text.name not in EDITABLE_TEXTS:
            result['texts'][text.name] = [text.as_string(), text.use_module, properties(text)]
    for tree in bpy.data.node_groups:
        if not tree.get(OWNER):
            # Existing generators use no complex groups, but preserve their IDs,
            # node properties and topology if a user has added one.
            result['node_groups'][tree.name] = [properties(tree), scalar_state(tree), animation_state(tree),
                [(node.name, node.bl_idname, scalar_state(node), pointers(node),
                  [(socket.identifier, plain_value(socket.default_value)) for socket in node.inputs
                   if hasattr(socket, 'default_value')]) for node in tree.nodes],
                sorted((link.from_node.name, link.from_socket.identifier, link.to_node.name,
                        link.to_socket.identifier) for link in tree.links)]
    if raw:
        return result
    return {key: hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode('utf-8')).hexdigest()
            for key, value in result.items()}


def inventory():
    return {category: sorted(block.name for block in getattr(bpy.data, category) if block.get(OWNER))
            for category in ('scenes', 'collections', 'objects', 'meshes', 'curves', 'materials',
                             'cameras', 'lights', 'worlds', 'actions', 'texts', 'node_groups')}


def canonical_owned_name(name):
    if not re.search(r'\.\d{3}$', name):
        return True
    # Generator labels include real station coordinates such as "rail 14.965".
    # Blender-appended copies ("rail 14.965.001" or "PACK_LEFT.001") fail this.
    return bool(re.fullmatch(r'ECS P2 \| (LEFT|RIGHT) .+ -?\d+\.\d{3}', name))


def native_drivers():
    ids = set()
    for category in ('objects', 'meshes', 'curves', 'materials', 'node_groups'):
        for block in getattr(bpy.data, category):
            if block.get(OWNER):
                ids.add(block)
                tree = getattr(block, 'node_tree', None)
                if tree:
                    ids.add(tree)
    return [fc for block in ids if block.animation_data for fc in block.animation_data.drivers]


def handler_state():
    return {name: [(getattr(func, '__module__', ''), getattr(func, '__qualname__', str(func)))
                   for func in getattr(bpy.app.handlers, name)]
            for name in dir(bpy.app.handlers) if isinstance(getattr(bpy.app.handlers, name), list)}


def world_points(curve):
    spline = curve.data.splines[0]
    points = spline.bezier_points if spline.type == 'BEZIER' else spline.points
    return [curve.matrix_world @ Vector(point.co[:3]) for point in points]


def sampled_curve(curve, resolution=32):
    spline = curve.data.splines[0]
    if spline.type != 'BEZIER':
        return world_points(curve)
    result = []
    for a, b in zip(spline.bezier_points, spline.bezier_points[1:]):
        result.extend(curve.matrix_world @ point for point in interpolate_bezier(
            a.co, a.handle_right, b.handle_left, b.co, resolution)[:-1])
    result.append(curve.matrix_world @ spline.bezier_points[-1].co)
    return result


def snapshot_controls(names):
    return {name: controller_state(bpy.data.objects[name]) for name in names}


def restore_controls(states):
    for name, state in states.items():
        obj = bpy.data.objects[name]
        for key, value in state.items():
            obj[key] = value
        obj.update_tag()
    bpy.context.view_layer.update()


def verify_visibility(scene, ctrl, check, details):
    groups = {'SHOW_DUCTS': 'PNEUMATIC_DUCTS', 'SHOW_PRECOOLERS': 'PRECOOLERS',
              'SHOW_PACKS': 'PACKS', 'SHOW_AIRFLOW': 'PHASE2_AIRFLOW'}
    objects = {key: [obj for obj in bpy.data.collections[name].all_objects
                     if obj.type in {'MESH', 'CURVE', 'FONT'}]
               for key, name in groups.items()}
    check('all_physical_and_flow_groups_have_visible_geometry', all(objects.values()))
    for key in SWITCHES:
        ctrl[key] = True
    for setting in (*groups, 'SHOW_LEFT', 'SHOW_RIGHT'):
        for enabled in (False, True):
            ctrl[setting] = enabled
            ctrl.update_tag()
            bpy.context.view_layer.update()
            graph = bpy.context.evaluated_depsgraph_get()
            results = []
            for group, members in objects.items():
                for obj in members:
                    side = obj.get('ecs_p2_side') or obj.get('ecs_phase2_side')
                    expected = not ctrl[group] or (side in SIDES and not ctrl['SHOW_'+side])
                    evaluated = obj.evaluated_get(graph)
                    results.append(evaluated.hide_render == expected and evaluated.hide_viewport == expected)
            check('independent_'+setting+'_'+str(enabled), bool(results) and all(results))
    details['visibility_group_counts'] = {key: len(value) for key, value in objects.items()}


def verify_flow(scene, ctrl, check, details):
    paths = {obj.name: obj for obj in scene.objects if obj.get(OWNER) and obj.get('ecs_p2_role') == 'FLOW_PATH'}
    expected = {'FLOW_'+side+'_'+kind for side in SIDES for kind in FLOW_KINDS}
    check('six_named_flow_paths', set(paths) == expected)
    markers = [obj for obj in scene.objects if obj.get(OWNER) and obj.get('ecs_p2_role') == 'FLOW_MARKER']
    check('native_directional_markers_exist', len(markers) >= 6 and all(obj.type == 'MESH' for obj in markers))
    direction_results, speed_results, records = [], [], []
    frame_start = scene.frame_start
    for path_name, path in sorted(paths.items()):
        pool = [obj for obj in markers if any(con.type == 'FOLLOW_PATH' and con.target == path
                                             for con in obj.constraints)]
        check(path_name+'_has_followers', bool(pool))
        if not pool:
            continue
        marker = min(pool, key=lambda obj: obj.get('ecs_p2_phase', 1.))
        constraint = next(con for con in marker.constraints if con.type == 'FOLLOW_PATH')
        check(path_name+'_native_follow_settings', constraint.use_fixed_location and constraint.use_curve_follow
              and constraint.forward_axis == 'FORWARD_Z')
        snapshots = {}

        def sample(speed, frame):
            ctrl['ECS_FLOW_SPEED'] = speed
            ctrl.update_tag()
            scene.frame_set(frame)
            bpy.context.view_layer.update()
            evaluated = marker.evaluated_get(bpy.context.evaluated_depsgraph_get())
            follower = evaluated.constraints[constraint.name]
            return {'offset': follower.offset_factor,
                    'position': list(evaluated.matrix_world.translation),
                    'direction': list((evaluated.matrix_world.to_3x3() @ Vector((0, 0, 1))).normalized())}

        for label, speed, frame in (('zero_start', 0., frame_start), ('zero_later', 0., frame_start+12),
                                     ('normal_start', .25, frame_start), ('normal_later', .25, frame_start+1),
                                     ('double_later', .5, frame_start+1)):
            snapshots[label] = sample(speed, frame)
        a, b, c = snapshots['normal_start'], snapshots['normal_later'], snapshots['double_later']
        movement = Vector(b['position'])-Vector(a['position'])
        delta = (b['offset']-a['offset']) % 1.
        double_delta = (c['offset']-a['offset']) % 1.
        stationary = (Vector(snapshots['zero_later']['position'])-Vector(snapshots['zero_start']['position'])).length
        forward = movement.length > 1e-5 and movement.normalized().dot(Vector(a['direction'])) > .7
        direction_results.append(forward and delta > 0.)
        speed_results.append(stationary < 1e-6 and abs(double_delta-2.*delta) < 2e-5)
        check(path_name+'_forward_motion', direction_results[-1])
        check(path_name+'_zero_and_double_speed', speed_results[-1])
        records.append({'path': path_name, 'marker': marker.name, 'samples': snapshots,
                        'forward_displacement_m': movement.length})
    check('all_six_branches_animate_forward', len(direction_results) == 6 and all(direction_results))
    check('all_six_branches_share_speed_control', len(speed_results) == 6 and all(speed_results))
    colors = {}
    for kind in FLOW_KINDS:
        materials = []
        for side in SIDES:
            pool = [obj for obj in markers if obj.get('ecs_p2_side') == side and obj.get('ecs_p2_kind') == kind]
            materials.extend(slot.material for obj in pool for slot in obj.material_slots if slot.material)
        check(kind+'_shared_left_right_material', bool(materials) and len(set(materials)) == 1)
        if not materials:
            continue
        mat = materials[0]
        bsdf = mat.node_tree.nodes.get('Principled BSDF')
        rgb = list(bsdf.inputs['Emission Color'].default_value[:3])
        colors[kind] = rgb
        if kind == 'HOT_BLEED':
            correct = rgb[0] > .7 and .02 < rgb[1] < .3 and rgb[2] < .1
        elif kind == 'PRECOOLED':
            correct = rgb[0] > .7 and .3 < rgb[1] < .8 and rgb[2] < .1
        else:
            correct = rgb[0] < .1 and rgb[1] > .3 and rgb[2] > .7
        check(kind+'_technical_color_language', correct and bsdf.inputs['Emission Strength'].default_value > 1.)
    details['flow_color_rgb'] = colors
    details['flow_motion_samples'] = records
    for side in SIDES:
        path = paths['FLOW_'+side+'_HOT_BLEED']
        prefix_name = path.get('ecs_p2_prefix_source')
        prefix = bpy.data.objects.get(prefix_name or '')
        offset = int(path.get('ecs_p2_physical_start_index', 0))
        prefix_points = world_points(prefix) if prefix else []
        check(side+'_hot_flow_extends_existing_valve_route', bool(prefix)
              and prefix.name == 'ECS BLEED | '+side+' ROUTE'
              and len(prefix_points) == offset+1 and all((a-b).length < 2e-5
                  for a, b in zip(prefix_points, world_points(path)[:offset+1])))
        sleeves = [obj for obj in scene.objects if obj.get('ecs_p2_role') == 'FLOW_PREFIX_MARKER'
                   and obj.get('ecs_p2_side') == side]
        check(side+'_engine_prefix_directional_markers_present', bool(sleeves)
              and all(any(con.type == 'FOLLOW_PATH' and con.target == path for con in obj.constraints) for obj in sleeves))


def verify_phase1_controls(scene, ctrl, engine_ctrl, check, details):
    wire = [obj for obj in scene.objects if obj.name.startswith('ECS WIRE | ')]
    aircraft = [obj for obj in scene.objects if obj.name.startswith('ECS AIR | ')]
    wire_mat = bpy.data.materials['ECS | Structural wire']
    for thickness, rgb in ((.002, (.82, .12, .035)), (.018, (.025, .62, .86))):
        ctrl['WIREFRAME_THICKNESS'], ctrl['WIREFRAME_COLOR'] = thickness, rgb
        ctrl.update_tag()
        bpy.context.view_layer.update()
        graph = bpy.context.evaluated_depsgraph_get()
        check('phase1_wire_width_'+str(thickness), len(wire) == 6 and all(
            abs(mod.thickness-thickness) < 1e-6 for obj in wire
            for mod in obj.evaluated_get(graph).modifiers if mod.type == 'WIREFRAME'))
        check('phase1_wire_rgb_'+str(thickness), color_matches(color_state(wire_mat, graph), rgb))
    for shell in (False, True):
        ctrl['SHOW_SHELL'], ctrl['SHOW_WIREFRAME'] = shell, not shell
        ctrl.update_tag()
        bpy.context.view_layer.update()
        graph = bpy.context.evaluated_depsgraph_get()
        check('phase1_shell_wire_independence_'+str(shell), all(
            obj.evaluated_get(graph).hide_render == (not shell) for obj in aircraft)
            and all(obj.evaluated_get(graph).hide_render == shell for obj in wire))
    clones = list(bpy.data.collections[overview.TEMPLATE].all_objects)
    for cutaway, nacelle, internals in ((False, True, True), (True, True, True),
                                       (False, False, True), (False, True, False)):
        engine_ctrl['CUTAWAY_MODE'], engine_ctrl['SHOW_NACELLE'], engine_ctrl['SHOW_INTERNALS'] = cutaway, nacelle, internals
        engine_ctrl.update_tag()
        bpy.context.view_layer.update()
        graph = bpy.context.evaluated_depsgraph_get()
        results = []
        for obj in clones:
            source = bpy.data.objects.get(obj.get('ecs_source_object', ''))
            if not source:
                continue
            groups = {col.name for col in source.users_collection}
            if 'ENGINE_NACELLE' in groups:
                expected = not nacelle or (cutaway and bool(source.get('cutaway_shell')))
            elif groups & {'ENGINE_STATIC', 'ENGINE_N1', 'ENGINE_N2', 'ENGINE_COMBUSTOR'}:
                expected = not internals or (cutaway and bool(source.get('cutaway_shell')))
            else:
                continue
            results.append(obj.evaluated_get(graph).hide_render == expected)
        check('phase1_engine_visibility_'+str((cutaway, nacelle, internals)), bool(results) and all(results))
    static_objects = [obj for group in ('PNEUMATIC_DUCTS', 'PRECOOLERS', 'PACKS')
                      for obj in bpy.data.collections[group].all_objects]
    engine_ctrl['N1_PHASE'] = engine_ctrl['N2_PHASE'] = 0.
    static_samples = []
    rotor_samples = []
    for n1, n2 in ((60., 0.), (0., 90.)):
        engine_ctrl['N1_SPEED'], engine_ctrl['N2_SPEED'] = n1, n2
        engine_ctrl.update_tag()
        scene.frame_set(scene.frame_start+6)
        bpy.context.view_layer.update()
        graph = bpy.context.evaluated_depsgraph_get()
        angles = [bpy.data.objects['ECS ENG | ROT_N'+str(spool)].evaluated_get(graph).rotation_euler.x for spool in (1, 2)]
        seconds = 6.*scene.render.fps_base/scene.render.fps
        check('phase1_independent_N1_N2_'+str((n1, n2)), all(abs(actual+speed*seconds*math.tau/60.) < 1e-5
              for actual, speed in zip(angles, (n1, n2))))
        static_samples.append({obj.name: [list(row) for row in obj.evaluated_get(graph).matrix_world] for obj in static_objects})
        rotor_samples.append({'N1_speed': n1, 'N2_speed': n2, 'angles': angles})
    check('phase2_physical_components_do_not_rotate_with_spools', bool(static_objects) and static_samples[0] == static_samples[1])
    details['engine_rotation_probes'] = rotor_samples


def verify_ui(scene, check):
    source = bpy.data.texts[overview.SCRIPT].as_string()
    namespace = {'__name__': 'ecs_phase2_verification_ui'}
    exec(compile(source, overview.SCRIPT, 'exec'), namespace)
    namespace['register']()
    check('extended_overview_ui_registers_twice', all(namespace['registered_class'](cls) for cls in namespace['CLASSES']))
    class LayoutProbe:
        """Execute the real draw function and collect the controls it exposes."""
        def __init__(self):
            self.properties = []

        def prop(self, data, path, **kwargs):
            self.properties.append((data.name, path))

        def row(self, **kwargs):
            return self

        def column(self, **kwargs):
            return self

        def separator(self, **kwargs):
            pass

        def label(self, **kwargs):
            pass

        def operator(self, *args, **kwargs):
            return SimpleNamespace()

    layout = LayoutProbe()
    namespace['ECS_OVERVIEW_PT_controls'].draw(SimpleNamespace(layout=layout), bpy.context)
    expected_controls = {
        'CTRL_ECS_OVERVIEW': ('SHOW_SHELL', 'SHOW_WIREFRAME', 'WIREFRAME_THICKNESS', 'WIREFRAME_COLOR'),
        'ECS ENG | CTRL_ENGINE': ('CUTAWAY_MODE', 'SHOW_NACELLE', 'SHOW_INTERNALS', 'N1_SPEED', 'N2_SPEED'),
        CONTROLLER: ('ECS_FLOW_SPEED', *SWITCHES),
    }
    check('existing_and_phase2_controls_in_shared_panel', all(
          (name, '["'+key+'"]') in layout.properties for name, keys in expected_controls.items() for key in keys))
    for camera in ('CAM_OVERVIEW_WIDE', 'CAM_OVERVIEW_3Q', 'CAM_OVERVIEW_SIDE'):
        result = bpy.ops.ecs_overview.inspect(camera=camera)
        check('existing_UI_'+camera, result == {'FINISHED'} and scene.camera.name == camera)
    for camera in ('CAM_ECS_PHASE2_LEFT', 'CAM_ECS_PHASE2_RIGHT', 'CAM_ECS_PHASE2_PACKS'):
        if camera in scene.objects:
            result = bpy.ops.ecs_overview.inspect(camera=camera)
            check('phase2_UI_'+camera, result == {'FINISHED'} and scene.camera.name == camera)


def merged_surface(objects, graph):
    vertices, faces = [], []
    for obj in objects:
        evaluated = obj.evaluated_get(graph)
        mesh = evaluated.to_mesh()
        try:
            offset = len(vertices)
            vertices.extend(evaluated.matrix_world @ vertex.co for vertex in mesh.vertices)
            faces.extend(tuple(index+offset for index in poly.vertices) for poly in mesh.polygons)
        finally:
            evaluated.to_mesh_clear()
    return BVHTree.FromPolygons(vertices, faces) if vertices and faces else None


def verify_geometry(scene, check, details):
    graph = bpy.context.evaluated_depsgraph_get()
    config = json.loads((ROOT / 'config' / 'aircraft.json').read_text(encoding='utf-8'))
    floor = config['cabin']['floor_z']
    gear = []
    for obj in scene.objects:
        source = bpy.data.objects.get(obj.get('ecs_source_object', ''))
        if obj.name.startswith('ECS AIR | ') and source and '06_LandingGear' in {col.name for col in source.users_collection}:
            gear.append(obj)
    gear_surface = merged_surface(gear, graph)
    check('existing_aircraft_used_for_clearance', bool(gear_surface))
    branches = {}
    physical_names = {}
    for side in SIDES:
        suffix = 'L' if side == 'LEFT' else 'R'
        wing = evaluated_surface(bpy.data.objects['ECS AIR | Wing main box_'+suffix], graph)
        route_names = {'HOT_BLEED': 'DUCT_BLEED_'+side,
                       'PRECOOLED': 'ECS P2 | '+side+' PRECOOLED DUCT',
                       'PACK_OUTPUT': 'ECS P2 | '+side+' PACK OUTPUT DUCT'}
        physical_names[side] = route_names
        routes = {kind: bpy.data.objects[name] for kind, name in route_names.items()}
        points = {kind: world_points(obj) for kind, obj in routes.items()}
        outlet = bpy.data.objects['ECS BLEED | '+side+' OUTLET']
        source = outlet.matrix_world.translation
        axis = (outlet.matrix_world.to_3x3() @ Vector((0, 0, 1))).normalized()
        first = routes['HOT_BLEED'].data.splines[0].bezier_points[0]
        tangent = routes['HOT_BLEED'].matrix_world.to_3x3() @ (first.handle_right-first.co)
        check(side+'_reuses_existing_installed_outlet', (points['HOT_BLEED'][0]-source).length < 2e-5)
        check(side+'_continues_existing_outlet_orientation', tangent.normalized().dot(axis) > .995)
        check(side+'_three_physical_routes_separate', len({obj.data for obj in routes.values()}) == 3
              and all(obj.get(OWNER) and obj.type == 'CURVE' for obj in routes.values()))
        check(side+'_all_physical_flow_transitions_connected',
              (points['HOT_BLEED'][-1]-points['PRECOOLED'][0]).length < 2e-5
              and (points['PRECOOLED'][-1]-points['PACK_OUTPUT'][0]).length < 2e-5)
        anchor_contract = {
            'PRECOOLER_'+side+'_INPUT': ('HOT_BLEED', None),
            'PRECOOLER_'+side+'_OUTPUT': ('HOT_BLEED', -1),
            'PACK_'+side+'_INPUT': ('PRECOOLED', None),
            'PACK_'+side+'_DISCHARGE': ('PRECOOLED', -1),
            'PACK_'+side+'_OUTPUT': ('PACK_OUTPUT', -1),
        }
        anchors = {}
        for name, (kind, index) in anchor_contract.items():
            obj = bpy.data.objects.get(name)
            position = obj.matrix_world.translation if obj else Vector((999., 999., 999.))
            anchors[name] = list(position)
            distance = ((position-points[kind][index]).length if index is not None
                        else min((position-point).length for point in points[kind]))
            check(name+'_interface_on_actual_duct', obj is not None and obj.type == 'EMPTY'
                  and obj.get(OWNER) and distance < 2e-5)
        end = bpy.data.objects['PACK_'+side+'_OUTPUT']
        output_axis = (end.matrix_world.to_3x3() @ Vector((0, 0, 1))).normalized()
        cold = routes['PACK_OUTPUT'].data.splines[0].bezier_points[-1]
        cold_tangent = routes['PACK_OUTPUT'].matrix_world.to_3x3() @ (cold.co-cold.handle_left)
        check(side+'_output_anchor_oriented_downstream', output_axis.dot(cold_tangent.normalized()) > .995)
        check(side+'_conditioned_output_stops_near_pack', sum((b-a).length for a, b in
              zip(points['PACK_OUTPUT'], points['PACK_OUTPUT'][1:])) < 2.)
        check(side+'_entire_branch_stays_on_own_side', all(point.y < -.05 if side == 'LEFT' else point.y > .05
              for route in points.values() for point in route))
        check(side+'_branch_runs_inward_to_lower_center_body', abs(points['PACK_OUTPUT'][-1].y) < 1.6
              and abs(points['PACK_OUTPUT'][-1].y) < abs(source.y)-2.5)
        measurements = {}
        for kind, route in routes.items():
            flow = bpy.data.objects['FLOW_'+side+'_'+kind]
            offset = int(flow.get('ecs_p2_physical_start_index', 0))
            flow_points = world_points(flow)[offset:]
            check(side+'_'+kind+'_flow_matches_physical_centerline',
                  flow.data.bevel_depth < route.data.bevel_depth
                  and len(flow_points) == len(points[kind])
                  and all((a-b).length < 2e-5 for a, b in zip(flow_points, points[kind])))
            # Compare Bezier handles as well as points: matching waypoints alone
            # does not ensure arrows remain inside a curved physical duct.
            check(side+'_'+kind+'_flow_bend_handles_match_duct', all(
                  (route.matrix_world @ getattr(a, attr)-flow.matrix_world @ getattr(b, attr)).length < 2e-5
                  for index, (a, b) in enumerate(zip(route.data.splines[0].bezier_points,
                                                     list(flow.data.splines[0].bezier_points)[offset:]))
                  for attr in ('handle_left', 'handle_right') if not (offset and index == 0 and attr == 'handle_left')))
            samples = sampled_curve(route, 32)
            radius = route.data.bevel_depth
            margins = []
            for point in samples:
                span = vertical_surface_span(wing, point)
                if span:
                    margins.append(span[1]-point.z-radius)
            clearance = min((gear_surface.find_nearest(point)[3]-radius for point in samples), default=100.) if gear_surface else -1.
            check(side+'_'+kind+'_no_upper_wing_protrusion', not margins or min(margins) > .005)
            check(side+'_'+kind+'_clears_existing_landing_gear', clearance > .02)
            check(side+'_'+kind+'_readable_duct_diameter', .06 <= 2*radius <= .18)
            check(side+'_'+kind+'_bounded_smooth_bends', all(point.handle_left_type == 'FREE'
                  and point.handle_right_type == 'FREE'
                  and (point.handle_left-point.co).cross(point.handle_right-point.co).length < 1e-5
                  for point in route.data.splines[0].bezier_points))
            measurements[kind] = {'samples': len(samples), 'radius_m': radius,
                'minimum_upper_wing_clearance_m': min(margins) if margins else None,
                'minimum_landing_gear_clearance_m': clearance,
                'start_world': list(points[kind][0]), 'end_world': list(points[kind][-1])}
        assembly_bounds = {}
        for assembly, group in (('PRECOOLER', 'PRECOOLERS'), ('PACK', 'PACKS')):
            root = bpy.data.objects.get(assembly+'_'+side)
            objects = [obj for obj in bpy.data.collections[group].all_objects
                       if obj.get('ecs_phase2_side') == side and obj.type in {'MESH', 'CURVE'}]
            check(assembly+'_'+side+'_technical_assembly_with_multiple_parts',
                  root is not None and root.type == 'EMPTY' and len(objects) >= 8)
            vertices = []
            for obj in objects:
                evaluated = obj.evaluated_get(graph)
                mesh = evaluated.to_mesh()
                try:
                    vertices.extend(evaluated.matrix_world @ vertex.co for vertex in mesh.vertices)
                finally:
                    evaluated.to_mesh_clear()
            if not vertices:
                continue
            minimum = [min(point[axis] for point in vertices) for axis in range(3)]
            maximum = [max(point[axis] for point in vertices) for axis in range(3)]
            assembly_bounds[assembly] = {'minimum': minimum, 'maximum': maximum, 'objects': len(objects)}
            check(assembly+'_'+side+'_below_cabin_floor', maximum[2] < floor-.03)
            check(assembly+'_'+side+'_mounting_geometry', any(
                  token in (obj.name+' '+obj.get('ecs_phase2_role', '')).upper()
                  for obj in objects for token in ('MOUNT', 'FRAME', 'SUPPORT', 'BRACKET', 'RAIL')))
            check(assembly+'_'+side+'_heat_exchanger_surface_detail', any(
                  token in obj.name.upper() for obj in objects for token in ('FIN', 'EXCHANGER', 'CORE')))
            if assembly == 'PACK':
                check('PACK_'+side+'_plausible_lower_center_wing_body_position',
                      11.5 < minimum[0] < maximum[0] < config['main_gear_station']-.35
                      and max(abs(minimum[1]), abs(maximum[1])) < config['fuselage_width']/2
                      and minimum[2] > .9 and maximum[2] < floor-.03)
        branches[side] = {'ducts': measurements, 'anchors': anchors, 'assemblies': assembly_bounds}
    check('left_right_physical_routes_are_separate_objects', all(
          bpy.data.objects[physical_names['LEFT'][kind]] != bpy.data.objects[physical_names['RIGHT'][kind]] for kind in FLOW_KINDS))
    check('left_right_ducts_correctly_handed_about_centerline', all(
          (left-Vector((right.x, -right.y, right.z))).length < 2e-5
          for kind in FLOW_KINDS
          for left, right in zip(world_points(bpy.data.objects[physical_names['LEFT'][kind]]),
                                 world_points(bpy.data.objects[physical_names['RIGHT'][kind]]))))
    physical = [obj for group in ('PNEUMATIC_DUCTS', 'PRECOOLERS', 'PACKS')
                for obj in bpy.data.collections[group].all_objects if obj.type in {'MESH', 'CURVE'}]
    mats = {slot.material for obj in physical for slot in obj.material_slots if slot.material}
    check('physical_system_uses_private_non_neon_materials', bool(mats) and all(
          mat.get(OWNER) and mat.use_nodes and any(node.type == 'BSDF_PRINCIPLED'
          and node.inputs['Metallic'].default_value >= .35
          and node.inputs['Emission Strength'].default_value < .1 for node in mat.node_tree.nodes) for mat in mats))
    check('no_phase3_distribution_or_mix_objects', not any(
          token in obj.name.upper() for obj in bpy.data.objects if obj.get(OWNER)
          for token in ('MIX_MANIFOLD', 'CABIN_DISTRIBUTION', 'CROSSOVER', 'OUTFLOW_VALVE', 'RECIRCULATION')))
    details['physical_branches'] = branches


def verify_roundtrip(path, check, details):
    path = Path(path).resolve()
    temporary = ROOT / 'reports' / 'ECS_Phase2_control_roundtrip.blend'
    saved_scene = bpy.context.window.scene.name
    before = snapshot_controls(('CTRL_ECS_OVERVIEW', 'ECS ENG | CTRL_ENGINE', CONTROLLER))
    ctrl = bpy.data.objects[CONTROLLER]
    state = {'SHOW_DUCTS': False, 'SHOW_PRECOOLERS': True, 'SHOW_PACKS': False,
             'SHOW_AIRFLOW': True, 'SHOW_LEFT': True, 'SHOW_RIGHT': False, 'ECS_FLOW_SPEED': .85}
    try:
        bpy.context.window.scene = bpy.data.scenes[overview.SCENE]
        for key, value in state.items():
            ctrl[key] = value
        ctrl.update_tag()
        bpy.context.view_layer.update()
        bpy.ops.wm.save_as_mainfile(filepath=str(temporary), copy=True)
        bpy.ops.wm.open_mainfile(filepath=str(temporary))
        bpy.context.window.scene = bpy.data.scenes[overview.SCENE]
        bpy.context.view_layer.update()
        ctrl = bpy.data.objects[CONTROLLER]
        check('phase2_nondefault_controls_save_reopen', all(abs(float(ctrl[key])-float(value)) < 1e-6
              for key, value in state.items()))
        graph = bpy.context.evaluated_depsgraph_get()
        left = bpy.data.objects['FLOW_LEFT_HOT_BLEED']
        right = bpy.data.objects['FLOW_RIGHT_HOT_BLEED']
        check('native_phase2_visibility_after_reopen', not left.evaluated_get(graph).hide_render
              and right.evaluated_get(graph).hide_render
              and bpy.data.objects['DUCT_BLEED_LEFT'].evaluated_get(graph).hide_render)
        phase1 = snapshot_controls(('CTRL_ECS_OVERVIEW', 'ECS ENG | CTRL_ENGINE'))
        check('phase1_controls_survive_phase2_setting_roundtrip', all(phase1[name] == before[name] for name in phase1))
        marker = next(obj for obj in bpy.data.collections['PHASE2_AIRFLOW'].objects
                      if obj.get('ecs_p2_role') == 'FLOW_MARKER' and obj.get('ecs_p2_side') == 'LEFT')
        scene = bpy.data.scenes[overview.SCENE]
        positions = []
        for frame in (scene.frame_start, scene.frame_start+1):
            scene.frame_set(frame)
            bpy.context.view_layer.update()
            positions.append(marker.evaluated_get(bpy.context.evaluated_depsgraph_get()).matrix_world.translation.copy())
        check('native_phase2_motion_after_reopen', (positions[1]-positions[0]).length > .001)
        details['saved_nondefault_phase2_control_probe'] = state
    finally:
        bpy.ops.wm.open_mainfile(filepath=str(path))
        bpy.context.window.scene = bpy.data.scenes[saved_scene]
    check('candidate_controls_restored_after_roundtrip', snapshot_controls(tuple(before)) == before)


def verify(path, before=None):
    path = Path(path).resolve()
    bpy.ops.wm.open_mainfile(filepath=str(path))
    checks, details = {'file_reopened': True}, {}

    def check(name, value):
        checks[name] = bool(value)

    if before:
        after = protected_state()
        checks.update({key+'_preserved': before[key] == after[key] for key in before})
    check('all_eight_existing_scenes_retained', EXPECTED_SCENES == set(bpy.data.scenes.keys()))
    scene = bpy.data.scenes[overview.SCENE]
    saved_scene = bpy.context.window.scene.name
    bpy.context.window.scene = scene
    saved_frame = (scene.frame_current, scene.frame_subframe)
    saved_camera = scene.camera.name if scene.camera else None
    controls = snapshot_controls(('CTRL_ECS_OVERVIEW', 'ECS ENG | CTRL_ENGINE', 'CTRL_ENGINE', CONTROLLER))
    handlers_before = handler_state()
    ctrl = bpy.data.objects[CONTROLLER]
    owned = [obj for obj in bpy.data.objects if obj.get(OWNER)]
    try:
        check('phase2_collection_nested_in_existing_overview', COLLECTION in bpy.data.collections[overview.COLLECTION].children
              and bpy.data.collections[COLLECTION].get(OWNER))
        check('phase2_subgroups_organized', set(GROUPS) == set(bpy.data.collections[COLLECTION].children.keys()))
        check('phase2_objects_only_in_overview', bool(owned) and all(obj.name in scene.objects for obj in owned)
              and all(not any(obj.get(OWNER) for obj in other.objects) for other in bpy.data.scenes if other != scene))
        check('phase2_has_no_added_scene', not inventory()['scenes'])
        check('phase2_resources_owned_separately_from_phase1', all(not obj.get(overview.OWNER) for obj in owned)
              and all(obj.data is None or obj.data.get(OWNER) for obj in owned))
        check('phase2_clean_deterministic_names', all(canonical_owned_name(name)
              for names in inventory().values() for name in names))
        check('phase2_controls_present', all(key in ctrl for key in (*SWITCHES, 'ECS_FLOW_SPEED')))
        check('flow_speed_has_nonnegative_range', ctrl.id_properties_ui('ECS_FLOW_SPEED').as_dict()['min'] >= 0.)
        verify_geometry(scene, check, details)
        verify_visibility(scene, ctrl, check, details)
        verify_flow(scene, ctrl, check, details)
        verify_phase1_controls(scene, bpy.data.objects['CTRL_ECS_OVERVIEW'],
                               bpy.data.objects['ECS ENG | CTRL_ENGINE'], check, details)
        verify_ui(scene, check)
        drivers = native_drivers()
        check('native_phase2_drivers_valid_without_autoexec', bool(drivers)
              and all(fc.driver.is_valid and fc.driver.is_simple_expression for fc in drivers))
        check('phase2_drivers_use_only_own_controller_or_existing_scene', all(
              target.id == ctrl or target.id == scene for fc in drivers
              for variable in fc.driver.variables for target in variable.targets))
        check('no_new_actions_or_custom_script_handlers', not inventory()['actions'] and handler_state() == handlers_before)
        check('standalone_engine_controls_untouched', controller_state(bpy.data.objects['CTRL_ENGINE']) == controls['CTRL_ENGINE'])
        details['native_phase2_drivers'] = len(drivers)
        details['invalid_drivers'] = [(fc.id_data.name, fc.data_path, fc.driver.expression) for fc in drivers if not fc.driver.is_valid]
    finally:
        restore_controls(controls)
        scene.frame_set(saved_frame[0], subframe=saved_frame[1])
        scene.camera = bpy.data.objects.get(saved_camera) if saved_camera else None
        bpy.context.view_layer.update()
        bpy.context.window.scene = bpy.data.scenes[saved_scene]
    if before:
        after = protected_state()
        checks.update({key+'_preserved_after_functional_tests': before[key] == after[key] for key in before})
    verify_roundtrip(path, check, details)
    if before:
        after = protected_state()
        checks.update({key+'_preserved_after_roundtrip': before[key] == after[key] for key in before})
    report = {'passed': all(checks.values()), 'blender': bpy.app.version_string, 'file': str(path),
              'checks': checks, 'details': details, 'scenes': sorted(bpy.data.scenes.keys()), 'inventory': inventory()}
    (ROOT / 'reports').mkdir(exist_ok=True)
    (ROOT / 'reports' / 'ecs_phase2_verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    if not report['passed']:
        raise RuntimeError('ECS Phase 2 verification failed: '+', '.join(name for name, passed in checks.items() if not passed))
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', default=str(ROOT / 'models' / 'Boeing_737-300_Helios_Livery.blend'))
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    report = verify(args.source)
    print('PASS ECS Phase 2:', len(report['checks']), 'saved-file checks', flush=True)


if __name__ == '__main__':
    main()

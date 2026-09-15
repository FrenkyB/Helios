"""Saved-file preservation, asset reuse and presentation checks for ECS phase 1."""
from array import array
import hashlib
import json
import math
from pathlib import Path
import re
import sys

import bpy
from mathutils import Vector
from mathutils.geometry import interpolate_bezier
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import ecs_overview as overview
import cfm56_engine as engine
from verify_passenger_cabin import material_state, update_scenes

EXPECTED_SCENES = {
    'HEL-1 | Boeing 737-300', '02 | 737 Classic flight deck',
    '03 | Passenger cabin - 138 seats', '04 | Passenger cabin layout',
    '05 | Larnaca - Helios Flight 522', '06 | Pressurization panel',
    engine.SCENE, overview.SCENE,
}
RUNTIME_FIELDS = {
    'rna_type', 'session_uid', 'users', 'is_updated', 'is_updated_data',
    'is_updated_transform', 'is_evaluated', 'is_runtime_data', 'is_valid',
}


def plain_value(value):
    """Detach nested mathutils arrays so snapshots survive .blend reopening."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, set):
        return sorted(value)
    if hasattr(value, 'items'):
        return {str(key): plain_value(item) for key, item in value.items()}
    try:
        return [plain_value(item) for item in value]
    except TypeError:
        return str(value)


def scalar_state(data):
    """Persistent scalar RNA values, without load/evaluation bookkeeping."""
    result = {}
    for prop in data.bl_rna.properties:
        if prop.identifier in RUNTIME_FIELDS:
            continue
        if prop.type in {'BOOLEAN', 'INT', 'FLOAT', 'STRING', 'ENUM'}:
            try:
                value = getattr(data, prop.identifier)
                result[prop.identifier] = plain_value(value)
            except (AttributeError, TypeError, ValueError):
                pass
    return result


def properties(data):
    return sorted((str(key), str(value)) for key, value in data.items())


def pointers(data):
    result = {}
    for prop in data.bl_rna.properties:
        if prop.type == 'POINTER' and prop.identifier not in {'rna_type', 'id_data'}:
            value = getattr(data, prop.identifier, None)
            if isinstance(value, bpy.types.ID):
                result[prop.identifier] = (value.bl_rna.identifier, value.name)
    return result


def curve_state(fc):
    return {
        'path': fc.data_path, 'index': fc.array_index,
        'mute': fc.mute, 'extrapolation': fc.extrapolation,
        'keys': [scalar_state(key) for key in fc.keyframe_points],
        'samples': [list(point.co) for point in fc.sampled_points],
        'modifiers': [scalar_state(mod) for mod in fc.modifiers],
    }


def animation_state(data):
    animation = data.animation_data
    if not animation:
        return None
    drivers = []
    for fc in animation.drivers:
        drivers.append({
            'curve': curve_state(fc), 'type': fc.driver.type,
            'expression': fc.driver.expression, 'use_self': fc.driver.use_self,
            'variables': [(var.name, var.type,
                           [(scalar_state(target), pointers(target))
                            for target in var.targets])
                          for var in fc.driver.variables],
        })
    nla = []
    for track in animation.nla_tracks:
        nla.append((scalar_state(track), [(scalar_state(strip), pointers(strip))
                                         for strip in track.strips]))
    return {'drivers': drivers, 'action': animation.action.name if animation.action else None,
            'slot': animation.action_slot_handle, 'nla': nla,
            'settings': scalar_state(animation)}


def action_state(action):
    if hasattr(action, 'fcurves'):
        curves = [curve_state(fc) for fc in action.fcurves]
    else:
        curves = [(layer.name, strip.type, bag.slot_handle, curve_state(fc))
                  for layer in action.layers for strip in layer.strips
                  for bag in strip.channelbags for fc in bag.fcurves]
    return [properties(action), scalar_state(action), curves]


def world_state(world):
    nodes, links = [], []
    if world.node_tree:
        for node in world.node_tree.nodes:
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
                        link.to_node.name, link.to_socket.identifier)
                       for link in world.node_tree.links)
    return [tuple(world.color), nodes, links]


def geometry_fingerprint(data, include_materials=True):
    """Hash local geometry once; names and user counts do not describe shape."""
    digest = hashlib.sha256()

    def add(value):
        digest.update(repr(value).encode('utf-8'))

    def packed(items, property_name, width, kind='f'):
        values = array(kind, [0]) * (len(items) * width)
        if values:
            items.foreach_get(property_name, values)
            digest.update(values.tobytes())

    add(data.bl_rna.identifier)
    if isinstance(data, bpy.types.Mesh):
        add((len(data.vertices), len(data.edges), len(data.loops), len(data.polygons)))
        packed(data.vertices, 'co', 3)
        packed(data.edges, 'vertices', 2, 'i')
        packed(data.loops, 'vertex_index', 1, 'i')
        for poly in data.polygons:
            add((poly.loop_start, poly.loop_total, poly.material_index, poly.use_smooth))
        for layer in data.uv_layers:
            add(layer.name)
            packed(layer.data, 'uv', 2)
        for attr in data.attributes:
            # Position and UV attributes are covered above. Other supported
            # generic attributes include sharp edges, custom normals and colors.
            if attr.name == 'position' or attr.name in data.uv_layers:
                continue
            add((attr.name, attr.domain, attr.data_type))
            field = {'FLOAT': ('value', 1, 'f'), 'INT': ('value', 1, 'i'),
                     'BOOLEAN': ('value', 1, 'b'), 'FLOAT_VECTOR': ('vector', 3, 'f'),
                     'FLOAT_COLOR': ('color', 4, 'f'), 'BYTE_COLOR': ('color', 4, 'f'),
                     'FLOAT2': ('vector', 2, 'f')}.get(attr.data_type)
            if field:
                packed(attr.data, *field)
        if data.shape_keys:
            for block in data.shape_keys.key_blocks:
                add((block.name, block.value, block.relative_key.name))
                packed(block.data, 'co', 3)
    elif isinstance(data, bpy.types.Curve):
        add((data.dimensions, data.resolution_u, data.render_resolution_u,
             data.bevel_depth, data.bevel_resolution, data.extrude, data.fill_mode))
        if isinstance(data, bpy.types.TextCurve):
            add((data.body, data.size, data.align_x, data.align_y))
        for spline in data.splines:
            add((spline.type, spline.use_cyclic_u, spline.order_u,
                 spline.resolution_u, spline.use_endpoint_u))
            for point in spline.points:
                add((tuple(point.co), point.radius, point.tilt, point.weight_softbody))
            for point in spline.bezier_points:
                add((tuple(point.co), tuple(point.handle_left), tuple(point.handle_right),
                     point.handle_left_type, point.handle_right_type, point.radius, point.tilt))
    else:
        add(scalar_state(data))
    if include_materials and hasattr(data, 'materials'):
        add([material.name if material else None for material in data.materials])
    return digest.hexdigest()


def protected_state(raw=False):
    """Fingerprint every original asset, including standalone engine and panel."""
    update_scenes()
    result = {key: {} for key in ('objects', 'geometry', 'materials', 'scenes',
                                 'collections', 'actions')}
    for obj in bpy.data.objects:
        if obj.get(overview.OWNER):
            continue
        data = obj.data
        if data and not data.get(overview.OWNER):
            key = data.bl_rna.identifier + ' | ' + data.name
            if key not in result['geometry']:
                result['geometry'][key] = [geometry_fingerprint(data),
                    properties(data), animation_state(data)]
        result['objects'][obj.name] = [
            obj.type, data.name if data else None, scalar_state(obj),
            [list(row) for row in obj.matrix_world],
            [list(row) for row in obj.matrix_parent_inverse],
            obj.parent.name if obj.parent else None,
            sorted(col.name for col in obj.users_collection),
            [(slot.link, slot.material.name if slot.material else None)
             for slot in obj.material_slots],
            [(scalar_state(mod), pointers(mod)) for mod in obj.modifiers],
            [(scalar_state(con), pointers(con)) for con in obj.constraints],
            properties(obj), animation_state(obj),
        ]
    for material in bpy.data.materials:
        if not material.get(overview.OWNER):
            result['materials'][material.name] = [material_state(material),
                scalar_state(material), properties(material), animation_state(material),
                animation_state(material.node_tree) if material.node_tree else None]
    for collection in bpy.data.collections:
        if not collection.get(overview.OWNER):
            result['collections'][collection.name] = [scalar_state(collection),
                properties(collection), sorted(obj.name for obj in collection.objects),
                sorted(col.name for col in collection.children)]
    for scene in bpy.data.scenes:
        if scene.get(overview.OWNER):
            continue
        world = scene.world
        result['scenes'][scene.name] = [
            sorted(obj.name for obj in scene.objects),
            sorted(col.name for col in scene.collection.children),
            scene.camera.name if scene.camera else None,
            scalar_state(scene.render), scalar_state(scene.view_settings),
            scalar_state(scene.unit_settings), scalar_state(scene.cycles),
            scene.frame_current, scene.frame_subframe, scene.frame_start, scene.frame_end,
            properties(scene), animation_state(scene),
            [world.name, scalar_state(world), properties(world), world_state(world),
             animation_state(world), animation_state(world.node_tree) if world.node_tree else None]
            if world else None,
        ]
    for action in bpy.data.actions:
        if not action.get(overview.OWNER):
            result['actions'][action.name] = action_state(action)
    if raw:
        return result
    return {key: hashlib.sha256(json.dumps(value, sort_keys=True,
                    default=str).encode('utf-8')).hexdigest()
            for key, value in result.items()}


def inventory():
    return {name: sorted(block.name for block in getattr(bpy.data, name)
                         if block.get(overview.OWNER))
            for name in ('scenes', 'collections', 'objects', 'meshes', 'curves',
                         'materials', 'cameras', 'lights', 'worlds', 'actions', 'texts')}


def canonical_owned_name(block):
    """Allow inherited source suffixes; reject new overview duplicate suffixes."""
    if not re.search(r'\.\d{3}$', block.name):
        return True
    if isinstance(block, bpy.types.Object):
        source = block.get('ecs_source_object')
        return bool(source) and block.name in {
            prefix + source for prefix in ('ECS AIR | ', 'ECS WIRE | ', 'ECS ENG | ')}
    if isinstance(block, (bpy.types.Mesh, bpy.types.Curve)):
        source = block.get('ecs_source_data')
        return bool(source) and block.name in {
            prefix + source for prefix in ('ECS AIR DATA | ', 'ECS ENG DATA | ')}
    if isinstance(block, bpy.types.Material):
        source = block.get('ecs_source_material')
        return bool(source) and block.name == 'ECS ENG MAT | ' + source
    return False


def controller_state(obj):
    """IDPropertyArray values otherwise remain aliases when a picker changes RGB."""
    return {key: plain_value(value) for key, value in obj.items()}


def native_drivers():
    """Include shader animation: RGB sockets live on node trees, not objects."""
    ids = set()
    for category in ('objects', 'meshes', 'curves', 'materials', 'worlds', 'scenes'):
        for block in getattr(bpy.data, category):
            if block.get(overview.OWNER):
                ids.add(block)
                tree = getattr(block, 'node_tree', None)
                if tree:
                    ids.add(tree)
    return [fc for block in ids if block.animation_data
            for fc in block.animation_data.drivers]


def color_state(material, depsgraph):
    evaluated = material.evaluated_get(depsgraph)
    tree = material.node_tree.evaluated_get(depsgraph)
    bsdf = tree.nodes.get('Principled BSDF')
    return {'diffuse': list(evaluated.diffuse_color[:3]),
            'base': list(bsdf.inputs['Base Color'].default_value[:3]),
            'emission': list(bsdf.inputs['Emission Color'].default_value[:3])}


def color_matches(values, expected):
    return all(len(value) == len(expected) and all(abs(a-b) < 1e-5
               for a, b in zip(value, expected)) for value in values.values())


def evaluated_surface(obj, depsgraph):
    """World-space surface, including the saved asset's bevels/modifiers."""
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    try:
        vertices = [evaluated.matrix_world @ vertex.co for vertex in mesh.vertices]
        polygons = [tuple(poly.vertices) for poly in mesh.polygons]
    finally:
        evaluated.to_mesh_clear()
    return {'tree': BVHTree.FromPolygons(vertices, polygons, all_triangles=False),
            'minimum_z': min(vertex.z for vertex in vertices),
            'maximum_z': max(vertex.z for vertex in vertices)}


def point_inside_surface(surface, point):
    """Odd ray intersections classify a closed mesh without normal assumptions."""
    tree = surface['tree']
    nearest = tree.find_nearest(point)
    if nearest[0] is not None and nearest[3] < 2e-5:
        return True
    direction = Vector((.371, .529, .763)).normalized()
    origin = point.copy()
    intersections = 0
    for _ in range(64):
        location, _normal, _index, _distance = tree.ray_cast(origin, direction, 100.)
        if location is None:
            return intersections % 2 == 1
        intersections += 1
        origin = location+direction*1e-4
    return False


def vertical_surface_span(surface, point):
    """First intersections from above/below measure the actual local wing skin."""
    tree = surface['tree']
    lower = tree.ray_cast(Vector((point.x, point.y, surface['minimum_z']-1.)), Vector((0, 0, 1)), 100.)[0]
    upper = tree.ray_cast(Vector((point.x, point.y, surface['maximum_z']+1.)), Vector((0, 0, -1)), 100.)[0]
    return (lower.z, upper.z) if lower is not None and upper is not None else None


def verify_control_round_trip(path, checks, details):
    """Exercise nondefault saved settings in a disposable copy, then reopen input."""
    path = Path(path).resolve()
    temporary = ROOT / 'reports' / 'ECS_Overview_control_roundtrip.blend'
    ctrl = bpy.data.objects['CTRL_ECS_OVERVIEW']
    original = controller_state(ctrl)
    current_scene = bpy.context.window.scene.name
    thickness, color = .011, (.31, .74, .08)
    try:
        bpy.context.window.scene = bpy.data.scenes[overview.SCENE]
        ctrl['WIREFRAME_THICKNESS'] = thickness
        ctrl['WIREFRAME_COLOR'] = color
        ctrl['SHOW_WIREFRAME'] = True
        ctrl.update_tag()
        bpy.context.view_layer.update()
        bpy.ops.wm.save_as_mainfile(filepath=str(temporary), copy=True)
        bpy.ops.wm.open_mainfile(filepath=str(temporary))
        bpy.context.window.scene = bpy.data.scenes[overview.SCENE]
        bpy.context.view_layer.update()
        ctrl = bpy.data.objects['CTRL_ECS_OVERVIEW']
        depsgraph = bpy.context.evaluated_depsgraph_get()
        values = color_state(bpy.data.materials['ECS | Structural wire'], depsgraph)
        wire = [obj for obj in bpy.data.objects if obj.name.startswith('ECS WIRE | ')]
        checks['wire_settings_save_reopen'] = bool(
            abs(ctrl['WIREFRAME_THICKNESS']-thickness) < 1e-6
            and color_matches({'control': ctrl['WIREFRAME_COLOR']}, color))
        checks['wire_thickness_driver_after_reopen'] = bool(wire) and all(
            abs(mod.thickness-thickness) < 1e-6
            for obj in wire for mod in obj.evaluated_get(depsgraph).modifiers
            if mod.type == 'WIREFRAME')
        checks['wire_color_drivers_after_reopen'] = color_matches(values, color)
        details['saved_control_probe'] = {'thickness_m': thickness,
                                         'color_rgb': list(color), 'evaluated': values}
    finally:
        bpy.ops.wm.open_mainfile(filepath=str(path))
        bpy.context.window.scene = bpy.data.scenes[current_scene]
    checks['saved_default_controls_restored_after_probe'] = (
        controller_state(bpy.data.objects['CTRL_ECS_OVERVIEW']) == original)


def verify_installed_bleed(scene, template, engine_ctrl, check, details):
    """Verify whole installed bleed systems are exact engine-local Y mirrors."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    bleed_sources = set(bpy.data.collections['ENGINE_BLEED'].objects)
    old = [obj for obj in template.objects if obj.get('ecs_source_object') in
           {source.name for source in bleed_sources}]
    check('shared_bleed_template_suppressed', len(old) == len(bleed_sources) and all(
          obj.get('ecs_installed_replaced') and obj.hide_render and obj.hide_viewport
          and (not obj.animation_data or not any(
              fc.data_path in ('hide_render', 'hide_viewport')
              for fc in obj.animation_data.drivers)) for obj in old))
    # Build an evaluated surface of the aft external core cowl, in template
    # coordinates. Nearest distances catch overshooting Bezier handles as well
    # as an apparently safe sequence of control points.
    vertices, polygons = [], []
    for obj in template.objects:
        if not obj.get('ecs_source_object', '').startswith('CORE_COWLING_'):
            continue
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        try:
            offset = len(vertices)
            vertices.extend(obj.matrix_world @ vertex.co for vertex in mesh.vertices)
            polygons.extend(tuple(offset+index for index in poly.vertices) for poly in mesh.polygons)
        finally:
            evaluated.to_mesh_clear()
    surface = BVHTree.FromPolygons(vertices, polygons, all_triangles=False)
    route_details = {}
    hardware_sources = {source for source in bleed_sources if source.name not in
                        {'BLEED_OUTLET_STUB', 'BLEED_OUTLET_FLANGE', 'BLEED_OUTLET_TO_AIRCRAFT'}}
    expected_names = {'ECS BLEED | '+side+' '+role for side in ('LEFT', 'RIGHT')
                      for role in ('ROOT', 'ROUTE', 'FLANGE', 'OUTLET', 'PYLON ENTRY')}
    expected_names.update('ECS BLEED | '+side+' | '+source.name
                          for side in ('LEFT', 'RIGHT') for source in hardware_sources)
    installed = [obj for obj in scene.objects if obj.name.startswith('ECS BLEED | ')]
    check('two_complete_installed_bleed_systems_no_duplicates', {obj.name for obj in installed} == expected_names)
    template_by_source = {obj.get('ecs_source_object'): obj for obj in old}
    hardware = {}
    directions = {}
    for side, inward in (('LEFT', 1.), ('RIGHT', -1.)):
        parent = bpy.data.objects['ENGINE_'+side+'_OVERVIEW']
        root = bpy.data.objects['ECS BLEED | '+side+' ROOT']
        pipe = bpy.data.objects['ECS BLEED | '+side+' ROUTE']
        flange = bpy.data.objects['ECS BLEED | '+side+' FLANGE']
        endpoint = bpy.data.objects['ECS BLEED | '+side+' OUTLET']
        entry = bpy.data.objects['ECS BLEED | '+side+' PYLON ENTRY']
        suffix = 'L' if side == 'LEFT' else 'R'
        pylon_surface = evaluated_surface(bpy.data.objects['ECS AIR | Engine pylon_'+suffix], depsgraph)
        wing_surface = evaluated_surface(bpy.data.objects['ECS AIR | Wing main box_'+suffix], depsgraph)
        check(side+'_bleed_root_installed_mirror_transform', root.parent == parent
              and root.get(overview.OWNER) and all(abs(value) < 1e-6 for value in root.location)
              and all(abs(value) < 1e-6 for value in root.rotation_euler)
              and all(abs(actual-expected) < 1e-6 for actual, expected in zip(
                  root.scale, (1., -1. if side == 'LEFT' else 1., 1.))))
        hardware[side] = {source: bpy.data.objects['ECS BLEED | '+side+' | '+source.name]
                          for source in hardware_sources}
        check(side+'_bleed_hardware_reuses_detached_template_geometry', all(
              obj.get(overview.OWNER) and obj.get('ecs_source_object') == source.name
              and obj.data == template_by_source[source.name].data
              and (not obj.data or (obj.data != source.data and obj.data.get(overview.OWNER)))
              for source, obj in hardware[side].items()))
        check(side+'_bleed_materials_remain_overview_owned', all(
              slot.material and slot.material.get(overview.OWNER)
              for obj in hardware[side].values() for slot in obj.material_slots))
        check(side+'_bleed_hardware_hierarchy_preserved', all(
              obj.parent == hardware[side].get(source.parent, root)
              and obj.matrix_parent_inverse == source.matrix_parent_inverse
              for source, obj in hardware[side].items()))
        check(side+'_bleed_driver_targets_private', all(target.id == engine_ctrl
              for obj in hardware[side].values() if obj.animation_data
              for fc in obj.animation_data.drivers for var in fc.driver.variables for target in var.targets))
        check(side+'_installed_bleed_owned_and_parented', all(
              obj.get(overview.OWNER) and obj.parent == root and obj.get('ecs_installed_side') == side
              for obj in (pipe, flange, endpoint, entry)))
        check(side+'_installed_bleed_open_route', pipe.type == 'CURVE'
              and len(pipe.data.splines) == 1 and pipe.data.splines[0].type == 'BEZIER'
              and not pipe.data.splines[0].use_cyclic_u and not pipe.data.use_fill_caps
              and .035 <= pipe.data.bevel_depth <= .06)
        points = list(pipe.data.splines[0].bezier_points)
        first, last = points[0], points[-1]
        pipe_in_engine = parent.matrix_world.inverted() @ pipe.matrix_world
        start = pipe_in_engine @ first.co
        end = pipe.matrix_world @ last.co
        source_stub = bpy.data.objects['BLEED_OUTLET_STUB']
        source_point = source_stub.data.splines[0].bezier_points[0].co
        source_connection = source_stub.matrix_world @ source_point
        if side == 'LEFT':
            source_connection.y *= -1
        start_direction = (pipe_in_engine.to_3x3() @ (first.handle_right-first.co)).normalized()
        check(side+'_installed_bleed_attached_to_source_valve',
              (start-source_connection).length < 1e-5 and start_direction.x > .999
              and abs(pipe.data.bevel_depth-source_stub.data.bevel_depth) < 1e-6)
        axis = (endpoint.matrix_world.to_3x3() @ Vector((0, 0, 1))).normalized()
        flange_axis = (flange.matrix_world.to_3x3() @ Vector((0, 0, 1))).normalized()
        tangent = (pipe.matrix_world.to_3x3() @ (last.co-last.handle_left)).normalized()
        directions[side] = axis
        check(side+'_internal_outlet_axis_follows_route_aft', axis.x > .8
              and axis.dot(tangent) > .999 and axis.dot(flange_axis) > .999)
        check(side+'_internal_outlet_inside_actual_wing', point_inside_surface(wing_surface, end)
              and end.y*parent.matrix_world.translation.y > 0.)
        check(side+'_outlet_route_and_flange_connected',
              (end-endpoint.matrix_world.translation).length < 1e-5
              and (end-flange.matrix_world.translation).length < 1e-5)
        check(side+'_outlet_flange_has_open_bore', flange.type == 'MESH'
              and all(math.hypot(poly.center.x, poly.center.y) > .035 for poly in flange.data.polygons)
              and all(math.hypot(vertex.co.x, vertex.co.y) > .035 for vertex in flange.data.vertices))
        check(side+'_route_has_continuous_tangents', all(
              (point.co-point.handle_left).normalized().dot(
                  (point.handle_right-point.co).normalized()) > .999
              for point in points[1:-1]))
        samples = [pipe_in_engine @ co for first_point, last_point in zip(points, points[1:])
                   for co in interpolate_bezier(first_point.co, first_point.handle_right,
                       last_point.handle_left, last_point.co, 32)]
        distances = [surface.find_nearest(point)[3] for point in samples]
        clearance = min(distances)-pipe.data.bevel_depth
        check(side+'_route_clears_evaluated_core_cowl', clearance > .015)
        check(side+'_route_does_not_cross_aircraft_centerline', all(
              (parent.matrix_world @ point).y*parent.matrix_world.translation.y > 0 for point in samples))
        entry_index = pipe.get('ecs_pylon_entry_index', -1)
        check(side+'_pylon_entry_is_a_route_control_point', isinstance(entry_index, int)
              and 0 < entry_index < len(points)-1)
        if not 0 < entry_index < len(points)-1:
            raise RuntimeError('Missing valid pylon entry index on '+pipe.name)
        entry_world = pipe.matrix_world @ points[entry_index].co
        check(side+'_pylon_entry_marker_is_nonrendered_and_connected', entry.hide_render
              and entry.type == 'EMPTY' and (entry.matrix_world.translation-entry_world).length < 1e-5)
        check(side+'_external_route_enters_actual_pylon_inboard', point_inside_surface(pylon_surface, entry_world)
              and abs(entry_world.y) < abs(parent.matrix_world.translation.y)
              and not point_inside_surface(pylon_surface, pipe.matrix_world @ first.co))
        # Sample complete circular tube sections, not just a safe-looking
        # centerline. The aft continuation must fit inside the actual pylon or
        # wing solid, including the transition where those solids overlap.
        union_samples = []
        terminal_ring = []
        for segment in range(entry_index, len(points)-1):
            a, b = points[segment], points[segment+1]
            positions = interpolate_bezier(a.co, a.handle_right, b.handle_left, b.co, 24)
            for number, position in enumerate(positions):
                t = number/(len(positions)-1)
                derivative = 3*(1-t)**2*(a.handle_right-a.co)+6*(1-t)*t*(b.handle_left-a.handle_right)+3*t*t*(b.co-b.handle_left)
                direction = (pipe.matrix_world.to_3x3() @ derivative).normalized()
                cross = direction.cross(Vector((0, 0, 1)))
                if cross.length < .1:
                    cross = direction.cross(Vector((1, 0, 0)))
                cross.normalize()
                other = direction.cross(cross).normalized()
                center = pipe.matrix_world @ position
                ring = [center+pipe.data.bevel_depth*(cross*math.cos(index*math.tau/24)+other*math.sin(index*math.tau/24))
                        for index in range(24)]
                union_samples.extend([center, *ring])
                if segment == len(points)-2 and number == len(positions)-1:
                    terminal_ring = ring
        contained = [point_inside_surface(pylon_surface, point) or point_inside_surface(wing_surface, point)
                     for point in union_samples]
        check(side+'_entire_internal_tube_fits_pylon_wing_union', bool(contained) and all(contained))
        check(side+'_terminal_tube_cross_section_inside_wing', bool(terminal_ring)
              and all(point_inside_surface(wing_surface, point) for point in terminal_ring))
        # Upper-skin rays apply wherever there is wing above the routing. The
        # engine-side portion forward of the wing footprint is allowed; its
        # pylon entry and final internal terminal are checked separately above.
        vertex_count, covered_count, internal_vertices = 0, 0, []
        upper_margins, flange_inside = [], []
        for obj in (pipe, flange):
            evaluated = obj.evaluated_get(depsgraph)
            mesh = evaluated.to_mesh()
            try:
                for vertex in mesh.vertices:
                    point = evaluated.matrix_world @ vertex.co
                    vertex_count += 1
                    span = vertical_surface_span(wing_surface, point)
                    if span:
                        covered_count += 1
                        upper_margins.append(span[1]-point.z)
                    if point.x > entry_world.x+pipe.data.bevel_depth:
                        internal_vertices.append(point_inside_surface(pylon_surface, point)
                                                 or point_inside_surface(wing_surface, point))
                    if obj == flange:
                        flange_inside.append(point_inside_surface(wing_surface, point))
            finally:
                evaluated.to_mesh_clear()
        check(side+'_evaluated_tube_stays_below_upper_wing_skin', bool(upper_margins)
              and min(upper_margins) > .001)
        check(side+'_evaluated_internal_tube_stays_inside_structure', bool(internal_vertices)
              and all(internal_vertices))
        check(side+'_terminal_flange_inside_actual_wing', bool(flange_inside) and all(flange_inside))
        route_details[side] = {'source_connection_local': list(start),
            'outlet_world': list(end), 'outlet_direction_world': list(axis),
            'pylon_entry_world': list(entry_world), 'pylon_entry_control_index': entry_index,
            'sampled_points': len(samples), 'minimum_core_cowl_clearance_m': clearance,
            'internal_cross_section_samples': len(union_samples),
            'internal_cross_section_samples_outside_structure': sum(not value for value in contained),
            'evaluated_routing_vertices': vertex_count, 'vertices_below_wing_footprint': covered_count,
            'minimum_upper_wing_skin_clearance_m': min(upper_margins) if upper_margins else None}
    check('installed_terminal_axes_are_mirrored', (directions['LEFT']-Vector((
          directions['RIGHT'].x, -directions['RIGHT'].y, directions['RIGHT'].z))).length < 1e-5)
    left_pipe = bpy.data.objects['ECS BLEED | LEFT ROUTE']
    right_pipe = bpy.data.objects['ECS BLEED | RIGHT ROUTE']
    left_matrix = bpy.data.objects['ENGINE_LEFT_OVERVIEW'].matrix_world.inverted() @ left_pipe.matrix_world
    right_matrix = bpy.data.objects['ENGINE_RIGHT_OVERVIEW'].matrix_world.inverted() @ right_pipe.matrix_world
    left_points = left_pipe.data.splines[0].bezier_points
    right_points = right_pipe.data.splines[0].bezier_points

    def mirror_matches(left, right):
        return (left-Vector((right.x, -right.y, right.z))).length < 3e-5

    check('final_routes_are_exact_mirrors', len(left_points) == len(right_points)
          and abs(left_pipe.data.bevel_depth-right_pipe.data.bevel_depth) < 1e-6
          and all(mirror_matches(left_matrix @ getattr(left, attr), right_matrix @ getattr(right, attr))
                  for left, right in zip(left_points, right_points)
                  for attr in ('co', 'handle_left', 'handle_right')))
    valve_before = engine_ctrl['BLEED_VALVE_OPEN']
    pose_results = []
    try:
        for opening in (0., .75):
            engine_ctrl['BLEED_VALVE_OPEN'] = opening
            engine_ctrl.update_tag()
            bpy.context.view_layer.update()
            depsgraph = bpy.context.evaluated_depsgraph_get()
            pair_results = {}
            pairs = {source.name: [hardware[side][source] for side in ('LEFT', 'RIGHT')]
                     for source in hardware_sources if source.type in {'MESH', 'CURVE'}}
            pairs.update({role: [bpy.data.objects['ECS BLEED | '+side+' '+role]
                                for side in ('LEFT', 'RIGHT')] for role in ('ROUTE', 'FLANGE')})
            for label, originals in pairs.items():
                objects = [obj.evaluated_get(depsgraph) for obj in originals]
                matrices = [bpy.data.objects['ENGINE_'+side+'_OVERVIEW'].matrix_world.inverted() @ obj.matrix_world
                            for side, obj in zip(('LEFT', 'RIGHT'), objects)]
                meshes = [obj.to_mesh() for obj in objects]
                try:
                    pair_results[label] = len(meshes[0].vertices) == len(meshes[1].vertices) and all(
                        mirror_matches(matrices[0] @ left.co, matrices[1] @ right.co)
                        for left, right in zip(meshes[0].vertices, meshes[1].vertices))
                finally:
                    for obj in objects:
                        obj.to_mesh_clear()
            check('all_installed_bleed_hardware_mirrored_valve_'+str(opening),
                  bool(pair_results) and all(pair_results.values()))
            for side in ('LEFT', 'RIGHT'):
                pivot = hardware[side][bpy.data.objects['BLEED_VALVE_PIVOT']].evaluated_get(depsgraph)
                check(side+'_installed_valve_native_behavior_'+str(opening),
                      abs(pivot.rotation_euler.z-opening*math.pi/2) < 1e-5)
            pose_results.append({'valve_open': opening, 'mirrored_hardware': pair_results})
    finally:
        engine_ctrl['BLEED_VALVE_OPEN'] = valve_before
        engine_ctrl.update_tag()
        bpy.context.view_layer.update()
    for enabled in (False, True):
        engine_ctrl['SHOW_INTERNALS'] = enabled
        engine_ctrl.update_tag()
        bpy.context.view_layer.update()
        depsgraph = bpy.context.evaluated_depsgraph_get()
        check('installed_bleed_visibility_'+str(enabled), all(
              obj.evaluated_get(depsgraph).hide_render == (not enabled)
              for obj in installed if obj.type != 'EMPTY'))
    cutaway_before = engine_ctrl['CUTAWAY_MODE']
    try:
        for cutaway in (True, False):
            engine_ctrl['CUTAWAY_MODE'] = cutaway
            engine_ctrl.update_tag()
            bpy.context.view_layer.update()
            depsgraph = bpy.context.evaluated_depsgraph_get()
            check('installed_valve_cutaway_behavior_'+str(cutaway), all(
                  obj.evaluated_get(depsgraph).hide_render == (
                      cutaway and source.name in {'BLEED_VALVE_HOUSING_Q2', 'BLEED_VALVE_HOUSING_Q3'})
                  for side in ('LEFT', 'RIGHT') for source, obj in hardware[side].items()
                  if obj.type in {'MESH', 'CURVE'}))
    finally:
        engine_ctrl['CUTAWAY_MODE'] = cutaway_before
        engine_ctrl.update_tag()
        bpy.context.view_layer.update()
    details['installed_bleed'] = route_details
    details['mirrored_bleed_hardware_poses'] = pose_results
    details['installed_bleed_objects'] = len(installed)


def verify(path, before=None):
    bpy.ops.wm.open_mainfile(filepath=str(path))
    checks = {'file_reopened': True}
    details = {}

    def check(name, value):
        checks[name] = bool(value)

    if before:
        after = protected_state()
        checks.update({key + '_preserved': before[key] == after[key] for key in before})
    check('existing_and_overview_scenes_present', EXPECTED_SCENES <= set(bpy.data.scenes.keys()))
    check('one_overview_scene', sum('ECS_OVERVIEW' in scene.name for scene in bpy.data.scenes) == 1)
    scene = bpy.data.scenes[overview.SCENE]
    previous_scene = bpy.context.window.scene
    bpy.context.window.scene = scene
    root = bpy.data.collections[overview.COLLECTION]
    template = bpy.data.collections[overview.TEMPLATE]
    owned = [obj for obj in bpy.data.objects if obj.get(overview.OWNER)]
    ctrl = bpy.data.objects['CTRL_ECS_OVERVIEW']
    engine_ctrl = bpy.data.objects['ECS ENG | CTRL_ENGINE']
    original_ctrl = bpy.data.objects['CTRL_ENGINE']
    controls_before = {obj: controller_state(obj) for obj in (ctrl, engine_ctrl, original_ctrl)}
    saved_frame = (scene.frame_current, scene.frame_subframe)
    saved_camera = scene.camera
    shape_cache = {}

    def shape(data):
        if data not in shape_cache:
            shape_cache[data] = geometry_fingerprint(data, include_materials=False)
        return shape_cache[data]

    def update():
        ctrl.update_tag()
        engine_ctrl.update_tag()
        bpy.context.view_layer.update()

    try:
        check('owned_scene_and_collections', scene.get(overview.OWNER) and root.get(overview.OWNER)
              and template.get(overview.OWNER))
        check('clean_root_collection', list(scene.collection.children) == [root]
              and len(scene.collection.objects) == 0)
        check('required_groups', set(overview.GROUPS) == {col.name for col in root.children})
        check('template_only_instanced', all(template not in list(s.collection.children_recursive)
                                            for s in bpy.data.scenes))
        check('no_suffixed_owned_ids', all(canonical_owned_name(block)
              for category in inventory() for block in getattr(bpy.data, category)
              if block.get(overview.OWNER)))
        check('all_scene_content_owned', all(obj.get(overview.OWNER) for obj in scene.objects))
        check('overview_not_linked_into_original_scenes', all(
            not any(obj.get(overview.OWNER) for obj in s.objects)
            for s in bpy.data.scenes if s != scene))
        instances = [obj for obj in scene.objects if obj.instance_type == 'COLLECTION'
                     and obj.instance_collection == template]
        check('two_reused_engines', {obj.name for obj in instances}
              == {'ENGINE_LEFT_OVERVIEW', 'ENGINE_RIGHT_OVERVIEW'} and len(instances) == 2)
        for name, y in [('ENGINE_LEFT_OVERVIEW', -4.83), ('ENGINE_RIGHT_OVERVIEW', 4.83)]:
            obj = bpy.data.objects[name]
            check(name + '_mount', all(abs(a-b) < 1e-5 for a, b in zip(obj.matrix_world.translation,
                                                                      (11., y, 1.60))))
            check(name + '_unit_scale_orientation', all(abs(a-1.) < 1e-5 for a in obj.scale)
                  and all(abs(a) < 1e-5 for a in obj.rotation_euler))
        clones = list(template.all_objects)
        provenance = {obj: bpy.data.objects.get(obj.get('ecs_source_object', '')) for obj in clones}
        check('engine_object_provenance', bool(clones) and all(provenance.values()))
        expected_engine_sources = {obj for name in ('ENGINE_STATIC', 'ENGINE_NACELLE',
            'ENGINE_N1', 'ENGINE_N2', 'ENGINE_COMBUSTOR', 'ENGINE_BLEED', 'ENGINE_CONTROLS')
            for obj in bpy.data.collections[name].objects}
        check('complete_physical_engine_reused', set(provenance.values()) == expected_engine_sources
              and len(clones) == len(expected_engine_sources))
        clone_map = {source: obj for obj, source in provenance.items() if source}
        check('engine_parent_hierarchy_preserved', all(source and obj.parent == clone_map.get(source.parent)
              and obj.matrix_parent_inverse == source.matrix_parent_inverse
              for obj, source in provenance.items()))
        check('engine_shape_copied_exactly', all(source and obj.data != source.data
              and obj.data.get(overview.OWNER) and obj.data.get('ecs_source_data') == source.data.name
              and shape(obj.data) == shape(source.data)
              for obj, source in provenance.items() if obj.data))
        data_map = {}
        for obj, source in provenance.items():
            if obj.data and source:
                data_map.setdefault(source.data, set()).add(obj.data)
        check('template_preserves_linked_geometry', all(len(items) == 1 for items in data_map.values()))
        check('template_only_overview_owned', all(obj.get(overview.OWNER) and not obj.get(engine.OWNER)
                                                for obj in clones))
        excluded = {obj for name in ('ENGINE_AIRFLOW', 'ENGINE_LABELS', 'ENGINE_CAMERAS', 'ENGINE_LIGHTS')
                    for obj in bpy.data.collections[name].all_objects}
        check('engine_presentation_exclusions', all(source not in excluded for source in provenance.values())
              and all(obj.type not in {'LIGHT', 'CAMERA', 'FONT'} for obj in clones))
        check('engine_materials_detached', all(mat.get(overview.OWNER) and not mat.get(engine.OWNER)
              for obj in clones if obj.data and hasattr(obj.data, 'materials')
              for mat in obj.data.materials if mat))
        copied_materials = {mat for obj in clones if obj.data and hasattr(obj.data, 'materials')
                            for mat in obj.data.materials if mat}
        check('engine_materials_reuse_original_appearance', all(
            mat.get('ecs_source_material') in bpy.data.materials
            and mat != bpy.data.materials[mat['ecs_source_material']]
            and mat.node_tree != bpy.data.materials[mat['ecs_source_material']].node_tree
            and material_state(mat) == material_state(bpy.data.materials[mat['ecs_source_material']])
            for mat in copied_materials))
        check('complete_engine_presentation_defaults', not engine_ctrl['CUTAWAY_MODE']
              and not engine_ctrl['SHOW_AIRFLOW'] and not engine_ctrl['SHOW_LABELS'])
        aircraft = [obj for obj in owned if obj.name.startswith('ECS AIR | ')]
        wire = [obj for obj in owned if obj.name.startswith('ECS WIRE | ')]
        check('one_aircraft_presentation_root', sum(obj.name == 'AIRCRAFT_OVERVIEW_ROOT' for obj in owned) == 1
              and bpy.data.objects['AIRCRAFT_OVERVIEW_ROOT'].parent == ctrl)
        def aircraft_reused(obj):
            source = bpy.data.objects.get(obj.get('ecs_source_object', ''))
            if not source or not source.data:
                return False
            if obj.data == source.data:
                return not obj.data.get(overview.OWNER)
            if not obj.data.get(overview.OWNER) or obj.data.get('ecs_source_data') != source.data.name:
                return False
            if source.name.startswith('Engine pylon_'):
                return bool(obj.get('ecs_adaptation'))
            return not source.material_slots and shape(obj.data) == shape(source.data)

        check('aircraft_reuses_original_geometry', bool(aircraft) and all(
            aircraft_reused(obj) for obj in aircraft if obj.data))
        pylons = [obj for obj in aircraft if obj.get('ecs_source_object', '').startswith('Engine pylon_')]
        pylon_ok = len(pylons) == 2
        for obj in pylons:
            source = bpy.data.objects[obj['ecs_source_object']]
            pylon_ok &= len(obj.data.vertices) == len(source.data.vertices)
            pylon_ok &= [tuple(poly.vertices) for poly in obj.data.polygons] == [tuple(poly.vertices) for poly in source.data.polygons]
            for actual, original in zip(obj.data.vertices, source.data.vertices):
                pylon_ok &= abs(actual.co.x - original.co.x) < 1e-6 and abs(actual.co.y - original.co.y) < 1e-6
                expected_z = {0: 2.40, 5: 2.40, 4: 1.97, 9: 1.97}.get(actual.index, original.co.z)
                pylon_ok &= abs(actual.co.z - expected_z) < 1e-5
        check('pylons_only_adjusted_at_documented_lower_attachment', pylon_ok)
        check('private_aircraft_material_overrides', all(slot.link == 'OBJECT' and slot.material
              and slot.material.get(overview.OWNER) for obj in aircraft + wire
              for slot in obj.material_slots))
        legacy = bpy.data.collections['05_Engines_CFM56_3']
        excluded_legacy = {obj.name for obj in legacy.all_objects if not obj.name.startswith('Engine pylon_')}
        check('no_legacy_engine_geometry_copied', not any(obj.get('ecs_source_object') in excluded_legacy
                                                        for obj in aircraft + wire))
        check('both_original_pylons_reused', len({obj.get('ecs_source_object') for obj in aircraft
              if obj.get('ecs_source_object', '').startswith('Engine pylon_')}) == 2)
        check('shell_wireframe_controls_present', 'SHOW_SHELL' in ctrl and 'SHOW_WIREFRAME' in ctrl)
        fuselage = next(obj for obj in aircraft if obj.get('ecs_source_object') == 'Fuselage | continuous quad loft')
        check('fuselage_uses_transparent_shell', any(slot.material and slot.material.use_nodes
              and any(node.bl_idname == 'ShaderNodeBsdfTransparent' for node in slot.material.node_tree.nodes)
              for slot in fuselage.material_slots))
        check('wireframe_non_destructive', bool(wire) and all(
            obj.data == bpy.data.objects[obj['ecs_source_object']].data
            and any(mod.type == 'WIREFRAME' for mod in obj.modifiers) for obj in wire))
        check('wireframe_appearance_controls_present', all(key in ctrl for key in
              ('WIREFRAME_THICKNESS', 'WIREFRAME_COLOR')))
        thickness_ui = ctrl.id_properties_ui('WIREFRAME_THICKNESS').as_dict()
        color_ui = ctrl.id_properties_ui('WIREFRAME_COLOR').as_dict()
        check('wireframe_controls_have_safe_ranges_and_color_picker',
              abs(thickness_ui['min']-.001) < 1e-6
              and abs(thickness_ui['max']-.025) < 1e-6
              and color_ui.get('subtype') == 'COLOR')
        wire_material = bpy.data.materials['ECS | Structural wire']
        check('wireframe_color_material_is_private', wire_material.get(overview.OWNER)
              and all(slot.material == wire_material for obj in wire for slot in obj.material_slots)
              and not any(slot.material == wire_material for obj in bpy.data.objects
                          if not obj.get(overview.OWNER) for slot in obj.material_slots))
        check('wireframe_thickness_all_modifiers_driven', len(wire) == 6 and all(
              any(fc.data_path == mod.path_from_id('thickness')
                  for fc in obj.animation_data.drivers)
              for obj in wire for mod in obj.modifiers if mod.type == 'WIREFRAME'))
        ctrl['SHOW_WIREFRAME'] = True
        wire_shapes = []
        thickness_samples = []
        for thickness in (.002, .018):
            ctrl['WIREFRAME_THICKNESS'] = thickness
            update()
            depsgraph = bpy.context.evaluated_depsgraph_get()
            sampled, meshes = {}, {}
            for obj in wire:
                evaluated = obj.evaluated_get(depsgraph)
                sampled[obj.name] = [mod.thickness for mod in evaluated.modifiers
                                     if mod.type == 'WIREFRAME']
                mesh = evaluated.to_mesh()
                try:
                    meshes[obj.name] = geometry_fingerprint(mesh, include_materials=False)
                finally:
                    evaluated.to_mesh_clear()
            check('wireframe_thickness_evaluates_'+str(thickness), all(
                  values and all(abs(value-thickness) < 1e-6 for value in values)
                  for values in sampled.values()))
            thickness_samples.append({'setting_m': thickness, 'evaluated': sampled})
            wire_shapes.append(meshes)
        check('wireframe_thickness_changes_evaluated_geometry', bool(wire_shapes[0])
              and all(wire_shapes[0][name] != wire_shapes[1][name] for name in wire_shapes[0]))
        details['thickness_samples'] = thickness_samples
        color_samples = []
        for rgb in ((.82, .12, .035), (.025, .62, .86)):
            ctrl['WIREFRAME_COLOR'] = rgb
            update()
            values = color_state(wire_material, bpy.context.evaluated_depsgraph_get())
            check('wireframe_rgb_evaluates_'+str(rgb), color_matches(values, rgb))
            color_samples.append({'setting_rgb': list(rgb), 'evaluated': values})
        details['color_samples'] = color_samples
        cameras = ('CAM_OVERVIEW_WIDE', 'CAM_OVERVIEW_3Q', 'CAM_OVERVIEW_SIDE')
        check('dedicated_cameras', all(name in scene.objects and bpy.data.objects[name].type == 'CAMERA'
              and bpy.data.objects[name].get(overview.OWNER) for name in cameras))
        check('dedicated_lights', bool([obj for obj in scene.objects if obj.type == 'LIGHT'])
              and all(obj.get(overview.OWNER) and obj.data.get(overview.OWNER)
                      for obj in scene.objects if obj.type == 'LIGHT'))
        guides = bpy.data.collections['OVERVIEW_GUIDES']
        check('guides_do_not_render', all(obj.type == 'EMPTY' or obj.hide_render or guides.hide_render
                                        for obj in guides.all_objects))
        finite = True
        for data in {obj.data for obj in owned if obj.data}:
            if isinstance(data, bpy.types.Mesh):
                finite &= all(math.isfinite(value) for vertex in data.vertices for value in vertex.co)
            elif isinstance(data, bpy.types.Curve):
                finite &= all(math.isfinite(value) for spline in data.splines
                              for point in list(spline.points) + list(spline.bezier_points) for value in point.co)
        check('finite_overview_geometry', finite)
        drivers = native_drivers()
        check('all_driver_targets_remapped', all(target.id and target.id.get(overview.OWNER)
              for fc in drivers for var in fc.driver.variables for target in var.targets))
        check('scene_driver_targets_use_overview', all(target.id == scene for fc in drivers
              for var in fc.driver.variables for target in var.targets if target.id_type == 'SCENE'))
        ctrl['SHOW_SHELL'], ctrl['SHOW_WIREFRAME'] = False, True
        update()
        depsgraph = bpy.context.evaluated_depsgraph_get()
        check('shell_can_hide_independently', all(obj.evaluated_get(depsgraph).hide_render for obj in aircraft)
              and all(not obj.evaluated_get(depsgraph).hide_render for obj in wire))
        ctrl['SHOW_SHELL'], ctrl['SHOW_WIREFRAME'] = True, False
        update()
        depsgraph = bpy.context.evaluated_depsgraph_get()
        check('wire_can_hide_independently', all(not obj.evaluated_get(depsgraph).hide_render for obj in aircraft)
              and all(obj.evaluated_get(depsgraph).hide_render for obj in wire))
        for cutaway, nacelle, internals in ((False, True, True), (True, True, True),
                                           (False, False, True), (False, True, False)):
            engine_ctrl['CUTAWAY_MODE'] = cutaway
            engine_ctrl['SHOW_NACELLE'] = nacelle
            engine_ctrl['SHOW_INTERNALS'] = internals
            update()
            depsgraph = bpy.context.evaluated_depsgraph_get()
            expected_visibility = []
            for obj, source in provenance.items():
                source_groups = {col.name for col in source.users_collection}
                if 'ENGINE_NACELLE' in source_groups:
                    expected_hidden = not nacelle or (cutaway and bool(source.get('cutaway_shell')))
                elif source_groups & {'ENGINE_STATIC', 'ENGINE_N1', 'ENGINE_N2', 'ENGINE_COMBUSTOR'}:
                    expected_hidden = not internals or (cutaway and bool(source.get('cutaway_shell')))
                else:
                    continue
                expected_visibility.append(obj.evaluated_get(depsgraph).hide_render == expected_hidden)
            check('engine_visibility_'+str((cutaway, nacelle, internals)),
                  bool(expected_visibility) and all(expected_visibility))
        engine_ctrl['CUTAWAY_MODE'] = False
        engine_ctrl['SHOW_NACELLE'] = engine_ctrl['SHOW_INTERNALS'] = True
        update()
        verify_installed_bleed(scene, template, engine_ctrl, check, details)
        clone = next(obj for obj in clones if obj.get('ecs_source_object') == 'FAN_N1_BLADE_01')

        def sample(frame):
            scene.frame_set(frame)
            update()
            return {item.parent.original.name: item.matrix_world.copy()
                    for item in bpy.context.evaluated_depsgraph_get().object_instances
                    if item.is_instance and item.object.original == clone}

        engine_ctrl['N1_PHASE'] = engine_ctrl['N2_PHASE'] = 0.
        engine_ctrl['N1_SPEED'] = 60.
        engine_ctrl['N2_SPEED'] = 0.
        first = sample(1)
        later = sample(7)
        angle = -(6 / (scene.render.fps / scene.render.fps_base)) * math.tau
        expected = math.atan2(math.sin(angle), math.cos(angle))
        check('both_instance_rotors_animate', set(first) == set(later) == {obj.name for obj in instances}
              and all(abs(later[name].to_euler().x - expected) < 1e-4 for name in later))
        check('instance_mounts_preserved_during_animation', all(
            (later[name].translation - first[name].translation).length < 1e-6 for name in later))
        n2 = bpy.data.objects['ECS ENG | ROT_N2']
        check('N2_independent_of_N1', abs(n2.evaluated_get(bpy.context.evaluated_depsgraph_get()).rotation_euler.x) < 1e-6)
        engine_ctrl['N1_SPEED'], engine_ctrl['N2_SPEED'] = 0., 90.
        sample(7)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        expected_n2 = -90.*6.*scene.render.fps_base/scene.render.fps*math.tau/60.
        check('N2_speed_control_evaluates', abs(n2.evaluated_get(depsgraph).rotation_euler.x-expected_n2) < 1e-5)
        check('N1_independent_of_N2', abs(bpy.data.objects['ECS ENG | ROT_N1'].evaluated_get(
              depsgraph).rotation_euler.x) < 1e-6)
        check('standalone_engine_controller_untouched', controller_state(original_ctrl) == controls_before[original_ctrl])
        # Executing the embedded sidebar twice must replace its classes rather
        # than register duplicate panels. Camera operators work in background too.
        ui_namespace = {'__name__': 'ecs_overview_verification_ui'}
        ui_source = bpy.data.texts[overview.SCRIPT].as_string()
        exec(compile(ui_source, overview.SCRIPT, 'exec'), ui_namespace)
        ui_namespace['register']()
        check('overview_ui_classes_idempotent', all(ui_namespace['registered_class'](cls)
              for cls in ui_namespace['CLASSES']))
        camera_results = []
        for camera in cameras:
            result = bpy.ops.ecs_overview.inspect(camera=camera)
            camera_results.append(result == {'FINISHED'} and scene.camera.name == camera
                                  and bpy.context.view_layer.objects.active == ctrl)
        check('overview_camera_buttons_work', all(camera_results))
        check('native_drivers_valid', bool(drivers) and all(fc.driver.is_valid and fc.driver.is_simple_expression
                                                         for fc in drivers))
        details['invalid_drivers'] = [(fc.id_data.name, fc.data_path, fc.driver.expression)
                                     for fc in drivers if not fc.driver.is_valid]
        details['engine_template_objects'] = len(clones)
        details['engine_unique_geometry'] = len(data_map)
        details['aircraft_objects'] = len(aircraft)
        details['wire_objects'] = len(wire)
        details['native_drivers'] = len(drivers)
    finally:
        for obj in (ctrl, engine_ctrl):
            for key, value in controls_before[obj].items():
                obj[key] = value
            obj.update_tag()
        scene.frame_set(saved_frame[0], subframe=saved_frame[1])
        scene.camera = saved_camera
        update()
        bpy.context.window.scene = previous_scene
    if before:
        after = protected_state()
        checks.update({key + '_preserved_after_animation': before[key] == after[key] for key in before})
    verify_control_round_trip(path, checks, details)
    if before:
        after = protected_state()
        checks.update({key + '_preserved_after_round_trip': before[key] == after[key] for key in before})
    report = {'passed': all(checks.values()), 'blender': bpy.app.version_string,
              'file': str(path), 'checks': checks, 'details': details,
              'scenes': sorted(bpy.data.scenes.keys()), 'inventory': inventory()}
    (ROOT / 'reports').mkdir(exist_ok=True)
    (ROOT / 'reports' / 'ecs_overview_verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('ECS_OVERVIEW_VERIFY', json.dumps({key: value for key, value in report.items()
          if key != 'inventory'}), flush=True)
    if not report['passed']:
        raise RuntimeError('ECS overview checks failed: ' + ', '.join(name for name, passed in checks.items() if not passed))
    return report


if __name__ == '__main__':
    verify(ROOT / 'models' / 'Boeing_737-300_Helios_Livery.blend')

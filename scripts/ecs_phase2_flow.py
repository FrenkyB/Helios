"""Native animated markers for the two Phase 2 pneumatic branches.

Routes follow the physical duct centre lines from engine to pack output. The
shared control is apparent metres per second, not a thermodynamic flow model.
All motion and visibility use Blender's simple-expression drivers; no handlers,
driver namespace setup, or trusted-file auto-execution is required.
"""
import math

import bpy
from mathutils import Vector

OWNER = 'ecs_phase2_asset'
COLORS = {
    'HOT_BLEED': (1., .10, .002),
    'PRECOOLED': (1., .38, .005),
    'PACK_OUTPUT': (.005, .38, 1.),
}
MATERIAL_NAMES = {
    'HOT_BLEED': 'ECS P2 | Flow hot bleed',
    'PRECOOLED': 'ECS P2 | Flow precooled',
    'PACK_OUTPUT': 'ECS P2 | Flow pack output',
}
MARKER_RADIUS = .025
MARKER_SPACING = .65
PATH_RADIUS = .012
PREFIX_MARKER_RADIUS = .053
RESOLUTION = 24


def owned(data):
    data[OWNER] = True
    return data


def property_variable(driver, name, target, path):
    variable = driver.variables.new()
    variable.name = name
    variable.type = 'SINGLE_PROP'
    if isinstance(target, bpy.types.Scene):
        variable.targets[0].id_type = 'SCENE'
    variable.targets[0].id = target
    variable.targets[0].data_path = path


def visibility(obj, ctrl, side):
    for path in ('hide_render', 'hide_viewport'):
        driver = obj.driver_add(path).driver
        driver.type = 'SCRIPTED'
        property_variable(driver, 'show', ctrl, '["SHOW_AIRFLOW"]')
        property_variable(driver, 'side', ctrl, '["SHOW_'+side+'"]')
        driver.expression = 'not show or not side'


def material(kind):
    color = COLORS[kind]
    mat = owned(bpy.data.materials.new(MATERIAL_NAMES[kind]))
    mat.diffuse_color = (*color, 1.)
    mat.use_nodes = True
    owned(mat.node_tree)
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    # Emission carries the visualization color without white light reflections
    # washing out cyan or amber through the ghosted metallic duct walls.
    bsdf.inputs['Base Color'].default_value = (0., 0., 0., 1.)
    bsdf.inputs['Metallic'].default_value = 0.
    bsdf.inputs['Roughness'].default_value = 1.
    bsdf.inputs['Specular IOR Level'].default_value = 0.
    bsdf.inputs['Emission Color'].default_value = (*color, 1.)
    bsdf.inputs['Emission Strength'].default_value = 1.8
    mat['ecs_p2_kind'] = kind
    return mat


def bezier_handles(points):
    """Bounded tangent handles, matching the physical duct generator."""
    points = [Vector(point) for point in points]
    result = []
    for index, point in enumerate(points):
        previous = point-points[index-1] if index else points[1]-point
        following = points[index+1]-point if index+1 < len(points) else previous
        if min(previous.length, following.length) < 1e-8:
            raise ValueError('Phase 2 flow routes contain duplicate adjacent points')
        tangent = previous.normalized()+following.normalized()
        if tangent.length < 1e-8:
            raise ValueError('Phase 2 flow routes reverse at a single waypoint')
        tangent.normalize()
        reach = min(previous.length, following.length)/3
        result.append((tuple(point-tangent*reach), tuple(point+tangent*reach)))
    return result


def route_length(points, handles):
    """Sample the same cubic centre line used by native Follow Path."""
    total = 0.
    for index in range(len(points)-1):
        a, b = Vector(points[index]), Vector(handles[index][1])
        c, d = Vector(handles[index+1][0]), Vector(points[index+1])
        previous = a
        for sample in range(1, 65):
            t = sample/64
            position = a*(1-t)**3+b*3*(1-t)**2*t+c*3*(1-t)*t*t+d*t**3
            total += (position-previous).length
            previous = position
    return total


def arrow_mesh(mat):
    """One linked +Z arrow mesh; materials are overridden per marker object."""
    vertices, faces = [], []
    # Cylindrical tail and the annular underside of the larger conical head.
    profile = ((-.065, .009), (.015, .009), (.015, MARKER_RADIUS))
    segments = 20
    for z, radius in profile:
        for index in range(segments):
            angle = math.tau*index/segments
            vertices.append((radius*math.cos(angle), radius*math.sin(angle), z))
    vertices.append((0., 0., .080))
    for ring in range(len(profile)-1):
        for index in range(segments):
            following = (index+1) % segments
            faces.append((ring*segments+index, ring*segments+following,
                          (ring+1)*segments+following, (ring+1)*segments+index))
    for index in range(segments):
        faces.append((2*segments+index, 2*segments+(index+1) % segments, 3*segments))
    faces.append(tuple(reversed(range(segments))))
    mesh = owned(bpy.data.meshes.new('ECS P2 | Linked airflow arrow'))
    mesh.from_pydata(vertices, [], faces)
    mesh.materials.append(mat)
    mesh.update()
    for polygon in mesh.polygons:
        polygon.use_smooth = len(polygon.vertices) <= 4
    return mesh


def prefix_marker_mesh(mat):
    """Open, downstream-pointing chevrons around the opaque installed pipe.

    The existing pipe has 47 mm outer radius. These 53 mm radius surface
    chevrons leave its material untouched and contain no solid disk or bore cap.
    """
    vertices, faces = [], []
    outline = ((-.075, -.055), (.075, -.055), (.075, .005),
               (.23, .005), (0., .065), (-.23, .005), (-.075, .005))
    for index in range(8):
        angle = index*math.tau/8
        offset = len(vertices)
        for across, z in outline:
            vertices.append((PREFIX_MARKER_RADIUS*math.cos(angle+across),
                             PREFIX_MARKER_RADIUS*math.sin(angle+across), z))
        faces.append(tuple(offset+vertex for vertex in (0, 1, 2, 6)))
        faces.append(tuple(offset+vertex for vertex in (5, 3, 4)))
    mesh = owned(bpy.data.meshes.new('ECS P2 | Linked installed-duct chevrons'))
    mesh.from_pydata(vertices, [], faces)
    mesh.materials.append(mat)
    mesh.update()
    return mesh


def prepend_installed_route(side, points, handles):
    """Read the corrected installed route without changing any Phase 1 ID."""
    name = 'ECS BLEED | '+side+' ROUTE'
    source = bpy.data.objects.get(name)
    if source is None or source.type != 'CURVE' or len(source.data.splines) != 1:
        raise ValueError('Phase 2 airflow requires the existing installed route: '+name)
    spline = source.data.splines[0]
    if spline.type != 'BEZIER':
        raise ValueError('Installed route must expose its original Bezier centreline: '+name)
    matrix = source.matrix_world
    prefix = [tuple(matrix@point.co) for point in spline.bezier_points]
    prefix_handles = [(tuple(matrix@point.handle_left), tuple(matrix@point.handle_right))
                      for point in spline.bezier_points]
    if (Vector(prefix[-1])-Vector(points[0])).length > 1e-4:
        raise ValueError('Phase 2 flow does not join the existing installed outlet: '+side)
    length = route_length(prefix, prefix_handles)
    # The incoming original handle and outgoing new handle each retain their
    # exact respective physical centreline at the common connection.
    joined_handles = (prefix_handles[:-1]+[(prefix_handles[-1][0], handles[0][1])]
                      + list(handles[1:]))
    return prefix+points[1:], joined_handles, length, len(prefix)-1, name


def tag_route(obj, side, kind, role, length):
    obj['ecs_p2_side'] = side
    obj['ecs_p2_kind'] = kind
    obj['ecs_p2_role'] = role
    obj['ecs_p2_length_m'] = length
    obj['Flow direction'] = 'Engine > precooler > pack > short conditioned-air output'


def follow_path(arrow, path, ctrl, scene, length, phase, period=1.):
    follow = arrow.constraints.new('FOLLOW_PATH')
    follow.name = 'Phase 2 downstream flow'
    follow.target = path
    follow.use_fixed_location = True
    follow.use_curve_follow = True
    follow.forward_axis = 'FORWARD_Z'
    follow.up_axis = 'UP_Y'
    driver = follow.driver_add('offset_factor').driver
    driver.type = 'SCRIPTED'
    property_variable(driver, 'speed', ctrl, '["ECS_FLOW_SPEED"]')
    property_variable(driver, 'fps', scene, 'render.fps')
    property_variable(driver, 'fps_base', scene, 'render.fps_base')
    property_variable(driver, 'start', scene, 'frame_start')
    driver.expression = (f'fmod(max(frame-start,0)*max(speed,0)*fps_base/'
                         f'(max(fps,1)*{length:.12g})+{phase:.12g},{period:.12g})')


def build(scene, groups, ctrl, routes):
    """Build six ordered flow routes; cleanup is owned by the Phase 2 wrapper.

    Each route has ``side``, ``kind``, world-coordinate ``points``, and optional
    explicit ``handles`` pairs. Omitted handles use the physical bounded-Bezier
    convention. The latter allows deterministic geometry and driver inspection.
    """
    expected = {(side, kind) for side in ('LEFT', 'RIGHT') for kind in COLORS}
    supplied = [(route['side'], route['kind']) for route in routes]
    if len(supplied) != 6 or set(supplied) != expected:
        raise ValueError('Phase 2 requires exactly one of each flow kind on each side')
    if not ctrl.get(OWNER):
        raise ValueError('Phase 2 airflow requires its dedicated owned controller')
    collection = groups['PHASE2_AIRFLOW']
    mats = {kind: material(kind) for kind in COLORS}
    mesh = arrow_mesh(mats['HOT_BLEED'])
    prefix_mesh = prefix_marker_mesh(mats['HOT_BLEED'])
    result = []
    for route in routes:
        side, kind = route['side'], route['kind']
        points = [tuple(point) for point in route['points']]
        if len(points) < 2:
            raise ValueError('Phase 2 airflow needs at least two route points')
        handles = route.get('handles') or bezier_handles(points)
        if len(handles) != len(points):
            raise ValueError('Phase 2 airflow handle count does not match route points')
        prefix_length, physical_start, prefix_source = 0., 0, ''
        if kind == 'HOT_BLEED':
            points, handles, prefix_length, physical_start, prefix_source = prepend_installed_route(
                side, points, handles)
        length = route_length(points, handles)
        if length < .10:
            raise ValueError('Phase 2 airflow route is too short for directional markers')
        name = 'FLOW_'+side+'_'+kind
        curve = owned(bpy.data.curves.new('ECS P2 | '+name+' centreline', 'CURVE'))
        curve.dimensions = '3D'
        curve.resolution_u = RESOLUTION
        curve.render_resolution_u = RESOLUTION
        curve.bevel_depth = PATH_RADIUS
        curve.bevel_resolution = 3
        curve.use_fill_caps = True
        curve.use_path = True
        curve.path_duration = 100
        spline = curve.splines.new('BEZIER')
        spline.bezier_points.add(len(points)-1)
        for point, position, (left, right) in zip(spline.bezier_points, points, handles):
            point.co = position
            point.handle_left_type = point.handle_right_type = 'FREE'
            point.handle_left, point.handle_right = left, right
        curve.materials.append(mats[kind])
        path = owned(bpy.data.objects.new(name, curve))
        collection.objects.link(path)
        tag_route(path, side, kind, 'FLOW_PATH', length)
        path['ecs_p2_prefix_length_m'] = prefix_length
        path['ecs_p2_physical_start_index'] = physical_start
        path['ecs_p2_prefix_source'] = prefix_source
        path['Flow speed units'] = 'Apparent metres/second; constant-speed visualization'
        path['Future valve source'] = 'ECS ENG | CTRL_ENGINE["BLEED_VALVE_OPEN"]'
        visibility(path, ctrl, side)
        count = max(2, min(24, math.ceil(length/MARKER_SPACING)))
        path['ecs_p2_marker_count'] = count
        for index in range(count):
            arrow = owned(bpy.data.objects.new(name+f'_ARROW_{index+1:03}', mesh))
            collection.objects.link(arrow)
            arrow.material_slots[0].link = 'OBJECT'
            arrow.material_slots[0].material = mats[kind]
            tag_route(arrow, side, kind, 'FLOW_MARKER', length)
            phase = (index+.5)/count
            arrow['ecs_p2_phase'] = phase
            follow_path(arrow, path, ctrl, scene, length, phase)
            visibility(arrow, ctrl, side)
        if prefix_length:
            period = prefix_length/length
            count = max(2, math.ceil(prefix_length/MARKER_SPACING))
            path['ecs_p2_prefix_marker_count'] = count
            for index in range(count):
                arrow = owned(bpy.data.objects.new(name+f'_SLEEVE_{index+1:03}', prefix_mesh))
                collection.objects.link(arrow)
                tag_route(arrow, side, kind, 'FLOW_PREFIX_MARKER', length)
                phase = period*(index+.5)/count
                arrow['ecs_p2_phase'] = phase
                arrow['ecs_p2_period'] = period
                arrow['ecs_p2_prefix_source'] = prefix_source
                arrow['Flow presentation'] = 'Open chevrons outside the unchanged installed bleed pipe'
                follow_path(arrow, path, ctrl, scene, length, phase, period)
                visibility(arrow, ctrl, side)
        result.append(path)
    return result

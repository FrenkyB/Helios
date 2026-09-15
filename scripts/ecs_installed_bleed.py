"""Exactly mirrored installed bleed hardware in the ECS overview only.

Both installations share the detached presentation geometry and materials.
The right bleed subsystem uses the source orientation; a Y-reflected parent
puts the complete left subsystem inboard. The engine core and standalone
engine remain untouched. Coordinates are metres; X aft, Y starboard, Z up.
"""
import math

import bpy
from mathutils import Vector

OWNER = 'ecs_overview_asset'
REPLACED_SOURCES = {'BLEED_OUTLET_STUB', 'BLEED_OUTLET_FLANGE'}
SOURCE_OUTLET = 'BLEED_OUTLET_TO_AIRCRAFT'
SOURCE_COLLECTION = 'ENGINE_BLEED'
ROOT_NAMES = {side: 'ECS BLEED | '+side+' ROOT' for side in ('LEFT', 'RIGHT')}
OMITTED_HARDWARE = REPLACED_SOURCES | {SOURCE_OUTLET}
PIPE_RADIUS = .047
FLANGE_OUTER_RADIUS = .066
FLANGE_INNER_RADIUS = .041
FLANGE_DEPTH = .022
SOURCE_CONNECTION = (2.47, -.64, -.72)
# The evaluated overview pylon encloses the final section at world Z=2.23.
# At its wing overlap the measured wing skin is approximately Z=1.90..2.44.
# Keep the 94 mm pipe and 132 mm end flange within those existing volumes.
RIGHT_ROUTE = (SOURCE_CONNECTION, (2.66, -.64, -.72), (2.74, -.69, -.60),
               (2.74, -.70, -.20), (2.74, -.69, .27), (2.79, -.57, .50),
               (2.87, -.35, .61), (2.96, -.045, .63), (3.10, -.025, .63),
               (3.38, 0., .63), (3.80, 0., .63))
PYLON_ENTRY_INDEX = 7
# Public points are engine-local. Shared geometry lives in the root frame,
# where both sides use RIGHT_ROUTE and only LEFT's parent has scale Y=-1.
ROUTES = {'LEFT': tuple((x, -y, z) for x, y, z in RIGHT_ROUTE), 'RIGHT': RIGHT_ROUTE}
SOURCE_CONNECTIONS = {side: points[0] for side, points in ROUTES.items()}
OUTLET_POINTS = {side: points[-1] for side, points in ROUTES.items()}
ENDPOINT_NAMES = {side: 'ECS BLEED | '+side+' OUTLET' for side in ROUTES}
ENTRY_NAMES = {side: 'ECS BLEED | '+side+' PYLON ENTRY' for side in ROUTES}
ENTRY_POINTS = {side: points[PYLON_ENTRY_INDEX] for side, points in ROUTES.items()}
OUTLET_DIRECTIONS = {'LEFT': (1., 0., 0.), 'RIGHT': (1., 0., 0.)}


def owned(data):
    if 'cfm56_asset' in data:
        del data['cfm56_asset']
    data[OWNER] = True
    return data


def configure_template(template):
    """Retain hidden provenance copies, replacing visible bleed per side."""
    if not template.get(OWNER):
        raise RuntimeError('Installed outlet treatment requires an overview-owned template')
    expected = {obj.name for obj in bpy.data.collections[SOURCE_COLLECTION].objects}
    found = set()
    for obj in template.objects:
        source = obj.get('ecs_source_object')
        if source in expected:
            for path in ('hide_render', 'hide_viewport'):
                obj.driver_remove(path)
                setattr(obj, path, True)
            obj['ecs_installed_replaced'] = True
            obj['ecs_installed_role'] = 'Hidden source provenance; visible subsystem mirrored under each installed bleed root'
            found.add(source)
        elif source == 'CTRL_ENGINE':
            obj['Integration outlet'] = 'Installed endpoints: ECS BLEED | LEFT OUTLET / RIGHT OUTLET; concealed in wing after passage through pylon, local +Z points aft'
    if found != expected:
        raise RuntimeError('Missing source-derived bleed components: '+str(expected-found))


def visibility(obj, engine_ctrl):
    for path in ('hide_render', 'hide_viewport'):
        fc = next((fc for fc in obj.animation_data.drivers if fc.data_path == path), None) if obj.animation_data else None
        expression = fc.driver.expression if fc else ''
        fc = fc or obj.driver_add(path)
        fc.driver.type = 'SCRIPTED'
        var = fc.driver.variables.new()
        var.name = 'ecs_inside'
        var.type = 'SINGLE_PROP'
        var.targets[0].id = engine_ctrl
        var.targets[0].data_path = '["SHOW_INTERNALS"]'
        fc.driver.expression = '('+expression+') or not ecs_inside' if expression else 'not ecs_inside'


def link_object(name, data, collection, parent, side):
    obj = owned(bpy.data.objects.new(name, data))
    collection.objects.link(obj)
    obj.parent = parent
    obj['ecs_installed_side'] = side
    obj['ecs_installed_role'] = 'Installed engine bleed route through pylon to internal wing handoff'
    return obj


def route(side, collection, parent, material, shared_data=None):
    """Bounded Bezier handles prevent automatic overshoot into the engine."""
    name = 'ECS BLEED | '+side+' ROUTE'
    if shared_data is not None:
        obj = link_object(name, shared_data, collection, parent, side)
        obj['ecs_source_connection'] = SOURCE_CONNECTIONS[side]
        obj['ecs_final_outlet'] = OUTLET_POINTS[side]
        obj['ecs_pipe_outer_diameter'] = 2*PIPE_RADIUS
        obj['ecs_pylon_entry_index'] = PYLON_ENTRY_INDEX
        return obj
    data = owned(bpy.data.curves.new(name, 'CURVE'))
    data.dimensions = '3D'
    data.resolution_u = 20
    data.bevel_depth = PIPE_RADIUS
    data.bevel_resolution = 4
    data.use_fill_caps = False
    data.materials.append(material)
    spline = data.splines.new('BEZIER')
    points = [Vector(co) for co in RIGHT_ROUTE]
    spline.bezier_points.add(len(points)-1)
    for i, (point, co) in enumerate(zip(spline.bezier_points, points)):
        point.co = co
        point.handle_left_type = point.handle_right_type = 'FREE'
        if i == 0:
            tangent = Vector((1, 0, 0))
            length = (points[1]-co).length/3
        elif i == len(points)-1:
            tangent = Vector(OUTLET_DIRECTIONS['RIGHT']).normalized()
            length = (co-points[i-1]).length/3
        else:
            before, after = co-points[i-1], points[i+1]-co
            tangent = (before.normalized()+after.normalized()).normalized()
            length = min(before.length, after.length)/3
        point.handle_left = co-tangent*length
        point.handle_right = co+tangent*length
    obj = link_object(name, data, collection, parent, side)
    obj['ecs_source_connection'] = SOURCE_CONNECTIONS[side]
    obj['ecs_final_outlet'] = OUTLET_POINTS[side]
    obj['ecs_pipe_outer_diameter'] = 2*PIPE_RADIUS
    obj['ecs_pylon_entry_index'] = PYLON_ENTRY_INDEX
    return obj


def flange(side, collection, parent, material, shared_data=None):
    """A real annular opening, with no polygon across the duct bore."""
    name = 'ECS BLEED | '+side+' FLANGE'
    if shared_data is not None:
        obj = link_object(name, shared_data, collection, parent, side)
        obj.location = OUTLET_POINTS['RIGHT']
        obj.rotation_euler = Vector(OUTLET_DIRECTIONS['RIGHT']).to_track_quat('Z', 'Y').to_euler()
        return obj
    vertices, faces = [], []
    segments = 64
    # Local Z is the flow direction. The front annulus lies at the endpoint.
    profile = ((-FLANGE_DEPTH, FLANGE_OUTER_RADIUS), (0., FLANGE_OUTER_RADIUS),
               (0., FLANGE_INNER_RADIUS), (-FLANGE_DEPTH, FLANGE_INNER_RADIUS))
    for z, radius in profile:
        for i in range(segments):
            angle = 2*math.pi*i/segments
            vertices.append((radius*math.cos(angle), radius*math.sin(angle), z))
    for band in range(4):
        next_band = (band+1) % 4
        for i in range(segments):
            j = (i+1) % segments
            faces.append((band*segments+i, band*segments+j,
                          next_band*segments+j, next_band*segments+i))
    data = owned(bpy.data.meshes.new(name))
    data.from_pydata(vertices, [], faces)
    data.materials.append(material)
    data.update()
    for polygon in data.polygons:
        polygon.use_smooth = polygon.index//segments in (0, 2)
    obj = link_object(name, data, collection, parent, side)
    obj.location = OUTLET_POINTS['RIGHT']
    obj.rotation_euler = Vector(OUTLET_DIRECTIONS['RIGHT']).to_track_quat('Z', 'Y').to_euler()
    return obj


def hardware(side, collection, parent, template, engine_ctrl):
    """Copy source object behavior while linking only detached overview data."""
    presentation = {obj.get('ecs_source_object'): obj for obj in template.objects}
    sources = [obj for obj in bpy.data.collections[SOURCE_COLLECTION].objects
               if obj.name not in OMITTED_HARDWARE]
    copies = {}
    for source in sources:
        obj = owned(source.copy())
        obj.name = 'ECS BLEED | '+side+' | '+source.name
        obj['ecs_source_object'] = source.name
        obj['ecs_installed_side'] = side
        obj['ecs_installed_role'] = 'Source-derived hardware; shared shape under mirrored installation root'
        collection.objects.link(obj)
        if source.data:
            obj.data = presentation[source.name].data
            obj['ecs_source_data'] = source.data.name
        for index, slot in enumerate(obj.material_slots):
            if slot.link == 'OBJECT':
                slot.material = presentation[source.name].material_slots[index].material
        if obj.animation_data and obj.animation_data.action:
            obj.animation_data.action = None
        copies[source] = obj
    for source, obj in copies.items():
        obj.parent = copies.get(source.parent, parent)
        if obj.animation_data:
            for fc in obj.animation_data.drivers:
                for variable in fc.driver.variables:
                    for target in variable.targets:
                        if isinstance(target.id, bpy.types.Object):
                            if target.id.name == 'CTRL_ENGINE':
                                target.id = engine_ctrl
                            elif target.id in copies:
                                target.id = copies[target.id]
                            else:
                                raise RuntimeError('Unexpected external installed bleed driver: '+obj.name)
                        elif isinstance(target.id, bpy.types.Scene):
                            target.id = bpy.context.scene
        for constraint in obj.constraints:
            if hasattr(constraint, 'target') and constraint.target:
                if constraint.target in copies:
                    constraint.target = copies[constraint.target]
                elif constraint.target.name == 'CTRL_ENGINE':
                    constraint.target = engine_ctrl
                else:
                    raise RuntimeError('Unexpected external installed bleed constraint: '+obj.name)
        visibility(obj, engine_ctrl)
    return {source.name: obj for source, obj in copies.items()}


def build(collection, instances, engine_ctrl):
    """Create matching subsystems beneath identity and Y-reflected roots.

    ``instances`` maps ENGINE_LEFT_OVERVIEW and ENGINE_RIGHT_OVERVIEW to the
    corresponding collection-instance empties. Both retain one shared template.
    Returns side-keyed roots, hardware maps, routes, flanges, pylon entries
    and concealed wing endpoints. No aircraft ECS equipment is constructed.
    """
    materials = {}
    template = instances['ENGINE_LEFT_OVERVIEW'].instance_collection
    if not template.get(OWNER) or not engine_ctrl.get(OWNER):
        raise RuntimeError('Installed outlets require overview-owned engine controls and geometry')
    for obj in template.objects:
        for slot in obj.material_slots:
            mat = slot.material
            if mat and mat.get('ecs_source_material') in ('CFM56 | bleed', 'CFM56 | fastener'):
                materials[mat['ecs_source_material']] = mat
    if len(materials) != 2:
        raise RuntimeError('Missing copied overview bleed or fastener materials')
    result = {}
    for side in ('RIGHT', 'LEFT'):
        root = link_object(ROOT_NAMES[side], None, collection,
                           instances['ENGINE_'+side+'_OVERVIEW'], side)
        root.scale = (1., -1. if side == 'LEFT' else 1., 1.)
        root['ecs_installed_role'] = 'Exact local Y reflection of right bleed subsystem' if side == 'LEFT' else 'Source orientation, facing aircraft centerline'
        components = hardware(side, collection, root, template, engine_ctrl)
        shared_pipe = result['RIGHT']['route'].data if side == 'LEFT' else None
        shared_flange = result['RIGHT']['flange'].data if side == 'LEFT' else None
        pipe = route(side, collection, root, materials['CFM56 | bleed'], shared_pipe)
        end_flange = flange(side, collection, root, materials['CFM56 | fastener'], shared_flange)
        endpoint = link_object(ENDPOINT_NAMES[side], None, collection, root, side)
        endpoint.location = OUTLET_POINTS['RIGHT']
        endpoint.rotation_euler = Vector(OUTLET_DIRECTIONS['RIGHT']).to_track_quat('Z', 'Y').to_euler()
        endpoint.empty_display_type = 'ARROWS'
        endpoint.empty_display_size = .16
        endpoint.hide_render = True
        endpoint['Connection'] = 'Local +Z downstream; concealed pneumatic handoff inside wing after passage through pylon'
        endpoint['ecs_source_connector'] = SOURCE_OUTLET
        endpoint['ecs_pipe_outer_diameter'] = 2*PIPE_RADIUS
        entry = link_object(ENTRY_NAMES[side], None, collection, root, side)
        entry.location = RIGHT_ROUTE[PYLON_ENTRY_INDEX]
        entry.empty_display_type = 'PLAIN_AXES'
        entry.empty_display_size = .09
        entry.hide_render = True
        entry['ecs_installed_role'] = 'Non-rendered marker just inside pylon wall; subsequent duct section stays in pylon/wing volume'
        entry['ecs_route_point_index'] = PYLON_ENTRY_INDEX
        for obj in (pipe, end_flange):
            visibility(obj, engine_ctrl)
        result[side] = dict(root=root, hardware=components, route=pipe, flange=end_flange,
                            pylon_entry=entry, outlet=endpoint)
    return result

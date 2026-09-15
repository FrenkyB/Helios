"""Independent installed-engine presentation, preserving the source engine assets.

Only object hierarchies and closed shell fragments belong to this layer. The
source template, its materials, all rotating meshes, and the installed bleed
system remain untouched. Aircraft coordinates: +X aft, +Y right, +Z up.
"""
import math
import re
from pathlib import Path

import bpy

SCENE = '08 | ECS_OVERVIEW'
OWNER = 'ecs_engine_presentation_asset'
COLLECTION = 'ECS_ENGINE_PRESENTATION'
CONTROLLER = 'CTRL_ECS_ENGINE_PRESENTATION'
SOURCE_TEMPLATE = 'ECS_ENGINE_TEMPLATE'
SOURCE_CONTROLLER = 'ECS ENG | CTRL_ENGINE'
SIDES = ('LEFT', 'RIGHT')
SECTIONS = ('INNER', 'OUTER', 'TOP', 'BOTTOM', 'FRONT', 'AFT')
TEMPLATES = {side: 'ECS_ENGINE_'+side+'_PRESENTATION' for side in SIDES}
INSTANCE_NAMES = {side: 'ENGINE_'+side+'_OVERVIEW' for side in SIDES}
CASE_PREFIXES = ('FAN_CASE', 'BOOSTER_CASE', 'HPC_CASE', 'COMBUSTOR_CASE',
                 'TURBINE_CASE', 'COMBUSTOR_OUTER_LINER', 'LINER_COOLING_HOLE')
NACELLE_PREFIXES = ('NACELLE_', 'CORE_COWLING_', 'EXHAUST_CASING_')
ID_CATEGORIES = ('objects', 'collections', 'meshes', 'curves', 'cameras', 'lights',
                 'materials', 'worlds', 'actions', 'texts', 'node_groups')


def owned(data):
    for key in ('cfm56_asset', 'ecs_overview_asset', 'ecs_phase2_asset'):
        if key in data:
            del data[key]
    data[OWNER] = True
    return data


def settings():
    """Keep saved shot settings through a targeted rebuild."""
    values = {side+'_ENGINE_MODE': 0 for side in SIDES}
    values.update({side+'_SHOW_'+section: True for side in SIDES for section in SECTIONS})
    ctrl = bpy.data.objects.get(CONTROLLER)
    if ctrl and ctrl.get(OWNER):
        for key in values:
            if key.endswith('_ENGINE_MODE'):
                value = ctrl.get(key, 0)
                if isinstance(value, (int, float)) and math.isfinite(value):
                    values[key] = max(0, min(2, int(value)))
            elif key in ctrl:
                values[key] = bool(ctrl[key])
    return values


def clear(scene, overview_root):
    """Retire only this presentation layer after checking all external users."""
    source = bpy.data.collections[SOURCE_TEMPLATE]
    owned_ids = {data for category in ID_CATEGORIES
                 for data in getattr(bpy.data, category) if data.get(OWNER)}
    reserved = {COLLECTION, CONTROLLER, 'ECS_ENGINE_PRESENTATION_README', *TEMPLATES.values()}
    for category in ID_CATEGORIES:
        for data in getattr(bpy.data, category):
            if (data.name in reserved or data.name.startswith(('ECS EP | ', 'LEFT_NACELLE_', 'RIGHT_NACELLE_'))) and data not in owned_ids:
                raise RuntimeError('Engine presentation name occupied by unrelated content: '+data.name)
    for data in owned_ids:
        if isinstance(data, bpy.types.Collection):
            if any(item not in owned_ids for item in (*data.objects, *data.children)):
                raise RuntimeError('Custom content in engine presentation collection: '+data.name)
    instances = {bpy.data.objects[INSTANCE_NAMES[side]] for side in SIDES}
    for data, users in bpy.data.user_map(subset=owned_ids).items():
        for user in users:
            if user in owned_ids or user == scene:
                continue
            if data.name == COLLECTION and user == overview_root:
                continue
            if user in instances and user.instance_collection == data:
                continue
            raise RuntimeError('Engine presentation resource has external user: '+data.name+' by '+user.name)
    # Restore the original references before removing private collections. This
    # also keeps the original template alive throughout the rebuild.
    for instance in instances:
        if instance.instance_collection != source and instance.instance_collection not in owned_ids:
            raise RuntimeError('Installed engine has a foreign instance collection: '+instance.name)
        instance.instance_collection = source
    if owned_ids:
        bpy.data.batch_remove(ids=tuple(owned_ids))


def controller(collection, values):
    ctrl = owned(bpy.data.objects.new(CONTROLLER, None))
    collection.objects.link(ctrl)
    ctrl.empty_display_size = .10
    ctrl['Presentation'] = '0 Closed; 1 Cutaway; 2 Fully open. Panel switches hide additional sections.'
    ctrl['Installation'] = 'Inner faces the fuselage. Cutaway opens the outer side and top.'
    for side in SIDES:
        key = side+'_ENGINE_MODE'
        ctrl[key] = values[key]
        ctrl.id_properties_ui(key).update(min=0, max=2, soft_min=0, soft_max=2,
            description='0 Closed; 1 Cutaway (outer and top removed); 2 Fully open')
        for section in SECTIONS:
            key = side+'_SHOW_'+section
            ctrl[key] = values[key]
            ctrl.id_properties_ui(key).update(description='Show '+side.lower()+' engine '+section.lower()+' shell when allowed by its mode')
    return ctrl


def angular_section(side, y, z):
    """Four cardinal shell sectors, with aircraft-relative side names."""
    if abs(z) > abs(y):
        return 'TOP' if z > 0 else 'BOTTOM'
    inner = y > 0 if side == 'LEFT' else y < 0
    return 'INNER' if inner else 'OUTER'


def source_role(src):
    name = src.get('ecs_source_object', src.name)
    if src.get('ecs_installed_replaced'):
        return 'SUPPRESSED_BLEED'
    if name.startswith(NACELLE_PREFIXES):
        return 'SHELL'
    if name.startswith(CASE_PREFIXES):
        return 'CASING'
    if name.startswith('AIRFLOW_') or name.startswith('FLOW_'):
        return 'AIRFLOW'
    if src.type == 'FONT':
        return 'LABEL'
    if src.type == 'EMPTY':
        return 'HELPER'
    return 'INTERNAL'


def driver(obj, path, expression, variables):
    obj.driver_remove(path)
    fc = obj.driver_add(path)
    fc.driver.type = 'SCRIPTED'
    for name, (target, key) in variables.items():
        var = fc.driver.variables.new()
        var.name = name
        var.type = 'SINGLE_PROP'
        var.targets[0].id = target
        var.targets[0].data_path = '["'+key+'"]'
    fc.driver.expression = expression


def visibility(obj, ctrl, master, side, role, section='', angular=''):
    if role in ('SUPPRESSED_BLEED', 'SOURCE_SHELL'):
        expression, variables = 'True', {}
    elif role in ('SHELL', 'CASING'):
        variables = {'mode': (ctrl, side+'_ENGINE_MODE'),
                     'panel': (ctrl, side+'_SHOW_'+section),
                     'global_cut': (master, 'CUTAWAY_MODE'),
                     'show': (master, 'SHOW_NACELLE' if role == 'SHELL' else 'SHOW_INTERNALS')}
        expression = 'not show or not panel or mode >= 2'
        if angular in ('OUTER', 'TOP'):
            expression += ' or mode >= 1 or global_cut'
    elif role == 'INTERNAL':
        expression = 'not inside'
        variables = {'inside': (master, 'SHOW_INTERNALS')}
    else:
        # Native helper and airflow drivers already point to the master.
        return
    for path in ('hide_render', 'hide_viewport'):
        driver(obj, path, expression, variables)


def fragment_mesh(src, half):
    """Split an existing quarter along its existing 45-degree vertex column.

    Every original skin/end-annulus face is retained exactly once across the
    two fragments. Only the new radial boundary cap is added, reversibly, to
    each private fragment. Source meshes are never edited.
    """
    mesh = src.data
    columns = 33
    if len(mesh.vertices) % columns:
        raise RuntimeError('Unexpected quarter-shell topology: '+src.name)
    rows = len(mesh.vertices)//columns
    if rows < 4 or rows % 2:
        raise RuntimeError('Unexpected quarter-shell section: '+src.name)
    low, high = (0, 16) if half == 0 else (16, 32)
    selected = [row*columns+col for row in range(rows) for col in range(low, high+1)]
    indices = {old: new for new, old in enumerate(selected)}
    vertices = [tuple(mesh.vertices[index].co) for index in selected]
    faces, face_properties, face_loops = [], [], []
    source_faces = []
    for poly in mesh.polygons:
        if all(index in indices for index in poly.vertices):
            source_vertices = list(poly.vertices)
            source_loops = list(poly.loop_indices)
            faces.append(tuple(indices[index] for index in source_vertices))
            face_properties.append((poly.use_smooth, poly.material_index))
            face_loops.append(source_loops)
            source_faces.append(poly.index)
    middle = [indices[row*columns+16] for row in range(rows)]
    # Source normals were normalized by the original mesh builder. Derive the
    # new cap winding from the retained boundary instead of assuming a profile
    # orientation (the rounded inlet profile turns back along the X axis).
    directed_edges = {(a, b) for face in faces
                      for a, b in zip(face, face[1:]+face[:1])}
    if (middle[0], middle[1]) in directed_edges:
        middle.reverse()
    faces.append(tuple(middle))
    face_properties.append((False, 0))
    result = owned(bpy.data.meshes.new('ECS EP | '+mesh.name+' | HALF '+str(half+1)))
    result.from_pydata(vertices, [], faces)
    result.update()
    for mat in mesh.materials:
        result.materials.append(mat)
    for poly, (smooth, material_index) in zip(result.polygons, face_properties):
        poly.use_smooth = smooth
        poly.material_index = material_index
    for layer in mesh.uv_layers:
        copied_layer = result.uv_layers.new(name=layer.name)
        for poly, source_loops in zip(result.polygons, face_loops):
            for new_loop, source_loop in zip(poly.loop_indices, source_loops):
                copied_layer.data[new_loop].uv = layer.data[source_loop].uv
        # The new radial boundary has no source polygon: use its neighboring
        # source loop's UV at each identical boundary vertex.
        source_uv = {mesh.loops[index].vertex_index: layer.data[index].uv.copy()
                     for source_loops in face_loops for index in source_loops}
        cap = result.polygons[-1]
        for loop in cap.loop_indices:
            vertex_index = result.loops[loop].vertex_index
            copied_layer.data[loop].uv = source_uv[selected[vertex_index]]
    result.set_sharp_from_angle(angle=math.radians(38))
    result['ecs_ep_source_mesh'] = mesh.name
    result['ecs_ep_half'] = half
    result['ecs_ep_source_vertex_indices'] = selected
    result['ecs_ep_source_face_indices'] = source_faces
    result['ecs_ep_added_cap_face'] = len(faces)-1
    return result


def clone_template(side, ctrl, master, source, mesh_cache):
    template = owned(bpy.data.collections.new(TEMPLATES[side]))
    template.instance_offset = source.instance_offset
    groups = {}
    for name in ('SHELL', 'INTERNALS', 'HELPERS'):
        group = owned(bpy.data.collections.new('ECS EP | '+side+' | '+name))
        template.children.link(group)
        groups[name] = group
    mapping = {}
    for src in source.all_objects:
        obj = owned(src.copy())
        source_name = src.get('ecs_source_object', src.name)
        obj.name = 'ECS EP | '+side+' | '+('ENGINE_RIG' if source_name == 'CTRL_ENGINE' else source_name)
        role = source_role(src)
        obj['ecs_ep_side'] = side
        obj['ecs_ep_source_object'] = src.name
        obj['ecs_ep_source_name'] = source_name
        obj['ecs_ep_role'] = role
        if source_name == 'CTRL_ENGINE':
            for key in list(obj.keys()):
                if key != OWNER and not key.startswith('ecs_ep_'):
                    del obj[key]
            obj['Purpose'] = 'Static local transform; speed and system controls remain on '+SOURCE_CONTROLLER
        groups['SHELL' if role in ('SHELL', 'CASING') else 'HELPERS' if role in ('HELPER', 'SUPPRESSED_BLEED') else 'INTERNALS'].objects.link(obj)
        mapping[src] = obj
    for src, obj in mapping.items():
        obj.parent = mapping.get(src.parent, src.parent)
        if obj.animation_data:
            if obj.animation_data.action:
                obj.animation_data.action = None
            for fc in obj.animation_data.drivers:
                for var in fc.driver.variables:
                    for target in var.targets:
                        if target.id == master:
                            continue
                        if isinstance(target.id, bpy.types.Object) and target.id in mapping:
                            target.id = mapping[target.id]
        for constraint in obj.constraints:
            if hasattr(constraint, 'target') and constraint.target in mapping:
                constraint.target = mapping[constraint.target]
        role = obj['ecs_ep_role']
        name = obj['ecs_ep_source_name']
        quadrant_match = re.search(r'_Q([1-4])$', name)
        if role in ('SHELL', 'CASING') and quadrant_match:
            obj['ecs_ep_role'] = 'SOURCE_SHELL'
            visibility(obj, ctrl, master, side, 'SOURCE_SHELL')
            quadrant = int(quadrant_match.group(1))-1
            for half in (0, 1):
                key = (src.data, half)
                if key not in mesh_cache:
                    mesh_cache[key] = fragment_mesh(src, half)
                angle = (quadrant+(half+.5)/2)*math.pi/2
                angular = angular_section(side, math.cos(angle), math.sin(angle))
                section = ('FRONT' if name.startswith('NACELLE_INTAKE') else
                           'AFT' if name.startswith(('CORE_COWLING', 'EXHAUST_CASING')) else angular)
                part = owned(obj.copy())
                part.data = mesh_cache[key]
                part.name = side+'_NACELLE_'+section+' | '+name+' | HALF '+str(half+1) if role == 'SHELL' else 'ECS EP | '+side+' | '+section+' | '+name+' | HALF '+str(half+1)
                part['ecs_ep_role'] = role
                part['ecs_ep_section'] = section
                part['ecs_ep_angular_section'] = angular
                part['ecs_ep_half'] = half
                groups['SHELL'].objects.link(part)
                visibility(part, ctrl, master, side, role, section, angular)
        elif role == 'CASING':
            # Fasteners and cooling perforations follow the enclosing sector.
            coords = [src.matrix_world @ vertex.co for vertex in src.data.vertices]
            y = sum(co.y for co in coords)/len(coords)
            z = sum(co.z for co in coords)/len(coords)
            section = angular_section(side, y, z)
            obj['ecs_ep_section'] = obj['ecs_ep_angular_section'] = section
            visibility(obj, ctrl, master, side, role, section, section)
        else:
            visibility(obj, ctrl, master, side, role)
    template['ecs_ep_side'] = side
    template['ecs_ep_source_template'] = source.name
    return template


def build(scene=None):
    """Apply the presentation layer to the existing overview, without rebuilding it."""
    scene = scene or bpy.data.scenes.get(SCENE)
    if scene is None or scene.name != SCENE:
        raise RuntimeError('Existing ECS overview scene is required')
    root = bpy.data.collections.get('ECS_OVERVIEW')
    source = bpy.data.collections.get(SOURCE_TEMPLATE)
    master = bpy.data.objects.get(SOURCE_CONTROLLER)
    if not root or not source or not master:
        raise RuntimeError('Existing installed-engine template and master control are required')
    if any(name not in bpy.data.objects for name in INSTANCE_NAMES.values()):
        raise RuntimeError('Both existing installed engine instances are required')
    values = settings()
    clear(scene, root)
    layer = owned(bpy.data.collections.new(COLLECTION))
    root.children.link(layer)
    ctrl = controller(layer, values)
    reference = owned(bpy.data.objects.new('ECS EP | SOURCE_REFERENCE', None))
    reference.instance_type = 'COLLECTION'
    reference.instance_collection = source
    reference.hide_render = reference.hide_viewport = True
    reference['Purpose'] = 'Retain the unchanged Phase 1 source template through save/reopen'
    layer.objects.link(reference)
    mesh_cache = {}
    templates = {}
    for side in SIDES:
        templates[side] = clone_template(side, ctrl, master, source, mesh_cache)
        bpy.data.objects[INSTANCE_NAMES[side]].instance_collection = templates[side]
    package = Path(__file__).parents[1]
    readme = owned(bpy.data.texts.new('ECS_ENGINE_PRESENTATION_README'))
    readme.write((package/'docs'/'ECS_ENGINE_PRESENTATION.md').read_text(encoding='utf-8'))
    for text_name, path in (('ECS_OVERVIEW_CONTROL.py', package/'scripts'/'ecs_overview_control.py'),
                            ('run_all.py', package/'run_all.py')):
        text = bpy.data.texts.get(text_name)
        if text is None:
            raise RuntimeError('Existing embedded workflow text is required: '+text_name)
        text.clear()
        text.write(path.read_text(encoding='utf-8'))
    ctrl.update_tag()
    bpy.context.view_layer.update()
    return {'controller': ctrl, 'collection': layer, 'templates': templates,
            'source_template': source, 'private_shell_meshes': len(mesh_cache)}

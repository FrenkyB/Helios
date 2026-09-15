"""Verify installed-engine controls while protecting the existing whole project.

The only mutable existing references are the two installed collection instances.
The sidebar and launcher texts may be refreshed; all existing Phase 1/2 geometry,
materials, settings, controllers, animations and other scenes remain protected.
"""
import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path
import re
import sys
from types import SimpleNamespace

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import ecs_overview as overview
from verify_ecs_phase2 import (
    action_state, animation_state, controller_state, geometry_fingerprint,
    handler_state, material_state, plain_value, pointers, properties, property_ui,
    restore_controls, scalar_state, snapshot_controls, update_scenes, world_state,
)
from verify_ecs_overview import EXPECTED_SCENES

OWNER = 'ecs_engine_presentation_asset'
CONTROLLER = 'CTRL_ECS_ENGINE_PRESENTATION'
SIDES = ('LEFT', 'RIGHT')
SECTIONS = ('INNER', 'OUTER', 'TOP', 'BOTTOM', 'FRONT', 'AFT')
TEMPLATES = {side: 'ECS_ENGINE_'+side+'_PRESENTATION' for side in SIDES}
INSTANCES = {'ENGINE_'+side+'_OVERVIEW' for side in SIDES}
EDITABLE_TEXTS = {'ECS_OVERVIEW_CONTROL.py', 'run_all.py'}
CONTROL_NAMES = ('CTRL_ECS_OVERVIEW', 'ECS ENG | CTRL_ENGINE', 'CTRL_ENGINE',
                 'CTRL_ECS_PHASE2', CONTROLLER)


def protected_state(raw=False):
    """Evaluate the retained source before comparing its derived transform cache.

    Blender does not evaluate children of a hidden collection instance after a
    reopen. Their saved location/rotation/scale and drivers are intact, but the
    runtime world matrices and bounding boxes initially contain identity/empty
    caches. Enable only our new hidden reference during this read, then restore
    it. No original object or protected field is altered or omitted.
    """
    reference = bpy.data.objects.get('ECS EP | SOURCE_REFERENCE')
    if reference is None or not reference.get(OWNER):
        return _protected_state(raw)
    hidden = reference.hide_viewport
    try:
        reference.hide_viewport = False
        reference.update_tag()
        return _protected_state(raw)
    finally:
        reference.hide_viewport = hidden
        reference.update_tag()
        bpy.context.view_layer.update()


def _protected_state(raw=False):
    """Fingerprint everything predating this presentation upgrade, including P2."""
    update_scenes()
    memberships = {obj: [] for obj in bpy.data.objects}
    for col in list(bpy.data.collections) + [scene.collection for scene in bpy.data.scenes]:
        for obj in col.objects:
            if not col.get(OWNER):
                memberships[obj].append(col.name)
    result = {key: {} for key in ('objects', 'geometry', 'materials', 'scenes',
                                  'collections', 'actions', 'worlds', 'texts', 'node_groups')}
    for category in ('meshes', 'curves', 'cameras', 'lights'):
        for data in getattr(bpy.data, category):
            if not data.get(OWNER):
                key = data.bl_rna.identifier+' | '+data.name
                result['geometry'][key] = [geometry_fingerprint(data), properties(data), animation_state(data)]
    for obj in bpy.data.objects:
        if obj.get(OWNER):
            continue
        references = pointers(obj)
        if obj.name in INSTANCES:
            # This exact reference is the upgrade's only existing object edit.
            references.pop('instance_collection', None)
        result['objects'][obj.name] = [
            obj.type, obj.data.name if obj.data else None, scalar_state(obj), references,
            [list(row) for row in obj.matrix_world],
            [list(row) for row in obj.matrix_parent_inverse],
            obj.parent.name if obj.parent else None, sorted(memberships[obj]),
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


def owned_state():
    """Exact deterministic generated state, beyond datablock counts and names."""
    update_scenes()
    result = {}
    for category in inventory():
        records = {}
        for block in getattr(bpy.data, category):
            if not block.get(OWNER):
                continue
            state = [scalar_state(block), properties(block),
                     animation_state(block) if hasattr(block, 'animation_data') else None]
            if category in {'meshes', 'curves', 'cameras', 'lights'}:
                state.append(geometry_fingerprint(block))
            elif category == 'objects':
                state.extend([pointers(block), property_ui(block),
                    [list(row) for row in block.matrix_parent_inverse],
                    [(scalar_state(mod), pointers(mod)) for mod in block.modifiers],
                    [(scalar_state(con), pointers(con)) for con in block.constraints],
                    [(slot.link, slot.material.name if slot.material else None) for slot in block.material_slots]])
            elif category == 'collections':
                state.extend([sorted(block.objects.keys()), sorted(block.children.keys())])
            elif category == 'materials':
                state.append(material_state(block))
            elif category == 'texts':
                state.append(block.as_string())
            records[block.name] = state
        result[category] = hashlib.sha256(json.dumps(records, sort_keys=True, default=str).encode()).hexdigest()
    return result


def native_drivers():
    result = []
    for category in ('objects', 'meshes', 'curves', 'materials', 'node_groups'):
        for block in getattr(bpy.data, category):
            if block.get(OWNER):
                if block.animation_data:
                    result.extend(block.animation_data.drivers)
                tree = getattr(block, 'node_tree', None)
                if tree and tree.animation_data:
                    result.extend(tree.animation_data.drivers)
    return result


def set_controls(ctrl, values):
    for key, value in values.items():
        ctrl[key] = value
    ctrl.update_tag()
    bpy.context.view_layer.update()


def mode_defaults(ctrl):
    set_controls(ctrl, {side+'_ENGINE_MODE': 0 for side in SIDES})
    set_controls(ctrl, {side+'_SHOW_'+section: True for side in SIDES for section in SECTIONS})


def matrix_record(obj, graph):
    return [list(row) for row in obj.evaluated_get(graph).matrix_world]


def visibility(obj, graph):
    evaluated = obj.evaluated_get(graph)
    return not evaluated.hide_render, not evaluated.hide_viewport


def expected_visible(obj, ctrl, master):
    role = obj.get('ecs_ep_role')
    side = obj.get('ecs_ep_side')
    section = obj.get('ecs_ep_section')
    angular = obj.get('ecs_ep_angular_section', section)
    mode = int(ctrl[side+'_ENGINE_MODE'])
    if mode == 0 and master['CUTAWAY_MODE']:
        mode = 1
    if role in {'SHELL', 'CASING'}:
        gate = master['SHOW_NACELLE'] if role == 'SHELL' else master['SHOW_INTERNALS']
        return bool(gate and ctrl[side+'_SHOW_'+section] and mode < 2
                    and not (mode == 1 and angular in {'OUTER', 'TOP'}))
    if role == 'INTERNAL':
        return bool(master['SHOW_INTERNALS'])
    if role in {'SUPPRESSED_BLEED', 'SOURCE_SHELL'}:
        return False
    return None


def verify_modes(scene, ctrl, check, details):
    master = bpy.data.objects['ECS ENG | CTRL_ENGINE']
    mode_defaults(ctrl)
    set_controls(master, {'CUTAWAY_MODE': False, 'SHOW_NACELLE': True, 'SHOW_INTERNALS': True})
    members = {side: list(bpy.data.collections[TEMPLATES[side]].all_objects) for side in SIDES}
    visible_sets = {}
    for left, right in itertools.product(range(3), repeat=2):
        set_controls(ctrl, {'LEFT_ENGINE_MODE': left, 'RIGHT_ENGINE_MODE': right})
        graph = bpy.context.evaluated_depsgraph_get()
        records = {}
        for side, mode in zip(SIDES, (left, right)):
            tested = [obj for obj in members[side] if expected_visible(obj, ctrl, master) is not None]
            check(side+'_mode_'+str(mode)+'_with_other_'+str(right if side == 'LEFT' else left),
                  bool(tested) and all(visibility(obj, graph) == (expected_visible(obj, ctrl, master),)*2
                                      for obj in tested))
            shell = {obj.name for obj in members[side] if obj.get('ecs_ep_role') in {'SHELL', 'CASING'}
                     and visibility(obj, graph)[0]}
            internal = {obj.name for obj in members[side] if obj.get('ecs_ep_role') == 'INTERNAL'
                        and visibility(obj, graph)[0]}
            if (side, mode) in visible_sets:
                check(side+'_unchanged_by_other_mode_'+str(left)+'_'+str(right),
                      visible_sets[side, mode] == (shell, internal))
            visible_sets[side, mode] = shell, internal
            records[side] = {'mode': mode, 'visible_shell_parts': len(shell), 'visible_internal_parts': len(internal)}
        details.setdefault('nine_mode_combinations', []).append(records)
    for side in SIDES:
        closed, cutaway, opened = [visible_sets[side, mode] for mode in range(3)]
        check(side+'_closed_cutaway_fully_open_distinct_shell_states',
              0 == len(opened[0]) < len(cutaway[0]) < len(closed[0]))
        check(side+'_internal_architecture_retained_in_every_mode', bool(closed[1]) and closed[1] == cutaway[1] == opened[1])
    mode_defaults(ctrl)
    for side, section in itertools.product(SIDES, SECTIONS):
        prop = side+'_SHOW_'+section
        set_controls(ctrl, {prop: False})
        graph = bpy.context.evaluated_depsgraph_get()
        targeted = [obj for obj in members[side] if obj.get('ecs_ep_role') in {'SHELL', 'CASING'}
                    and obj.get('ecs_ep_section') == section]
        all_shells = [obj for objects in members.values() for obj in objects
                      if obj.get('ecs_ep_role') in {'SHELL', 'CASING'}]
        check(prop+'_independent_section_switch', bool(targeted) and all(
              visibility(obj, graph) == (expected_visible(obj, ctrl, master),)*2 for obj in all_shells))
        set_controls(ctrl, {prop: True})
    for cutaway, nacelle, internals in itertools.product((False, True), repeat=3):
        set_controls(master, {'CUTAWAY_MODE': cutaway, 'SHOW_NACELLE': nacelle, 'SHOW_INTERNALS': internals})
        graph = bpy.context.evaluated_depsgraph_get()
        objects = [obj for group in members.values() for obj in group
                   if expected_visible(obj, ctrl, master) is not None]
        check('legacy_global_compatibility_'+str((cutaway, nacelle, internals)), all(
              visibility(obj, graph) == (expected_visible(obj, ctrl, master),)*2 for obj in objects))
    set_controls(master, {'CUTAWAY_MODE': False, 'SHOW_NACELLE': True, 'SHOW_INTERNALS': True})


def verify_geometry(scene, check, details):
    source = bpy.data.collections[overview.TEMPLATE]
    source_objects = set(source.all_objects)
    source_names = {obj.name for obj in source_objects}
    source_mats = {slot.material for obj in source_objects for slot in obj.material_slots if slot.material}
    fragment_meshes = set()
    sections = {}
    for side in SIDES:
        instance = bpy.data.objects['ENGINE_'+side+'_OVERVIEW']
        template = bpy.data.collections[TEMPLATES[side]]
        objects = list(template.all_objects)
        check(side+'_existing_instance_uses_private_template', instance.instance_collection == template
              and instance.instance_type == 'COLLECTION' and instance.name in scene.objects)
        check(side+'_private_template_retains_original_instance_offset', tuple(template.instance_offset) == tuple(source.instance_offset))
        check(side+'_entire_original_engine_object_hierarchy_reused',
              {obj.get('ecs_ep_source_object') for obj in objects} == source_names)
        check(side+'_source_mapping_and_ownership_complete', all(
              obj.get(OWNER) and obj.get('ecs_ep_side') == side and obj.get('ecs_ep_source_object') in source_names
              and not obj.get('ecs_overview_asset') and not obj.get('ecs_phase2_asset') and not obj.get('cfm56_asset')
              for obj in objects))
        base = {obj.get('ecs_ep_source_object'): obj for obj in objects
                if not (obj.data and obj.data.get(OWNER))}
        check(side+'_base_clone_count_matches_original', len(base) == len(source_objects))
        check(side+'_source_meshes_shared_without_modification', all(
              obj.data == bpy.data.objects[name].data for name, obj in base.items()))
        check(side+'_private_transform_hierarchy_matches_original', all(
              obj.parent == base.get(bpy.data.objects[name].parent.name) if bpy.data.objects[name].parent else obj.parent is None
              for name, obj in base.items()))
        private_parts = [obj for obj in objects if obj.data and obj.data.get(OWNER)]
        fragment_meshes.update(obj.data for obj in private_parts)
        mapped = {}
        for obj in private_parts:
            mapped.setdefault(obj.get('ecs_ep_source_object'), []).append(obj)
        for name, parts in mapped.items():
            src = bpy.data.objects[name]
            mesh = src.data
            retained = []
            valid = len(parts) == 2 and all(part.get('ecs_ep_role') in {'SHELL', 'CASING'} for part in parts)
            for part in parts:
                data = part.data
                vertices = list(data.get('ecs_ep_source_vertex_indices', []))
                faces = list(data.get('ecs_ep_source_face_indices', []))
                cap = int(data.get('ecs_ep_added_cap_face', -1))
                retained.extend(faces)
                valid = valid and (len(vertices) == len(data.vertices) and len(faces)+1 == len(data.polygons)
                    and cap == len(faces) and data.get('ecs_ep_source_mesh') == mesh.name
                    and part.matrix_local == base[name].matrix_local
                    and tuple(data.materials) == tuple(mesh.materials))
                if not valid:
                    continue
                valid = valid and all((vertex.co-mesh.vertices[int(original)].co).length < 1e-8
                                     for vertex, original in zip(data.vertices, vertices))
                for poly, original in zip(data.polygons, faces):
                    old = mesh.polygons[int(original)]
                    valid = valid and tuple(vertices[index] for index in poly.vertices) == tuple(old.vertices)
                    valid = valid and poly.material_index == old.material_index and poly.use_smooth == old.use_smooth
                    valid = valid and list(data.uv_layers.keys()) == list(mesh.uv_layers.keys())
                    for layer in mesh.uv_layers:
                        valid = valid and all((data.uv_layers[layer.name].data[new].uv-layer.data[old_loop].uv).length < 1e-8
                            for new, old_loop in zip(poly.loop_indices, old.loop_indices))
                boundary = data.polygons[cap]
                valid = valid and all(int(vertices[index]) % 33 == 16 for index in boundary.vertices)
                edges = {}
                for poly in data.polygons:
                    ids = list(poly.vertices)
                    for a, b in zip(ids, ids[1:]+ids[:1]):
                        edges.setdefault(tuple(sorted((a, b))), []).append((a, b))
                valid = valid and all(len(uses) == 2 and uses[0] == tuple(reversed(uses[1])) for uses in edges.values())
            check(side+'_exact_original_shell_face_union_'+name, valid and sorted(retained) == list(range(len(mesh.polygons))))
        check(side+'_split_source_shells_are_hidden_and_retained', bool(mapped) and all(
              base[name].get('ecs_ep_role') == 'SOURCE_SHELL' and base[name].data == bpy.data.objects[name].data
              for name in mapped))
        shells = [obj for obj in objects if obj.get('ecs_ep_role') in {'SHELL', 'CASING'}]
        sections[side] = {section: len([obj for obj in shells if obj.get('ecs_ep_section') == section]) for section in SECTIONS}
        check(side+'_all_six_shell_sections_have_geometry', all(sections[side].values()))
        for section in SECTIONS:
            selected = [obj for obj in shells if obj.get('ecs_ep_section') == section]
            cardinal_results = []
            for obj in selected:
                coords = [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]
                center = sum(coords, Vector())/len(coords)
                angular = obj.get('ecs_ep_angular_section')
                if angular == 'TOP':
                    cardinal_results.append(center.z > 0 and center.z >= abs(center.y)-2e-5)
                elif angular == 'BOTTOM':
                    cardinal_results.append(center.z < 0 and -center.z >= abs(center.y)-2e-5)
                else:
                    inner = center.y > 0 if side == 'LEFT' else center.y < 0
                    cardinal_results.append(abs(center.y) >= abs(center.z)-2e-5 and
                                            ((angular == 'INNER') == inner))
            check(side+'_'+section+'_aircraft_relative_section_geometry', bool(selected) and all(cardinal_results))
        front = [obj for obj in shells if obj.get('ecs_ep_section') == 'FRONT']
        aft = [obj for obj in shells if obj.get('ecs_ep_section') == 'AFT']
        check(side+'_front_and_aft_shells_follow_engine_axis', max(
              (obj.matrix_world @ v.co).x for obj in front for v in obj.data.vertices) < min(
              (obj.matrix_world @ v.co).x for obj in aft for v in obj.data.vertices))
        check(side+'_all_surface_materials_reuse_source_materials', all(
              slot.material in source_mats for obj in objects for slot in obj.material_slots if slot.material))
    check('two_private_hierarchies_independent', not (set(bpy.data.collections[TEMPLATES['LEFT']].all_objects)
          & set(bpy.data.collections[TEMPLATES['RIGHT']].all_objects)))
    check('shell_fragment_meshes_shared_between_sides', bool(fragment_meshes) and all(
          any(obj.data == mesh for obj in bpy.data.collections[TEMPLATES[side]].all_objects)
          for mesh in fragment_meshes for side in SIDES))
    reference = bpy.data.objects.get('ECS EP | SOURCE_REFERENCE')
    check('untouched_original_template_kept_alive_in_saved_project', reference is not None
          and reference.get(OWNER) and reference.instance_collection == source
          and reference.hide_render and reference.hide_viewport)
    check('no_new_system_geometry_or_materials', not inventory()['materials'] and not inventory()['curves']
          and all(mesh.get('ecs_ep_source_mesh') for mesh in fragment_meshes)
          and len(fragment_meshes) == len(inventory()['meshes']))
    check('no_private_engine_objects_linked_to_other_scenes', all(
          not any(obj.get(OWNER) for obj in other.objects) for other in bpy.data.scenes if other != scene))
    details['shell_sections'] = sections
    details['private_fragment_meshes'] = len(fragment_meshes)
    details['original_template_objects'] = len(source_objects)


def verify_animation(scene, ctrl, check, details):
    master = bpy.data.objects['ECS ENG | CTRL_ENGINE']
    mode_defaults(ctrl)
    set_controls(master, {'CUTAWAY_MODE': False, 'SHOW_INTERNALS': True,
                          'N1_PHASE': 0., 'N2_PHASE': 0.})
    sides = {side: list(bpy.data.collections[TEMPLATES[side]].all_objects) for side in SIDES}
    rotors = {(side, spool): next(obj for obj in sides[side]
                if obj.get('ecs_ep_source_name') == 'ROT_N'+str(spool)) for side in SIDES for spool in (1, 2)}
    shells = [obj for objects in sides.values() for obj in objects if obj.get('ecs_ep_role') in {'SHELL', 'CASING'}]
    physical = [obj for name in ('PNEUMATIC_DUCTS', 'PRECOOLERS', 'PACKS')
                for obj in bpy.data.collections[name].all_objects]
    installed = [obj for obj in scene.objects if obj.name.startswith('ECS BLEED | ')]
    static_before = None
    probes = []
    for mode in range(3):
        set_controls(ctrl, {side+'_ENGINE_MODE': mode for side in SIDES})
        for n1, n2 in ((60., 0.), (0., 90.), (60., 90.)):
            set_controls(master, {'N1_SPEED': n1, 'N2_SPEED': n2})
            samples = []
            for frame in (scene.frame_start, scene.frame_start+6):
                scene.frame_set(frame)
                bpy.context.view_layer.update()
                graph = bpy.context.evaluated_depsgraph_get()
                samples.append({(side, spool): rotors[side, spool].evaluated_get(graph).rotation_euler.x
                                for side in SIDES for spool in (1, 2)})
                state = {obj.name: matrix_record(obj, graph) for obj in (*shells, *physical, *installed)}
                if static_before is None:
                    static_before = state
                check('static_shells_p1_bleed_p2_system_'+str((mode, n1, n2, frame)), state == static_before)
            seconds = 6.*scene.render.fps_base/scene.render.fps
            for side in SIDES:
                check(side+'_independent_N1_N2_mode_'+str((mode, n1, n2)), all(
                      abs(samples[1][side, spool]-samples[0][side, spool]+speed*seconds*math.tau/60.) < 1e-5
                      for spool, speed in ((1, n1), (2, n2))))
            probes.append({'mode': mode, 'N1_RPM': n1, 'N2_RPM': n2,
                           'angles': {side: [samples[1][side, spool] for spool in (1, 2)] for side in SIDES}})
    check('private_spools_keep_original_shared_speed_driver_targets', all(
          any(target.id == master and target.data_path == '["N'+str(spool)+'_SPEED"]'
              for fc in rotor.animation_data.drivers for variable in fc.driver.variables for target in variable.targets)
          for (side, spool), rotor in rotors.items()))
    details['rotor_motion'] = probes


class LayoutProbe:
    """Execute the embedded panel's actual draw method without an open editor."""
    def __init__(self):
        self.properties = []
        self.operators = []

    def prop(self, data, path, **kwargs):
        self.properties.append((data.name, path))

    def row(self, **kwargs):
        return self

    def column(self, **kwargs):
        return self

    def box(self, **kwargs):
        return self

    def split(self, **kwargs):
        return self

    def separator(self, **kwargs):
        pass

    def label(self, **kwargs):
        pass

    def operator(self, name, **kwargs):
        result = SimpleNamespace()
        self.operators.append((name, kwargs, result))
        return result


def verify_ui(scene, check, details):
    source = bpy.data.texts[overview.SCRIPT].as_string()
    namespace = {'__name__': 'ecs_engine_presentation_verification_ui'}
    before_handlers = handler_state()
    for repetition in range(2):
        exec(compile(source, overview.SCRIPT, 'exec'), namespace)
        namespace['register']()
        check('embedded_sidebar_repeat_registration_'+str(repetition), all(
              namespace['registered_class'](cls) for cls in namespace['CLASSES']))
    layout = LayoutProbe()
    namespace['ECS_OVERVIEW_PT_controls'].draw(SimpleNamespace(layout=layout), bpy.context)
    old_expected = {
        'CTRL_ECS_OVERVIEW': ('SHOW_SHELL', 'SHOW_WIREFRAME', 'WIREFRAME_THICKNESS', 'WIREFRAME_COLOR'),
        'ECS ENG | CTRL_ENGINE': ('CUTAWAY_MODE', 'SHOW_NACELLE', 'SHOW_INTERNALS', 'N1_SPEED', 'N2_SPEED'),
        'CTRL_ECS_PHASE2': ('ECS_FLOW_SPEED', 'SHOW_DUCTS', 'SHOW_PRECOOLERS', 'SHOW_PACKS',
                           'SHOW_AIRFLOW', 'SHOW_LEFT', 'SHOW_RIGHT'),
    }
    check('existing_phase1_phase2_controls_in_same_panel', all(
          (name, '["'+key+'"]') in layout.properties for name, keys in old_expected.items() for key in keys))
    for side in SIDES:
        check(side+'_six_section_controls_in_panel', all(
              (CONTROLLER, '["'+key+'"]') in layout.properties
              for key in (side+'_SHOW_'+section for section in SECTIONS)))
    buttons = {(getattr(op, 'side', None), getattr(op, 'mode', None)) for name, _, op in layout.operators
               if name == 'ecs_overview.engine_presentation'}
    check('nine_side_and_both_mode_buttons', buttons == set(itertools.product((*SIDES, 'BOTH'), range(3))))
    ctrl = bpy.data.objects[CONTROLLER]
    master = bpy.data.objects['ECS ENG | CTRL_ENGINE']
    fine = {key: ctrl[key] for key in ctrl.keys() if '_SHOW_' in key}
    for side, mode in itertools.product((*SIDES, 'BOTH'), range(3)):
        mode_defaults(ctrl)
        set_controls(master, {'CUTAWAY_MODE': False})
        result = bpy.ops.ecs_overview.engine_presentation(side=side, mode=mode)
        check('UI_mode_button_'+side+'_'+str(mode), result == {'FINISHED'} and all(
              ctrl[test+'_ENGINE_MODE'] == (mode if side in {test, 'BOTH'} else 0) for test in SIDES))
    for side, other_mode in itertools.product(SIDES, (0, 2)):
        other = 'RIGHT' if side == 'LEFT' else 'LEFT'
        set_controls(ctrl, {side+'_ENGINE_MODE': 0, other+'_ENGINE_MODE': other_mode,
                            side+'_SHOW_FRONT': False})
        set_controls(master, {'CUTAWAY_MODE': True})
        result = bpy.ops.ecs_overview.engine_presentation(side=side, mode=0)
        check('UI_close_clears_global_preserves_other_'+side+'_'+str(other_mode),
              result == {'FINISHED'} and not master['CUTAWAY_MODE'] and ctrl[side+'_ENGINE_MODE'] == 0
              and ctrl[other+'_ENGINE_MODE'] == max(1, other_mode) and not ctrl[side+'_SHOW_FRONT'])
    set_controls(ctrl, fine)
    check('only_one_overview_panel_class', sum(cls.__name__ == 'ECS_OVERVIEW_PT_controls' for cls in namespace['CLASSES']) == 1)
    check('sidebar_registers_no_script_handlers', before_handlers == handler_state())
    for camera in ('CAM_OVERVIEW_WIDE', 'CAM_OVERVIEW_3Q', 'CAM_OVERVIEW_SIDE',
                   'CAM_ECS_PHASE2_LEFT', 'CAM_ECS_PHASE2_RIGHT', 'CAM_ECS_PHASE2_PACKS'):
        result = bpy.ops.ecs_overview.inspect(camera=camera)
        check('preserved_camera_button_'+camera, result == {'FINISHED'} and scene.camera.name == camera)
    details['sidebar_control_count'] = len(layout.properties)


def verify_roundtrip(path, check, details):
    path = Path(path).resolve()
    temporary = ROOT / 'reports' / 'ECS_Engine_Presentation_control_roundtrip.blend'
    active = bpy.context.window.scene.name
    before = snapshot_controls(CONTROL_NAMES)
    state = {'LEFT_ENGINE_MODE': 2, 'RIGHT_ENGINE_MODE': 1,
             'LEFT_SHOW_INNER': False, 'LEFT_SHOW_FRONT': False,
             'RIGHT_SHOW_BOTTOM': False, 'RIGHT_SHOW_AFT': False}
    try:
        bpy.context.window.scene = bpy.data.scenes[overview.SCENE]
        set_controls(bpy.data.objects[CONTROLLER], state)
        bpy.ops.wm.save_as_mainfile(filepath=str(temporary), copy=True)
        bpy.ops.wm.open_mainfile(filepath=str(temporary))
        bpy.context.window.scene = bpy.data.scenes[overview.SCENE]
        bpy.context.view_layer.update()
        ctrl = bpy.data.objects[CONTROLLER]
        master = bpy.data.objects['ECS ENG | CTRL_ENGINE']
        check('nondefault_independent_modes_and_sections_save_reopen', all(ctrl[key] == value for key, value in state.items()))
        graph = bpy.context.evaluated_depsgraph_get()
        objects = [obj for side in SIDES for obj in bpy.data.collections[TEMPLATES[side]].all_objects
                   if expected_visible(obj, ctrl, master) is not None]
        check('independent_native_visibility_after_reopen', bool(objects) and all(
              visibility(obj, graph) == (expected_visible(obj, ctrl, master),)*2 for obj in objects))
        check('old_controllers_survive_new_presentation_roundtrip', all(
              controller_state(bpy.data.objects[name]) == values for name, values in before.items() if name != CONTROLLER))
        drivers = native_drivers()
        check('all_native_drivers_valid_after_reopen_without_autoexec', bool(drivers)
              and all(fc.driver.is_valid and fc.driver.is_simple_expression for fc in drivers))
        set_controls(master, {'N1_SPEED': 60., 'N2_SPEED': 90., 'N1_PHASE': 0., 'N2_PHASE': 0.})
        scene = bpy.data.scenes[overview.SCENE]
        samples = []
        for frame in (scene.frame_start, scene.frame_start+6):
            scene.frame_set(frame)
            bpy.context.view_layer.update()
            graph = bpy.context.evaluated_depsgraph_get()
            samples.append({(side, spool): next(obj for obj in bpy.data.collections[TEMPLATES[side]].all_objects
                if obj.get('ecs_ep_source_name') == 'ROT_N'+str(spool)).evaluated_get(graph).rotation_euler.x
                for side in SIDES for spool in (1, 2)})
        check('both_spools_both_engines_animate_after_reopen', all(
              abs(samples[1][side, spool]-samples[0][side, spool]) > .1 for side in SIDES for spool in (1, 2)))
        details['saved_nondefault_presentation_probe'] = state
    finally:
        bpy.ops.wm.open_mainfile(filepath=str(path))
        bpy.context.window.scene = bpy.data.scenes[active]
        temporary.unlink(missing_ok=True)
    check('candidate_controls_restored_after_roundtrip', snapshot_controls(CONTROL_NAMES) == before)


def verify_existing_controls(scene, check):
    """Exercise preserved aircraft and pneumatic switches in the upgraded scene."""
    master = bpy.data.objects['CTRL_ECS_OVERVIEW']
    for enabled in (False, True):
        set_controls(master, {'SHOW_SHELL': enabled, 'SHOW_WIREFRAME': not enabled})
        graph = bpy.context.evaluated_depsgraph_get()
        check('existing_aircraft_shell_wire_controls_'+str(enabled), all(
              visibility(obj, graph)[0] == (enabled if obj.name.startswith('ECS AIR | ') else not enabled)
              for obj in scene.objects if obj.name.startswith(('ECS AIR | ', 'ECS WIRE | '))))
    ctrl = bpy.data.objects['CTRL_ECS_PHASE2']
    mapping = {'SHOW_DUCTS': 'PNEUMATIC_DUCTS', 'SHOW_PRECOOLERS': 'PRECOOLERS',
               'SHOW_PACKS': 'PACKS', 'SHOW_AIRFLOW': 'PHASE2_AIRFLOW'}
    set_controls(ctrl, {'SHOW_LEFT': True, 'SHOW_RIGHT': True, **{key: True for key in mapping}})
    for setting, name in mapping.items():
        members = [obj for obj in bpy.data.collections[name].all_objects if obj.type in {'MESH', 'CURVE'}]
        set_controls(ctrl, {setting: False})
        graph = bpy.context.evaluated_depsgraph_get()
        check('existing_phase2_'+setting+'_still_hides_group', bool(members) and all(
              visibility(obj, graph) == (False, False) for obj in members))
        set_controls(ctrl, {setting: True})
    for side in SIDES:
        set_controls(ctrl, {'SHOW_'+side: False})
        graph = bpy.context.evaluated_depsgraph_get()
        parts = [obj for name in mapping.values() for obj in bpy.data.collections[name].all_objects
                 if obj.type in {'MESH', 'CURVE'} and (obj.get('ecs_phase2_side') or obj.get('ecs_p2_side')) == side]
        check('existing_phase2_'+side+'_branch_switch', bool(parts) and all(visibility(obj, graph) == (False, False) for obj in parts))
        set_controls(ctrl, {'SHOW_'+side: True})
    markers = [next(obj for obj in bpy.data.collections['PHASE2_AIRFLOW'].all_objects
                    if obj.get('ecs_p2_side') == side and obj.get('ecs_p2_role') == 'FLOW_MARKER') for side in SIDES]
    for speed in (0., 1.):
        set_controls(ctrl, {'ECS_FLOW_SPEED': speed})
        samples = []
        for frame in (scene.frame_start, scene.frame_start+1):
            scene.frame_set(frame)
            graph = bpy.context.evaluated_depsgraph_get()
            samples.append([obj.evaluated_get(graph).matrix_world.translation.copy() for obj in markers])
        check('existing_phase2_flow_speed_'+str(speed), all(
              (b-a).length < 1e-6 if speed == 0 else (b-a).length > .001 for a, b in zip(*samples)))


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
    active = bpy.context.window.scene.name
    bpy.context.window.scene = scene
    frame = scene.frame_current, scene.frame_subframe
    camera = scene.camera.name if scene.camera else None
    controls = snapshot_controls(CONTROL_NAMES)
    handlers = handler_state()
    ctrl = bpy.data.objects[CONTROLLER]
    try:
        check('presentation_collection_in_existing_overview',
              'ECS_ENGINE_PRESENTATION' in bpy.data.collections[overview.COLLECTION].children
              and bpy.data.collections['ECS_ENGINE_PRESENTATION'].get(OWNER))
        check('one_presentation_controller', len([obj for obj in bpy.data.objects if obj.name == CONTROLLER]) == 1
              and ctrl.get(OWNER) and ctrl.name in scene.objects)
        check('native_control_properties_present', all(side+'_ENGINE_MODE' in ctrl and all(
              side+'_SHOW_'+section in ctrl for section in SECTIONS) for side in SIDES))
        check('native_modes_have_documented_range', all(
              ctrl.id_properties_ui(side+'_ENGINE_MODE').as_dict().get('min') == 0
              and ctrl.id_properties_ui(side+'_ENGINE_MODE').as_dict().get('max') == 2 for side in SIDES))
        check('no_added_scenes_actions_worlds', not any(inventory()[key] for key in ('scenes', 'actions', 'worlds')))
        check('deterministic_names_without_duplicate_suffixes', all(not re.search(r'\.\d{3}$', name)
              for names in inventory().values() for name in names))
        verify_geometry(scene, check, details)
        verify_modes(scene, ctrl, check, details)
        verify_animation(scene, ctrl, check, details)
        verify_existing_controls(scene, check)
        verify_ui(scene, check, details)
        drivers = native_drivers()
        allowed = {scene, ctrl, bpy.data.objects['ECS ENG | CTRL_ENGINE']}
        allowed.update(obj for obj in bpy.data.objects if obj.get(OWNER))
        check('all_presentation_drivers_native_and_valid_without_autoexec', bool(drivers)
              and all(fc.driver.is_valid and fc.driver.is_simple_expression for fc in drivers))
        check('drivers_use_only_private_rig_or_existing_overview_master', all(
              target.id in allowed for fc in drivers for var in fc.driver.variables for target in var.targets))
        check('no_new_script_handlers', handler_state() == handlers)
        check('standalone_engine_controller_untouched', controller_state(bpy.data.objects['CTRL_ENGINE']) == controls['CTRL_ENGINE'])
        details['native_driver_count'] = len(drivers)
        details['invalid_drivers'] = [(fc.id_data.name, fc.data_path, fc.driver.expression)
                                     for fc in drivers if not fc.driver.is_valid]
    finally:
        restore_controls(controls)
        scene.frame_set(frame[0], subframe=frame[1])
        scene.camera = bpy.data.objects.get(camera) if camera else None
        bpy.context.view_layer.update()
        bpy.context.window.scene = bpy.data.scenes[active]
    if before:
        after = protected_state()
        checks.update({key+'_preserved_after_functional_tests': before[key] == after[key] for key in before})
    verify_roundtrip(path, check, details)
    if before:
        after = protected_state()
        checks.update({key+'_preserved_after_roundtrip': before[key] == after[key] for key in before})
    report = {'passed': all(checks.values()), 'blender': bpy.app.version_string, 'file': str(path),
              'checks': checks, 'details': details, 'scenes': sorted(bpy.data.scenes.keys()),
              'inventory': inventory(), 'owned_state': owned_state()}
    (ROOT / 'reports').mkdir(exist_ok=True)
    output = ROOT / 'reports' / 'ecs_engine_presentation_verification.json'
    output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    if not report['passed']:
        raise RuntimeError('ECS engine presentation verification failed: '+', '.join(
            name for name, passed in checks.items() if not passed))
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', default=str(ROOT / 'models' / 'Boeing_737-300_Helios_Livery.blend'))
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    report = verify(args.source)
    print('PASS ECS engine presentation:', len(report['checks']), 'saved-file checks', flush=True)


if __name__ == '__main__':
    main()

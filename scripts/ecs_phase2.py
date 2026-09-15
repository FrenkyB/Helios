"""Add the owned Phase 2 system to the existing ECS overview, without rebuilding it."""
import math
from pathlib import Path

import bpy
from mathutils import Vector

import ecs_phase2_geometry as geometry
import ecs_phase2_flow as flow

SCENE = '08 | ECS_OVERVIEW'
COLLECTION = 'ECS_PHASE2'
CONTROLLER = 'CTRL_ECS_PHASE2'
OWNER = 'ecs_phase2_asset'
GROUPS = ('PNEUMATIC_DUCTS', 'PRECOOLERS', 'PACKS', 'PHASE2_AIRFLOW', 'PHASE2_HELPERS')
SWITCHES = ('SHOW_DUCTS', 'SHOW_PRECOOLERS', 'SHOW_PACKS', 'SHOW_AIRFLOW', 'SHOW_LEFT', 'SHOW_RIGHT')
CAMERAS = {
    'CAM_ECS_PHASE2_LEFT': ((10.0, -10.8, 7.7), (13.9, -2.9, 2.0), 8.8),
    'CAM_ECS_PHASE2_RIGHT': ((10.0, 10.8, 7.7), (13.9, 2.9, 2.0), 8.8),
    'CAM_ECS_PHASE2_PACKS': ((9.3, -5.8, 6.9), (13.6, 0.0, 2.05), 5.5),
}
ID_CATEGORIES = ('objects', 'collections', 'meshes', 'curves', 'cameras', 'lights',
                 'materials', 'worlds', 'actions', 'texts', 'node_groups')


def owned(data):
    data[OWNER] = True
    return data


def settings():
    """Retain the user's Phase 2 switches and speed across an additive rebuild."""
    result = {key: True for key in SWITCHES}
    result['ECS_FLOW_SPEED'] = 1.0
    ctrl = bpy.data.objects.get(CONTROLLER)
    if ctrl and ctrl.get(OWNER):
        for key in SWITCHES:
            if key in ctrl:
                result[key] = bool(ctrl[key])
        value = ctrl.get('ECS_FLOW_SPEED', 1.0)
        if isinstance(value, (int, float)) and math.isfinite(value):
            result['ECS_FLOW_SPEED'] = max(0.0, min(5.0, float(value)))
    return result


def clear(scene, overview_root):
    """Remove only our IDs, refusing to discard custom users or foreign content."""
    reserved_objects = {CONTROLLER, *CAMERAS}
    for side in ('LEFT', 'RIGHT'):
        reserved_objects.update({'DUCT_BLEED_'+side, 'PRECOOLER_'+side, 'PACK_'+side})
        reserved_objects.update('FLOW_'+side+'_'+kind for kind in flow.COLORS)
        reserved_objects.update('PACK_'+side+'_'+suffix for suffix in ('INPUT', 'OUTPUT', 'DISCHARGE'))
        reserved_objects.update('PRECOOLER_'+side+'_'+suffix for suffix in ('INPUT', 'OUTPUT'))
    owned_ids = set()
    for category in ID_CATEGORIES:
        for data in getattr(bpy.data, category):
            if data.get(OWNER):
                owned_ids.add(data)
            elif (data.name.startswith('ECS P2 | ') or
                  (category == 'objects' and data.name in reserved_objects) or
                  (category == 'collections' and data.name in {COLLECTION, *GROUPS}) or
                  (category == 'texts' and data.name == 'ECS_PHASE2_README')):
                raise RuntimeError('Phase 2 name is occupied by unowned content: '+data.name)
    for data in owned_ids:
        if isinstance(data, bpy.types.Collection):
            if any(item not in owned_ids for item in (*data.objects, *data.children)):
                raise RuntimeError('Custom content inside Phase 2 collection: '+data.name)
    # Blender's ID user map catches external parents, constraints, driver targets,
    # shared materials/meshes, and collection instances, not only scene membership.
    embedded_trees = {data.node_tree for data in owned_ids
                      if isinstance(data, (bpy.types.Material, bpy.types.World)) and data.node_tree}
    for data, users in bpy.data.user_map(subset=owned_ids).items():
        for user in users:
            if user in owned_ids or user in embedded_trees:
                continue
            if data.name == COLLECTION and user == overview_root:
                continue
            # The ID map also reports indirect scene membership for objects.
            # Only this existing scene is a permitted owner of the new layer.
            if user == scene:
                continue
            raise RuntimeError('Phase 2 data is used outside its layer: '+data.name+' by '+user.name)
    if owned_ids:
        bpy.data.batch_remove(ids=tuple(owned_ids))


def controller(collection, values):
    ctrl = owned(bpy.data.objects.new(CONTROLLER, None))
    collection.objects.link(ctrl)
    ctrl.empty_display_type = 'PLAIN_AXES'
    ctrl.empty_display_size = .12
    ctrl['Phase'] = '2 | Engine bleed to independent pack outputs'
    ctrl['Flow control'] = 'Manual documentary flow. Apparent speed in metres/second.'
    ctrl['Future valve source'] = 'ECS ENG | CTRL_ENGINE["BLEED_VALVE_OPEN"]'
    for key in SWITCHES:
        ctrl[key] = values[key]
        ctrl.id_properties_ui(key).update(description=key.replace('_', ' ').capitalize())
    ctrl['ECS_FLOW_SPEED'] = values['ECS_FLOW_SPEED']
    ctrl.id_properties_ui('ECS_FLOW_SPEED').update(
        min=0.0, max=5.0, soft_min=0.0, soft_max=2.5,
        description='Apparent metres/second along the duct. Zero stops markers.')
    return ctrl


def inspection_cameras(collection):
    for name, (location, target, scale) in CAMERAS.items():
        data = owned(bpy.data.cameras.new(name))
        data.type = 'ORTHO'
        data.ortho_scale = scale
        data.clip_start, data.clip_end = .03, 500.0
        obj = owned(bpy.data.objects.new(name, data))
        collection.objects.link(obj)
        obj.location = location
        obj.rotation_euler = (Vector(target)-obj.location).to_track_quat('-Z', 'Y').to_euler()


def embed_texts():
    directory = Path(__file__).resolve().parent
    script = bpy.data.texts.get('ECS_OVERVIEW_CONTROL.py')
    if script is None:
        raise RuntimeError('The existing ECS sidebar text is missing')
    script.clear()
    script.write((directory/'ecs_overview_control.py').read_text(encoding='utf-8'))
    script.use_module = True
    readme = owned(bpy.data.texts.new('ECS_PHASE2_README'))
    readme.write((directory.parent/'docs'/'ECS_PHASE2.md').read_text(encoding='utf-8'))
    readme.use_fake_user = True
    launcher = bpy.data.texts.get('run_all.py') or bpy.data.texts.new('run_all.py')
    launcher.clear()
    launcher.write((directory.parent/'run_all.py').read_text(encoding='utf-8'))
    launcher.filepath = str(directory.parent/'run_all.py')


def build():
    scene = bpy.data.scenes.get(SCENE)
    overview_root = bpy.data.collections.get('ECS_OVERVIEW')
    if scene is None or overview_root is None or overview_root.name not in scene.collection.children:
        raise RuntimeError('Generate the existing ECS overview Phase 1 before adding Phase 2')
    for name in ('CTRL_ECS_OVERVIEW', 'ECS ENG | CTRL_ENGINE',
                 'ECS BLEED | LEFT OUTLET', 'ECS BLEED | RIGHT OUTLET'):
        if bpy.data.objects.get(name) is None:
            raise RuntimeError('Required existing Phase 1 asset is missing: '+name)
    previous_scene = bpy.context.window.scene
    previous_camera = scene.camera.name if scene.camera else None
    values = settings()
    try:
        bpy.context.window.scene = scene
        clear(scene, overview_root)
        root = owned(bpy.data.collections.new(COLLECTION))
        root['Phase'] = '2 | Pneumatic ducts, precoolers and packs'
        overview_root.children.link(root)
        groups = {}
        for name in GROUPS:
            groups[name] = owned(bpy.data.collections.new(name))
            root.children.link(groups[name])
        ctrl = controller(groups['PHASE2_HELPERS'], values)
        bpy.context.view_layer.update()
        result = geometry.build(scene, groups, ctrl)
        flow.build(scene, groups, ctrl, result['flows'])
        inspection_cameras(groups['PHASE2_HELPERS'])
        embed_texts()
        bpy.context.view_layer.update()
        if previous_camera:
            scene.camera = bpy.data.objects[previous_camera]
        return scene
    finally:
        bpy.context.window.scene = previous_scene

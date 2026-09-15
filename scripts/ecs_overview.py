"""Phase 1: scene-safe aircraft presentation and two reused CFM56 instances.

Geometry comes from the existing saved assets, never from a second model builder.
Coordinates retain the aircraft convention: metres, +X aft, +Y starboard, +Z up.
"""
import math
from pathlib import Path

import bpy
from mathutils import Vector
import geometry as g
import ecs_installed_bleed as installed_bleed

SCENE = '08 | ECS_OVERVIEW'
COLLECTION = 'ECS_OVERVIEW'
TEMPLATE = 'ECS_ENGINE_TEMPLATE'
OWNER = 'ecs_overview_asset'
SCRIPT = 'ECS_OVERVIEW_CONTROL.py'
GROUPS = ('AIRCRAFT_OVERVIEW','ENGINES_OVERVIEW','OVERVIEW_GUIDES',
          'OVERVIEW_CAMERAS','OVERVIEW_LIGHTS','OVERVIEW_HELPERS')
ENGINE_GROUPS = ('ENGINE_STATIC','ENGINE_NACELLE','ENGINE_N1','ENGINE_N2',
                 'ENGINE_COMBUSTOR','ENGINE_BLEED','ENGINE_CONTROLS')
MOUNTS = {'ENGINE_LEFT_OVERVIEW':(11.,-4.83,1.60),
          'ENGINE_RIGHT_OVERVIEW':(11.,4.83,1.60)}
WIREFRAME_THICKNESS = .005
WIREFRAME_COLOR = (.045,.26,.39)


def owned(data):
    # Object/data copies must not inherit source generator ownership.
    if 'cfm56_asset' in data:
        del data['cfm56_asset']
    data[OWNER] = True
    return data


def scene_collections(scene):
    return {scene.collection,*scene.collection.children_recursive}


def clear():
    scene = bpy.data.scenes.get(SCENE)
    root = bpy.data.collections.get(COLLECTION)
    for item in (scene,root,bpy.data.collections.get(TEMPLATE)):
        if item and not item.get(OWNER):
            raise RuntimeError('Refusing to replace unowned overview name: '+item.name)
    objects = {o for o in bpy.data.objects if o.get(OWNER)}
    collections = {c for c in bpy.data.collections if c.get(OWNER)}
    if scene and any(o not in objects for o in scene.objects):
        raise RuntimeError('Overview scene contains custom objects; preserve them separately before rebuilding')
    if scene and any(c not in collections for c in scene.collection.children_recursive):
        raise RuntimeError('Overview scene contains custom collections; preserve them separately before rebuilding')
    for other in bpy.data.scenes:
        if other!=scene and (scene_collections(other)&collections or any(o.name in other.objects for o in objects)):
            raise RuntimeError('Overview content is linked into another scene: '+other.name)
    for obj in bpy.data.objects:
        if obj not in objects and obj.instance_collection in collections:
            raise RuntimeError('Overview template is used outside the overview: '+obj.name)
    for col in collections:
        if any(o not in objects for o in col.objects):
            raise RuntimeError('Custom object in overview-owned collection: '+col.name)
        if any(c not in collections for c in col.children):
            raise RuntimeError('Custom collection in overview-owned collection: '+col.name)
    if objects:
        bpy.data.batch_remove(ids=tuple(objects))
    if collections:
        bpy.data.batch_remove(ids=tuple(collections))
    if scene:
        bpy.data.scenes.remove(scene)
    for blocks in (bpy.data.meshes,bpy.data.curves,bpy.data.cameras,bpy.data.lights,
                   bpy.data.materials,bpy.data.worlds,bpy.data.actions):
        for data in list(blocks):
            if data.get(OWNER) and data.users==0:
                blocks.remove(data)


def empty(name, collection, location=(0,0,0), parent=None):
    obj = owned(bpy.data.objects.new(name,None))
    collection.objects.link(obj)
    obj.location = location
    obj.parent = parent
    obj.empty_display_size = .45
    return obj


def hide_driver(obj, ctrl, prop):
    for path in ('hide_render','hide_viewport'):
        fc = obj.driver_add(path)
        fc.driver.type = 'SCRIPTED'
        var = fc.driver.variables.new()
        var.name = 'show'
        var.targets[0].id = ctrl
        var.targets[0].data_path = '["'+prop+'"]'
        fc.driver.expression = 'not show'


def property_driver(data, path, ctrl, property_path, index=None):
    """Native simple expressions also work when script auto-execution is off."""
    fc = data.driver_add(path) if index is None else data.driver_add(path,index)
    fc.driver.type = 'SCRIPTED'
    var = fc.driver.variables.new()
    var.name = 'value'
    var.targets[0].id = ctrl
    var.targets[0].data_path = property_path
    fc.driver.expression = 'value'


def wireframe_material_controls(mat, ctrl):
    owned(mat.node_tree)
    bsdf = mat.node_tree.nodes['Principled BSDF']
    for index in range(3):
        path = '["WIREFRAME_COLOR"]['+str(index)+']'
        property_driver(mat,'diffuse_color',ctrl,path,index)
        for socket in ('Base Color','Emission Color'):
            property_driver(bsdf.inputs[socket],'default_value',ctrl,path,index)


def wireframe_state():
    """Keep saved wire settings when updating this scene alone."""
    ctrl = bpy.data.objects.get('CTRL_ECS_OVERVIEW')
    thickness, color = WIREFRAME_THICKNESS, WIREFRAME_COLOR
    if ctrl and ctrl.get(OWNER):
        value = ctrl.get('WIREFRAME_THICKNESS',thickness)
        if isinstance(value,(int,float)) and math.isfinite(value):
            thickness = max(.001,min(.025,float(value)))
        value = ctrl.get('WIREFRAME_COLOR',color)
        if hasattr(value,'__len__') and len(value)==3 and all(
                isinstance(c,(int,float)) and math.isfinite(c) for c in value):
            color = tuple(max(0.,min(1.,float(c))) for c in value)
    return thickness,color


def material(name,color,alpha=1.,emission=0.):
    mat = owned(g.material('ECS | '+name,color,.2,.42,emission))
    if alpha<1:
        nodes, links = mat.node_tree.nodes,mat.node_tree.links
        bsdf = nodes.get('Principled BSDF')
        transparent = nodes.new('ShaderNodeBsdfTransparent')
        mix = nodes.new('ShaderNodeMixShader')
        mix.inputs[0].default_value = alpha
        links.new(transparent.outputs[0],mix.inputs[1])
        links.new(bsdf.outputs[0],mix.inputs[2])
        # The technical shell should not cast opaque shadows onto the engines.
        light_path = nodes.new('ShaderNodeLightPath')
        shadows = nodes.new('ShaderNodeMixShader')
        links.new(light_path.outputs['Is Shadow Ray'],shadows.inputs[0])
        links.new(mix.outputs[0],shadows.inputs[1])
        links.new(transparent.outputs[0],shadows.inputs[2])
        links.new(shadows.outputs[0],nodes.get('Material Output').inputs['Surface'])
        mat.diffuse_color = (*color,alpha)
        mat.surface_render_method = 'DITHERED'
    return mat


def override_material(obj, mat):
    # Object-linked slots do not change the shared master mesh's material list.
    if not obj.material_slots:
        # Isolated private fallback for a source asset with no material slots.
        source_data = obj.data
        obj.data = owned(source_data.copy())
        obj.data.name = 'ECS AIR DATA | '+source_data.name
        obj.data['ecs_source_data'] = source_data.name
        obj.data.materials.append(mat)
    for slot in obj.material_slots:
        slot.link = 'OBJECT'
        slot.material = mat


def aircraft(groups,ctrl,mats):
    source = bpy.data.collections['B737_300_EXTERIOR']
    parent = empty('AIRCRAFT_OVERVIEW_ROOT',groups['AIRCRAFT_OVERVIEW'],parent=ctrl)
    parent['ecs_source_collection'] = source.name
    legacy = set(bpy.data.collections['05_Engines_CFM56_3'].all_objects)
    sources = [o for o in source.all_objects if o.type in {'MESH','CURVE'}
               and (o not in legacy or o.name.startswith('Engine pylon_'))]
    sources = [o for o in sources if not o.name.startswith(('Static discharge','Pitot',
               'Dorsal VHF','Ventral antenna','Door handle','Door hinge','Door sill'))]
    copies = []
    for src in sources:
        obj = owned(src.copy())
        obj.name = 'ECS AIR | '+src.name
        obj['ecs_source_object'] = src.name
        obj['ecs_source_data'] = src.data.name
        obj.animation_data_clear()
        groups['AIRCRAFT_OVERVIEW'].objects.link(obj)
        obj.parent = parent
        obj.matrix_parent_inverse.identity()
        obj.matrix_world = src.matrix_world.copy()
        obj.hide_render = obj.hide_viewport = False
        # The two original pylons belong to the older, larger stylized nacelles.
        # Change only four lower vertices on a private overview mesh, retaining
        # all upper attachment points and the original aircraft/engine mounts.
        if src.name.startswith('Engine pylon_'):
            obj.data = owned(src.data.copy())
            obj.data.name = 'ECS AIR DATA | '+src.data.name
            obj.data['ecs_source_data'] = src.data.name
            obj['ecs_adaptation'] = 'Pylon lower attachment: vertices 0,5 z=2.40; 4,9 z=1.97'
            for index,z in ((0,2.40),(5,2.40),(4,1.97),(9,1.97)):
                obj.data.vertices[index].co.z = z
            obj.data.update()
            mat = mats['pylon']
        elif src.type=='CURVE':
            mat = mats['seam']
        elif src.name.startswith(('Window_','Cockpit pane_')):
            mat = mats['window']
        elif '06_LandingGear' in {c.name for c in src.users_collection}:
            mat = mats['gear']
        else:
            mat = mats['shell']
        override_material(obj,mat)
        hide_driver(obj,ctrl,'SHOW_SHELL')
        copies.append(obj)
        # Existing sparse seam curves complement a reduced display-only lattice.
        if src.name=='Fuselage | continuous quad loft' or src.name.startswith((
                'Wing main box_','Vertical fin with dorsal fillet','Horizontal stabilizer')):
            wire = owned(src.copy())
            wire.name = 'ECS WIRE | '+src.name
            wire['ecs_source_object'] = src.name
            wire['ecs_source_data'] = src.data.name
            wire.animation_data_clear()
            groups['AIRCRAFT_OVERVIEW'].objects.link(wire)
            wire.parent = parent
            wire.matrix_parent_inverse.identity()
            wire.matrix_world = src.matrix_world.copy()
            override_material(wire,mats['wire'])
            reduce = wire.modifiers.new('Overview display lattice density','DECIMATE')
            reduce.decimate_type = 'UNSUBDIV'
            reduce.iterations = 6 if src.name.startswith('Fuselage') else 4
            lattice = wire.modifiers.new('Overview non-destructive wireframe','WIREFRAME')
            lattice.thickness = WIREFRAME_THICKNESS
            property_driver(lattice,'thickness',ctrl,'["WIREFRAME_THICKNESS"]')
            lattice.use_replace = True
            # Tiny closing faces at the nose have acute angles: even-offset
            # compensation would amplify those into long protruding spikes.
            lattice.use_even_offset = False
            lattice.offset = 0.
            hide_driver(wire,ctrl,'SHOW_WIREFRAME')
    return copies


def engine_template(scene):
    """Detach presentation data once; preserve linked blades inside the template."""
    template = owned(bpy.data.collections.new(TEMPLATE))
    template['ecs_source_collection'] = 'CFM56_3_ENGINE'
    template['purpose'] = 'One source-derived presentation asset, reused by both installed instances'
    objects, data_cache, materials = {},{},{}
    sources = [o for name in ENGINE_GROUPS for o in bpy.data.collections[name].objects]
    for src in sources:
        obj = owned(src.copy())
        obj.name = 'ECS ENG | '+src.name
        obj['ecs_source_object'] = src.name
        template.objects.link(obj)
        objects[src] = obj
        if obj.animation_data and obj.animation_data.action:
            obj.animation_data.action = None
        if src.data:
            if src.data not in data_cache:
                data = owned(src.data.copy())
                data.name = 'ECS ENG DATA | '+src.data.name
                data['ecs_source_data'] = src.data.name
                if hasattr(data,'materials'):
                    for index,src_mat in enumerate(src.data.materials):
                        if not src_mat:
                            continue
                        if src_mat not in materials:
                            mat = owned(src_mat.copy())
                            mat.name = 'ECS ENG MAT | '+src_mat.name
                            mat['ecs_source_material'] = src_mat.name
                            materials[src_mat] = mat
                        data.materials[index] = materials[src_mat]
                data_cache[src.data] = data
            obj.data = data_cache[src.data]
            obj['ecs_source_data'] = src.data.name
        for index,slot in enumerate(obj.material_slots):
            if slot.link=='OBJECT' and slot.material:
                src_mat = slot.material
                if src_mat not in materials:
                    mat = owned(src_mat.copy())
                    mat.name = 'ECS ENG MAT | '+src_mat.name
                    mat['ecs_source_material'] = src_mat.name
                    materials[src_mat] = mat
                slot.material = materials[src_mat]
    for src,obj in objects.items():
        obj.parent = objects.get(src.parent)
        if obj.animation_data:
            for fc in obj.animation_data.drivers:
                for var in fc.driver.variables:
                    for target in var.targets:
                        if isinstance(target.id,bpy.types.Object):
                            if target.id not in objects:
                                raise RuntimeError('Unexpected external engine driver: '+obj.name)
                            target.id = objects[target.id]
                        elif isinstance(target.id,bpy.types.Scene):
                            target.id = scene
        for constraint in obj.constraints:
            if hasattr(constraint,'target') and constraint.target:
                if constraint.target not in objects:
                    raise RuntimeError('Unexpected external engine constraint: '+obj.name)
                constraint.target = objects[constraint.target]
    ctrl = objects[bpy.data.objects['CTRL_ENGINE']]
    for key,value in dict(N1_SPEED=12.,N2_SPEED=30.,N1_PHASE=0.,N2_PHASE=0.,
                          CUTAWAY_MODE=False,SHOW_NACELLE=True,SHOW_INTERNALS=True,
                          SHOW_AIRFLOW=False,SHOW_LABELS=False,BLEED_VALVE_OPEN=0.,BLEED_SOURCE=0).items():
        ctrl[key] = value
    ctrl['Overview operation'] = 'Both installed instances share these presentation controls; source engine remains independent'
    ctrl.update_tag()
    installed_bleed.configure_template(template)
    return template


def setup_guides(groups,ctrl):
    guide_col = groups['OVERVIEW_GUIDES']
    outlets = {side:Vector(MOUNTS['ENGINE_'+side+'_OVERVIEW'])+Vector(point)
               for side,point in installed_bleed.OUTLET_POINTS.items()}
    for name,location in [('LEFT_BLEED_START',outlets['LEFT']),
                           ('RIGHT_BLEED_START',outlets['RIGHT']),
                           ('FORWARD_SYSTEM_SPACE',(11.8,0,2.1)),
                           ('CABIN_CORRIDOR_START',(5.7,0,3.25)),
                           ('CABIN_CORRIDOR_END',(26.2,0,3.25)),
                           ('AFT_STUDY_AREA',(27.7,0,2.65))]:
        obj = empty('ECS GUIDE | '+name,guide_col,location,parent=ctrl)
        obj.hide_render = True
        obj.empty_display_type = 'ARROWS'
        obj['purpose'] = 'Planning guide only; no equipment, duct or operational connection'
    data = owned(bpy.data.curves.new('ECS GUIDE | Future camera travel','CURVE'))
    data.dimensions = '3D'
    spline = data.splines.new('BEZIER')
    points = [(-5,-13,8),(8,-9,4),(12,-4.8,1.8),(13,0,3.3),(23,0,3.3),(29,0,4)]
    spline.bezier_points.add(len(points)-1)
    for point,co in zip(spline.bezier_points,points):
        point.co = co
        point.handle_left_type = point.handle_right_type = 'AUTO'
    route = owned(bpy.data.objects.new(data.name,data))
    guide_col.objects.link(route)
    route.hide_render = True
    route.parent = ctrl
    route['purpose'] = 'Unanimated camera planning path only; not an airflow route'
    route.data.path_duration = 240


def camera(name,location,target,scale,collection):
    data = owned(bpy.data.cameras.new(name))
    obj = owned(bpy.data.objects.new(name,data))
    collection.objects.link(obj)
    obj.location = location
    obj.rotation_euler = (Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler()
    data.type = 'ORTHO'
    data.ortho_scale = scale
    data.clip_start,data.clip_end = .02,500
    return obj


def build():
    old_scene = bpy.context.window.scene.name
    saved_thickness,saved_color = wireframe_state()
    for name in ('B737_300_EXTERIOR','CFM56_3_ENGINE',*ENGINE_GROUPS):
        if name not in bpy.data.collections:
            raise RuntimeError('Build existing aircraft and CFM56 first; missing '+name)
    reserved = {'CTRL_ECS_OVERVIEW','AIRCRAFT_OVERVIEW_ROOT',*MOUNTS,SCRIPT,'ECS_OVERVIEW_README','ECS_OVERVIEW_WORLD'}
    prefixes = ('ECS AIR','ECS ENG','ECS WIRE','ECS BLEED','ECS GUIDE','ECS LIGHT','ECS |','CAM_OVERVIEW_')
    for blocks in (bpy.data.objects,bpy.data.meshes,bpy.data.curves,bpy.data.cameras,
                   bpy.data.lights,bpy.data.materials,bpy.data.worlds,bpy.data.texts):
        for item in blocks:
            if not item.get(OWNER) and (item.name in reserved or item.name.startswith(prefixes)):
                raise RuntimeError('Refusing to replace unowned overview name: '+item.name)
    clear()
    for name in (COLLECTION,TEMPLATE,*GROUPS):
        if bpy.data.collections.get(name):
            raise RuntimeError('Overview collection name collision: '+name)
    scene = owned(bpy.data.scenes.new(SCENE))
    bpy.context.window.scene = scene
    scene.unit_settings.system = 'METRIC'
    scene['Phase'] = '1 — overview base only; no aircraft ECS equipment or network'
    scene['Sources'] = 'Existing B737_300_EXTERIOR and CFM56_3_ENGINE'
    scene['Axis'] = 'Metres; X aft, Y starboard, Z up'
    root = owned(g.collection(COLLECTION))
    groups = {name:owned(g.collection(name,root)) for name in GROUPS}
    ctrl = empty('CTRL_ECS_OVERVIEW',groups['OVERVIEW_HELPERS'])
    for key in ('SHOW_SHELL','SHOW_WIREFRAME'):
        ctrl[key] = True
        ctrl.id_properties_ui(key).update(default=True,description='Overview presentation only')
    ctrl['WIREFRAME_THICKNESS'] = saved_thickness
    ctrl.id_properties_ui('WIREFRAME_THICKNESS').update(
        min=.001,max=.025,soft_min=.001,soft_max=.015,default=WIREFRAME_THICKNESS,
        subtype='DISTANCE',description='Overview wire width in metres; 0.005 m = 5 mm')
    ctrl['WIREFRAME_COLOR'] = saved_color
    ctrl.id_properties_ui('WIREFRAME_COLOR').update(
        min=0.,max=1.,subtype='COLOR',default=WIREFRAME_COLOR,
        description='Overview wire material RGB color; independent of the aircraft shell')
    mats = dict(shell=material('Transparent aircraft shell',(.10,.34,.48),.105),
                window=material('Window silhouettes',(.12,.55,.70),.19,.25),
                wire=material('Structural wire',WIREFRAME_COLOR,1.,.3),
                seam=material('Existing panel seams',(.10,.32,.45),.45,.25),
                gear=material('Muted landing gear',(.12,.20,.27),.36),
                pylon=material('Engine mounting pylons',(.22,.36,.44),.65))
    wireframe_material_controls(mats['wire'],ctrl)
    print('ECS: Reuse aircraft exterior with scene-specific display materials',flush=True)
    aircraft(groups,ctrl,mats)
    print('ECS: Derive one engine template and create two installed instances',flush=True)
    template = engine_template(scene)
    instances = {}
    for name,position in MOUNTS.items():
        obj = empty(name,groups['ENGINES_OVERVIEW'],position,parent=ctrl)
        obj.instance_type = 'COLLECTION'
        obj.instance_collection = template
        obj['ecs_source_collection'] = 'CFM56_3_ENGINE'
        obj['mount_axis'] = '+X aft; unscaled engine on the existing aircraft engine axis'
        instances[name] = obj
    installed_bleed.build(groups['ENGINES_OVERVIEW'],instances,bpy.data.objects['ECS ENG | CTRL_ENGINE'])
    setup_guides(groups,ctrl)
    target = (16.2,0,3.4)
    for name,loc,scale in [('CAM_OVERVIEW_WIDE',(-15,-38,35),42.),
                            ('CAM_OVERVIEW_3Q',(-17,-35,18),40.),
                            ('CAM_OVERVIEW_SIDE',(16.2,-65,9),38.)]:
        cam = camera(name,loc,target,scale,groups['OVERVIEW_CAMERAS'])
        if name=='CAM_OVERVIEW_WIDE':
            scene.camera = cam
    camera('CAM_OVERVIEW_ENGINE_STUDY',(3,-13,6),(12.5,-4.83,1.8),13.,groups['OVERVIEW_CAMERAS'])
    for name,loc,aim,power,size,color in [
            ('KEY',(8,-10,22),target,9000,16,(.65,.83,1)),
            ('RIM',(24,10,17),target,11000,15,(.22,.58,1)),
            ('FILL',(-6,1,10),(11,0,2),4500,12,(.8,.9,1)),
            ('LEFT_ENGINE',(8,-7,6),(12,-4.83,1.6),700,4,(1,.82,.58)),
            ('RIGHT_ENGINE',(8,7,6),(12,4.83,1.6),700,4,(1,.82,.58))]:
        data = owned(bpy.data.lights.new('ECS LIGHT | '+name,'AREA'))
        data.energy,data.size,data.color = power,size,color
        obj = owned(bpy.data.objects.new(data.name,data))
        groups['OVERVIEW_LIGHTS'].objects.link(obj)
        obj.location = loc
        obj.rotation_euler = (Vector(aim)-obj.location).to_track_quat('-Z','Y').to_euler()
    world = owned(bpy.data.worlds.new('ECS_OVERVIEW_WORLD'))
    world.use_nodes = True
    world.node_tree.nodes['Background'].inputs[0].default_value = (.008,.019,.032,1)
    world.node_tree.nodes['Background'].inputs[1].default_value = .35
    scene.world = world
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 48
    scene.cycles.use_denoising = True
    scene.cycles.transparent_max_bounces = 24
    scene.render.resolution_x,scene.render.resolution_y = 1600,1000
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.fps = 24
    scene.frame_start,scene.frame_end = 1,240
    scene.view_settings.view_transform = 'AgX'
    script = bpy.data.texts.get(SCRIPT) or bpy.data.texts.new(SCRIPT)
    script.clear()
    script.write(Path(__file__).with_name('ecs_overview_control.py').read_text(encoding='utf-8'))
    script.use_module = True
    owned(script)
    readme = bpy.data.texts.get('ECS_OVERVIEW_README') or bpy.data.texts.new('ECS_OVERVIEW_README')
    readme.clear()
    readme.write((Path(__file__).parents[1]/'docs'/'ECS_OVERVIEW.md').read_text(encoding='utf-8'))
    owned(readme)
    bpy.context.view_layer.update()
    if old_scene in bpy.data.scenes:
        bpy.context.window.scene = bpy.data.scenes[old_scene]
    g.COL = None
    return scene

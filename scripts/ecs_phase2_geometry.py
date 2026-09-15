"""Installed Phase 2 pneumatic equipment, in metres (X aft, +Y right).

This is a documentary reconstruction fitted to the existing visual airframe,
not maintenance or manufacturing geometry. Only Phase 2 IDs are created here;
the orchestrator owns cleanup. No operators, source edits, or file saves.
"""
import json
import math

import bpy
from mathutils import Vector

OWNER = 'ecs_phase2_asset'
PREFIX = 'ECS P2 | '
SIDES = {'LEFT': -1., 'RIGHT': 1.}
PRECOOLER_CENTER = (15.30, 4.08, 2.16)
PACK_CENTER = (13.60, .93, 2.02)
PIPE_RADII = {'HOT_BLEED': .047, 'PRECOOLED': .055, 'PACK_OUTPUT': .070}
PRECOOLER_INPUT_INDEX = 4
PACK_INPUT_INDEX = 7

# Coordinates describe the right installation. Each side is independently
# constructed from the actual corresponding Phase 1 handoff; positive object
# scales keep the mechanical winding and visible flange faces correct.
HOT_POINTS = ((14.8, 4.83, 2.23), (15.04, 4.83, 2.23),
              (15.24, 4.69, 2.19), (15.30, 4.54, 2.16),
              (15.30, 4.46, 2.16), (15.30, 4.08, 2.16),
              (15.30, 3.70, 2.16), (15.30, 3.62, 2.16))
PRECOOLED_POINTS = ((15.30, 3.62, 2.16), (15.30, 3.40, 2.16),
                    (15.14, 3.18, 2.15), (14.85, 2.80, 2.13),
                    (14.60, 2.25, 2.08), (14.55, 1.75, 2.07),
                    (14.52, 1.35, 2.06), (14.35, 1.08, 2.06),
                    (14.05, 1.08, 2.06), (13.65, 1.08, 2.06),
                    (13.43, 1.08, 2.06), (13.18, 1.08, 2.06),
                    (12.98, .98, 2.08), (12.95, .85, 2.15),
                    (12.84, .65, 2.18),
                    (12.70, .65, 2.18))
OUTPUT_POINTS = ((12.70, .65, 2.18), (12.45, .65, 2.18),
                 (12.12, .65, 2.18))


def owned(data):
    data[OWNER] = True
    return data


def world_point(point, side):
    return (point[0], SIDES[side]*point[1], point[2])


def visibility(obj, ctrl, group, side):
    obj['ecs_phase2_side'] = side
    obj['ecs_phase2_group'] = group
    for prop in ('hide_viewport', 'hide_render'):
        driver = obj.driver_add(prop).driver
        driver.type = 'SCRIPTED'
        for name, control in (('group', group), ('side', 'SHOW_'+side)):
            variable = driver.variables.new()
            variable.name = name
            variable.type = 'SINGLE_PROP'
            variable.targets[0].id = ctrl
            variable.targets[0].data_path = '["'+control+'"]'
        driver.expression = 'not (group and side)'


def object_new(name, data, collection, ctrl, group, side, role, parent=None):
    if bpy.data.objects.get(name):
        raise RuntimeError('Phase 2 object name is already occupied: '+name)
    obj = owned(bpy.data.objects.new(name, data))
    collection.objects.link(obj)
    obj.parent = parent
    obj['ecs_phase2_role'] = role
    visibility(obj, ctrl, group, side)
    return obj


def material(label, rgb, metal=.75, roughness=.32, ctrl=None, ghost=False):
    mat = owned(bpy.data.materials.new(PREFIX+label))
    mat.diffuse_color = (*rgb, 1.)
    mat.use_nodes = True
    owned(mat.node_tree)
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    shader = nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (*rgb, 1.)
    shader.inputs['Metallic'].default_value = metal
    shader.inputs['Roughness'].default_value = roughness
    if ghost:
        transparent = nodes.new('ShaderNodeBsdfTransparent')
        blend = nodes.new('ShaderNodeMixShader')
        blend.name = 'Airflow inspection transparency'
        links.new(shader.outputs['BSDF'], blend.inputs[1])
        links.new(transparent.outputs[0], blend.inputs[2])
        links.new(blend.outputs[0], nodes.get('Material Output').inputs['Surface'])
        driver = blend.inputs[0].driver_add('default_value').driver
        driver.type = 'SCRIPTED'
        variable = driver.variables.new()
        variable.name = 'flow'
        variable.type = 'SINGLE_PROP'
        variable.targets[0].id = ctrl
        variable.targets[0].data_path = '["SHOW_AIRFLOW"]'
        driver.expression = '.86 if flow else 0.0'
    return mat


def mesh_object(name, vertices, faces, mat, context, role, smooth=False):
    collection, ctrl, group, side, parent = context
    data = owned(bpy.data.meshes.new(name))
    data.from_pydata(vertices, [], faces)
    data.materials.append(mat)
    data.update()
    if smooth:
        for poly in data.polygons:
            poly.use_smooth = True
    return object_new(name, data, collection, ctrl, group, side, role, parent)


def box(label, center, dimensions, mat, context, role='CASING', bevel=.008):
    cx, cy, cz = center
    dx, dy, dz = (d/2 for d in dimensions)
    verts = [(cx+x*dx, cy+y*dy, cz+z*dz)
             for x,y,z in ((-1,-1,-1),(-1,-1,1),(-1,1,-1),(-1,1,1),
                           (1,-1,-1),(1,-1,1),(1,1,-1),(1,1,1))]
    faces = ((0,4,6,2),(1,3,7,5),(0,1,5,4),(2,6,7,3),(0,2,3,1),(4,5,7,6))
    obj = mesh_object(PREFIX+context[3]+' '+label, verts, faces, mat, context, role)
    if bevel:
        modifier = obj.modifiers.new('Machined edge', 'BEVEL')
        modifier.width, modifier.segments = bevel, 2
    return obj


def lathe(label, start, end, profile, mat, context, role='MACHINERY', segments=48):
    """Closed radial profile around an arbitrary axis; annular profiles open bore."""
    a, b = Vector(start), Vector(end)
    axis = (b-a).normalized()
    ref = Vector((0, 0, 1)) if abs(axis.z)<.9 else Vector((0, 1, 0))
    u = axis.cross(ref).normalized()
    v = axis.cross(u).normalized()
    vertices, faces = [], []
    for along, radius in profile:
        center = a+axis*along
        for index in range(segments):
            angle = index*2*math.pi/segments
            vertices.append(center+radius*(u*math.cos(angle)+v*math.sin(angle)))
    for band in range(len(profile)):
        next_band = (band+1)%len(profile)
        for index in range(segments):
            nxt = (index+1)%segments
            faces.append((band*segments+index,band*segments+nxt,
                          next_band*segments+nxt,next_band*segments+index))
    return mesh_object(PREFIX+context[3]+' '+label, vertices, faces, mat, context, role, True)


def tube(label, start, end, radius, mat, context, role='INTERFACE', thickness=.006):
    length = (Vector(end)-Vector(start)).length
    return lathe(label, start, end, ((0,radius),(length,radius),
                 (length,radius-thickness),(0,radius-thickness)), mat, context, role)


def flange(label, point, direction, radius, mat, context):
    a = Vector(point)-Vector(direction).normalized()*.013
    b = a+Vector(direction).normalized()*.026
    return tube(label, a, b, radius+ .019, mat, context, 'FLANGE', .022)


def bezier_handles(points):
    points = [Vector(point) for point in points]
    result = []
    for index, point in enumerate(points):
        if index == 0:
            tangent = (points[1]-point).normalized()
            length = (points[1]-point).length/3
        elif index == len(points)-1:
            tangent = (point-points[index-1]).normalized()
            length = (point-points[index-1]).length/3
        else:
            before, after = point-points[index-1], points[index+1]-point
            tangent = (before.normalized()+after.normalized()).normalized()
            length = min(before.length, after.length)/3
        result.append((tuple(point-tangent*length), tuple(point+tangent*length)))
    return result


def duct(name, points, kind, mat, context):
    data = owned(bpy.data.curves.new(name, 'CURVE'))
    data.dimensions = '3D'
    data.resolution_u = 24
    data.bevel_depth = PIPE_RADII[kind]
    data.bevel_resolution = 4
    data.use_fill_caps = False
    data.materials.append(mat)
    spline = data.splines.new('BEZIER')
    spline.bezier_points.add(len(points)-1)
    handles = bezier_handles(points)
    for point, co, (left, right) in zip(spline.bezier_points, points, handles):
        point.co = co
        point.handle_left_type = point.handle_right_type = 'FREE'
        point.handle_left, point.handle_right = left, right
    collection, ctrl, group, side, parent = context
    obj = object_new(name, data, collection, ctrl, group, side, 'DUCT', parent)
    obj['ecs_phase2_kind'] = kind
    obj['ecs_phase2_path_json'] = json.dumps(points)
    obj['ecs_phase2_diameter_m'] = 2*PIPE_RADII[kind]
    return obj, {'side':side,'kind':kind,'points':points,'handles':handles,
                 'spline_type':'BEZIER','physical_object':name}


def anchor(name, point, direction, collection, ctrl, side, role):
    obj = object_new(name, None, collection, ctrl, 'SHOW_DUCTS', side, role)
    obj.location = point
    obj.rotation_euler = Vector(direction).to_track_quat('Z','Y').to_euler()
    obj.empty_display_type, obj.empty_display_size = 'ARROWS', .11
    obj['Connection'] = 'Local +Z is downstream. Static aircraft system anchor.'
    return obj


def precooler(side, collection, ctrl, mats):
    root = object_new('PRECOOLER_'+side, None, collection, ctrl, 'SHOW_PRECOOLERS',side,'PRECOOLER')
    root['Assembly'] = 'Finned engine-side bleed heat exchanger, retained in wing/pylon volume'
    context = (collection,ctrl,'SHOW_PRECOOLERS',side,root)
    p = lambda xyz: world_point(xyz,side)
    # Open exchanger grid, a pair of pressure plenums, tie rails and four lugs.
    for i in range(23):
        box('PRECOOLER exchanger fin %02d'%i,p((15.01+i*.0264,4.08,2.16)),
            (.009,.60,.25),mats['fins'],context,'HEAT_EXCHANGER_FIN',.002)
    for y, label in ((4.415,'inlet'),(3.745,'outlet')):
        box('PRECOOLER '+label+' plenum',p((15.30,y,2.16)),(.63,.075,.265),mats['casing'],context,'PLENUM',.022)
    for x in (14.965,15.635):
        box('PRECOOLER longitudinal tie rail '+str(x),p((x,4.08,2.16)),(.035,.74,.29),mats['frame'],context,'MOUNT')
    for x in (15.0,15.6):
        for y in (3.78,4.38):
            box('PRECOOLER attachment '+str((x,y)),p((x,y,2.335)),(.07,.10,.035),mats['frame'],context,'MOUNT')
    for y0,y1,label in ((4.46,4.37,'inlet neck'),(3.79,3.62,'outlet neck')):
        tube('PRECOOLER '+label,p((15.30,y0,2.16)),p((15.30,y1,2.16)),.070,mats['casing'],context)
    return root


def pack(side, collection, ctrl, mats):
    root = object_new('PACK_'+side,None,collection,ctrl,'SHOW_PACKS',side,'PACK')
    root['Assembly'] = 'Open mounted pack: primary/secondary exchangers, air-cycle machine, water separator'
    context = (collection,ctrl,'SHOW_PACKS',side,root)
    p = lambda xyz: world_point(xyz,side)
    # A load-bearing open tray; small vertical attachments reach the lower
    # fuselage structure below the existing cabin floor (2.68 m).
    for y in (.40,1.39):
        box('PACK main tray rail '+str(y),p((13.59,y,1.68)),(1.94,.048,.085),mats['frame'],context,'MOUNT')
    for x in (12.65,13.26,14.54):
        box('PACK tray crossmember '+str(x),p((x,.895,1.68)),(.048,1.0,.085),mats['frame'],context,'MOUNT')
    for x in (12.73,14.46):
        for y in (.46,1.33):
            box('PACK mount upright '+str((x,y)),p((x,y,2.07)),(.037,.037,.70),mats['frame'],context,'MOUNT')
            box('PACK airframe attachment '+str((x,y)),p((x,y,2.445)),(.14,.11,.055),mats['frame'],context,'MOUNT')
    for label,x,width in (('primary',14.17,.43),('secondary',13.63,.40)):
        for i in range(20):
            box('PACK '+label+' fin %02d'%i,p((x-width/2+i*width/19,1.07,2.035)),
                (.011,.52,.53),mats['fins'],context,'HEAT_EXCHANGER_FIN',.002)
        for z in (1.765,2.305):
            box('PACK '+label+' exchanger frame '+str(z),p((x,1.07,z)),(width+.05,.55,.035),mats['casing'],context,'CASING')
        # Narrow header manifolds leave the fin stack exposed in side-on
        # inspection; full-height side panels would conceal every fin and make
        # the exchanger read as a plain equipment box.
        for y in (.785,1.355):
            for z in (1.825,2.245):
                box('PACK '+label+' header manifold '+str((y,z)),p((x,y,z)),
                    (width+.03,.055,.10),mats['casing'],context,'PLENUM',.016)
    # Coaxial compressor and expansion turbine casings, with exposed neck and
    # mounting feet: immediately readable as an air-cycle machine, not a box.
    start,end=p((12.94,1.07,2.05)),p((13.40,1.07,2.05))
    lathe('PACK air cycle machine',start,end,
          ((0,.075),(.05,.17),(.12,.205),(.19,.205),(.23,.10),
           (.29,.10),(.32,.18),(.39,.195),(.43,.15),(.46,.07),
           (.46,.05),(0,.05)),mats['casing'],context,'AIR_CYCLE_MACHINE',64)
    for x in (13.055,13.31):
        flange('PACK ACM split casing '+str(x),p((x,1.07,2.05)),(1,0,0),.195,mats['flange'],context)
        box('PACK ACM mounting saddle '+str(x),p((x,1.07,1.78)),(.065,.35,.11),mats['frame'],context,'MOUNT')
    # Water separator body stays inside the tray and leaves a clean forward
    # conditioned-air discharge, without a Phase 3 manifold connection.
    lathe('PACK water separator',p((12.82,.65,1.78)),p((12.82,.65,2.28)),
          ((0,.065),(.05,.12),(.33,.12),(.39,.095),(.43,.06),(.43,.035),(0,.035)),
          mats['casing'],context,'WATER_SEPARATOR')
    tube('PACK separator retention band',p((12.82,.65,1.88)),p((12.82,.65,1.92)),.133,mats['flange'],context,'MOUNT',.014)
    # A low-profile actuator and short capped sensor fitting add legibility.
    tube('PACK inlet valve housing',p((14.35,1.08,2.06)),p((14.53,1.27,2.06)),.089,mats['casing'],context,'PACK_VALVE',.010)
    box('PACK valve actuator',p((14.405,1.20,2.225)),(.13,.11,.095),mats['dark'],context,'ACTUATOR',.016)
    return root


def build(scene, groups, ctrl):
    """Create only Phase 2 geometry; return exact matching flow centerlines."""
    if ctrl is None or not ctrl.get(OWNER):
        raise RuntimeError('Phase 2 geometry requires a private Phase 2 controller')
    mats = dict(
        duct=material('Warm stainless ducts',(.40,.34,.26),.82,.28,ctrl,True),
        casing=material('Aluminium equipment casings',(.43,.48,.49),.78,.31,ctrl,True),
        fins=material('Heat exchanger fins',(.25,.30,.31),.85,.35,ctrl,True),
        frame=material('Mounting rails',(.18,.23,.20),.55,.38),
        flange=material('Couplings and fasteners',(.52,.54,.50),.88,.26),
        dark=material('Actuator graphite',(.035,.045,.049),.40,.36))
    result = {'flows':[], 'endpoints':{}, 'components':{}}
    for side in SIDES:
        source = bpy.data.objects.get('ECS BLEED | '+side+' OUTLET')
        if source is None or source.name not in scene.objects:
            raise RuntimeError('Missing installed Phase 1 bleed handoff for '+side)
        p = lambda xyz: world_point(xyz,side)
        hot = [p(point) for point in HOT_POINTS]
        hot[0] = tuple(source.matrix_world.translation)
        tangent = (source.matrix_world.to_3x3()@Vector((0,0,1))).normalized()
        hot[1] = tuple(Vector(hot[0])+tangent*.24)
        cool = [p(point) for point in PRECOOLED_POINTS]
        output = [p(point) for point in OUTPUT_POINTS]
        context = (groups['PNEUMATIC_DUCTS'],ctrl,'SHOW_DUCTS',side,None)
        names = {'HOT_BLEED':'DUCT_BLEED_'+side,
                 'PRECOOLED':PREFIX+side+' PRECOOLED DUCT',
                 'PACK_OUTPUT':PREFIX+side+' PACK OUTPUT DUCT'}
        ducts = {}
        for kind, points in (('HOT_BLEED',hot),('PRECOOLED',cool),('PACK_OUTPUT',output)):
            obj, record = duct(names[kind],points,kind,mats['duct'],context)
            obj['ecs_phase2_source_connector'] = source.name
            result['flows'].append(record)
            ducts[kind] = obj
            # Rings at accessible joints; all are real open bores.
            indices = (0,3,len(points)-1) if kind=='HOT_BLEED' else ((0,3,6,len(points)-1) if kind=='PRECOOLED' else (0,len(points)-1))
            for index in indices:
                vec = Vector(points[min(index+1,len(points)-1)])-Vector(points[max(0,index-1)])
                flange(kind+' coupling %02d'%index,points[index],vec,PIPE_RADII[kind],mats['flange'],context)
        ducts['HOT_BLEED']['ecs_phase2_precooler_input_index'] = PRECOOLER_INPUT_INDEX
        ducts['PRECOOLED']['ecs_phase2_pack_input_index'] = PACK_INPUT_INDEX
        cooler = precooler(side,groups['PRECOOLERS'],ctrl,mats)
        machine = pack(side,groups['PACKS'],ctrl,mats)
        # Local hangers attach the wing duct at span stations inside the skin.
        for i in (2,4):
            point = Vector(cool[i])
            box('PNEUMATIC wing saddle %02d'%i,tuple(point+Vector((0,0,.093))),(.16,.13,.055),mats['frame'],context,'MOUNT')
        anchors = {
            'PRECOOLER_'+side+'_INPUT':(hot[PRECOOLER_INPUT_INDEX],(0,-SIDES[side],0),'PRECOOLER_INPUT'),
            'PRECOOLER_'+side+'_OUTPUT':(hot[-1],Vector(cool[1])-Vector(cool[0]),'PRECOOLER_OUTPUT'),
            'PACK_'+side+'_INPUT':(cool[PACK_INPUT_INDEX],(-1,0,0),'PACK_INPUT'),
            'PACK_'+side+'_DISCHARGE':(cool[-1],(-1,0,0),'PACK_DISCHARGE'),
            'PACK_'+side+'_OUTPUT':(output[-1],(-1,0,0),'PACK_OUTPUT')}
        for name,(point,direction,role) in anchors.items():
            anchor(name,point,direction,groups['PHASE2_HELPERS'],ctrl,side,role)
        result['endpoints'][side] = {name:tuple(value[0]) for name,value in anchors.items()}
        result['components'][side] = {'precooler':cooler.name,'pack':machine.name,
                                       'source':source.name,'ducts':names}
    return result

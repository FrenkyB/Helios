"""HEL-5: isolated CFM56-3 presentation asset. Metres; +X intake to exhaust.

Stage counts follow the Boeing CFM56-3 AMM. Airfoil shapes, section stations,
duct routing and nacelle contours are visual reconstructions, not service CAD.
"""
import math
from pathlib import Path

import bpy
from mathutils import Vector
import geometry as g

SCENE = '07 | CFM56_ENGINE'
COLLECTION = 'CFM56_3_ENGINE'
OWNER = 'cfm56_asset'
SCRIPT = 'CFM56_ENGINE_CONTROL.py'
GROUPS = ('ENGINE_STATIC', 'ENGINE_NACELLE', 'ENGINE_N1', 'ENGINE_N2',
          'ENGINE_COMBUSTOR', 'ENGINE_BLEED', 'ENGINE_AIRFLOW', 'ENGINE_CONTROLS',
          'ENGINE_LABELS', 'ENGINE_CAMERAS', 'ENGINE_LIGHTS')
DEFAULTS = dict(N1_SPEED=12., N2_SPEED=30., BLEED_VALVE_OPEN=1., BLEED_SOURCE=0,
                SHOW_NACELLE=True, SHOW_INTERNALS=True, SHOW_AIRFLOW=False,
                SHOW_LABELS=False, CUTAWAY_MODE=True, N1_PHASE=0., N2_PHASE=0.)
STATIONS = dict(INTAKE=0., FAN=.39, LPC=.72, HPC=1.09, COMBUSTOR=2.02,
                HPT=2.43, LPT=2.61, EXHAUST=3.17)
TAU = 2 * math.pi


def driver(obj, path, ctrl, expression, properties, index=None):
    fc = obj.driver_add(path) if index is None else obj.driver_add(path, index)
    fc.driver.type = 'SCRIPTED'
    for variable, prop in properties.items():
        var = fc.driver.variables.new()
        var.name = variable
        var.type = 'SINGLE_PROP'
        var.targets[0].id = ctrl
        var.targets[0].data_path = '["' + prop + '"]'
    fc.driver.expression = expression
    return fc


def visibility(obj, ctrl, expression, properties):
    for path in ('hide_render', 'hide_viewport'):
        driver(obj, path, ctrl, expression, properties)


def empty(name, parent=None, location=(0, 0, 0)):
    obj = bpy.data.objects.new(name, None)
    g.COL.objects.link(obj)
    obj.location = location
    obj.parent = parent
    obj.empty_display_size = .13
    return obj


def shell(name, profile, mat, quadrant=None, thickness=.015, flattened=False):
    """Closed thickness section; complete engine is four reversible quadrants."""
    start, end = (0, TAU) if quadrant is None else (quadrant*math.pi/2, (quadrant+1)*math.pi/2)
    n = 128 if quadrant is None else 32
    section = list(profile) + [(x, r-thickness) for x, r in reversed(profile)]
    verts = []
    for x, r in section:
        for j in range(n+1):
            a = start+(end-start)*j/n
            z = r*math.sin(a)
            if flattened:
                # Classic nacelle: circular fan clearance, flattened external keel.
                z = max(z, -.805 + (profile[0][1]-r)*.05)
            verts.append((x, r*math.cos(a), z))
    faces = []
    m = n+1
    for k in range(len(section)):
        nk = (k+1) % len(section)
        for j in range(n):
            faces.append((k*m+j, k*m+j+1, nk*m+j+1, nk*m+j))
    if quadrant is not None:
        faces += [tuple(k*m for k in reversed(range(len(section)))),
                  tuple(k*m+n for k in range(len(section)))]
    obj = g.mesh(name, verts, faces, mat)
    # Keep the cut boundaries and end annuli crisp rather than smoothing them
    # into the cylindrical skin, which makes thin shells look inflated.
    for poly in obj.data.polygons:
        band = poly.index//n
        if band in (len(profile)-1,len(section)-1) or poly.index >= len(section)*n:
            poly.use_smooth = False
    obj.data.set_sharp_from_angle(angle=math.radians(38))
    return obj


def blade_mesh(name, x, root, tip, chord, sweep, twist, mat):
    """Cambered, twisted, closed airfoil with an elliptical leading edge."""
    rings = []
    for j in range(9):
        s = j/8
        r = root+(tip-root)*s
        width = chord*(.73+.32*math.sin(math.pi*s)-.18*s)
        ring = []
        for i in range(24):
            a = TAU*i/24
            u = (1-math.cos(a))/2
            thick = .075*width*math.sin(a)*(1-.65*u)
            camber = .095*width*math.sin(math.pi*u)
            axial = (u-.5)*width
            tangent = thick+camber
            angle = twist*(1-.64*s)
            ring.append((x+axial*math.cos(angle)-tangent*math.sin(angle)+.07*s*s*sweep,
                         r, axial*math.sin(angle)+tangent*math.cos(angle)+sweep*s*s))
        rings.append(ring)
    return g.loft(name, rings, mat)


def row(name, x, root, tip, chord, count, mat, parent, sweep=.025, twist=.65):
    first = blade_mesh(name+'_BLADE_01', x, root, tip, chord, sweep, twist, mat)
    first.parent = parent
    for i in range(1, count):
        obj = bpy.data.objects.new(name+f'_BLADE_{i+1:02}', first.data)
        g.COL.objects.link(obj)
        obj.parent = parent
        obj.rotation_euler.x = TAU*i/count
    return first


def tube(name, points, mat, radius=.022):
    # Smooth interpolated route with explicit end tangents for later connection.
    obj = g.curve(name, points, mat, radius)
    spline = obj.data.splines[0]
    coords = [tuple(p.co[:3]) for p in spline.points]
    obj.data.splines.remove(spline)
    spline = obj.data.splines.new('BEZIER')
    spline.bezier_points.add(len(coords)-1)
    for p, co in zip(spline.bezier_points, coords):
        p.co = co
        p.handle_left_type = p.handle_right_type = 'AUTO'
    obj.data.resolution_u = 16
    return obj


def clear():
    root = bpy.data.collections.get(COLLECTION)
    if root and not root.get(OWNER):
        raise RuntimeError('Refusing to replace unowned collection '+COLLECTION)
    scene = bpy.data.scenes.get(SCENE)
    if scene and not scene.get(OWNER):
        raise RuntimeError('Refusing to replace unowned scene '+SCENE)
    if root:
        owned = set(root.all_objects)
        if scene and (any(o not in owned for o in scene.objects)
                      or any(c != root for c in scene.collection.children)):
            raise RuntimeError('Engine scene contains custom content; move it to a separate scene before regeneration')
        if any(o.name in s.objects for s in bpy.data.scenes if s != scene for o in owned):
            raise RuntimeError('Engine linked into another scene; unlink before regeneration')
        for obj in list(owned):
            if not obj.get(OWNER):
                raise RuntimeError('Unowned object in engine collection: '+obj.name)
        # Avoid rebuilding Blender's dependency graph for every linked blade.
        # The verified ownership boundary above remains identical.
        bpy.data.batch_remove(ids=tuple(owned))
        bpy.data.batch_remove(ids=tuple(root.children_recursive)+(root,))
    if scene:
        bpy.data.scenes.remove(scene)
    for blocks in (bpy.data.meshes, bpy.data.curves, bpy.data.cameras, bpy.data.lights,
                   bpy.data.worlds, bpy.data.materials, bpy.data.actions):
        for data in list(blocks):
            if data.users == 0 and data.get(OWNER):
                blocks.remove(data)


def build():
    previous_name = bpy.context.window.scene.name
    previous_col = g.COL
    clear()
    for name in ('CTRL_ENGINE', 'ROT_N1', 'ROT_N2', *GROUPS):
        if bpy.data.objects.get(name) or bpy.data.collections.get(name):
            raise RuntimeError('Engine name collides with existing content: '+name)
    scene = bpy.data.scenes.new(SCENE)
    scene[OWNER] = True
    bpy.context.window.scene = scene
    scene.unit_settings.system = 'METRIC'
    scene['Axis'] = '+X intake to exhaust; Y=Z=0 spool centreline; metres'
    scene['Reference'] = 'turbofan_engine.png; CFM56-3 Boeing AMM 72-00-00 stage arrangement'
    scene['Geometry scope'] = '1.524 m fan; 3.4 m illustrated envelope; approximate section stations and plumbing'
    scene['Stage order'] = 'FAN / 3 LPC / 9 HPC / annular combustor / 1 HPT / 4 LPT / exhaust'
    root = g.collection(COLLECTION)
    root[OWNER] = True
    groups = {name: g.collection(name, root) for name in GROUPS}
    for col in groups.values():
        col[OWNER] = True
    g.use(groups['ENGINE_CONTROLS'])
    ctrl = empty('CTRL_ENGINE')
    for key, value in DEFAULTS.items():
        ctrl[key] = value
        desc = {'N1_SPEED':'N1 RPM. Keyframe then Bake RPM animation for speed ramps.',
                'N2_SPEED':'N2 RPM. Independent from N1. Small RPM values give documentary slow motion.',
                'BLEED_SOURCE':'0: stage 5 primary; 1: stage 9 high pressure selection',
                'CUTAWAY_MODE':'Remove camera-facing shell quadrants reversibly',
                'N1_PHASE':'Generated integral correction; use Bake RPM animation',
                'N2_PHASE':'Generated integral correction; use Bake RPM animation'}.get(key, key)
        if isinstance(value, bool):
            ctrl.id_properties_ui(key).update(default=value, description=desc)
        else:
            low, high = (-1e12, 1e12) if 'PHASE' in key else (0., 15000. if 'SPEED' in key else 1.)
            if isinstance(value, int):
                low, high = int(low), int(high)
            ctrl.id_properties_ui(key).update(min=low, max=high, default=value, description=desc)
    ctrl['Integration outlet'] = 'BLEED_OUTLET_TO_AIRCRAFT at (2.70,-0.64,-0.72), local +Z points aft (+X)'
    n1 = empty('ROT_N1', ctrl)
    n2 = empty('ROT_N2', ctrl)
    for spool, prop in ((n1, 'N1'), (n2, 'N2')):
        spool.rotation_mode = 'XYZ'
        fc = driver(spool, 'rotation_euler', ctrl,
                    '-(rpm*(frame-1)*fpsbase/fps*0.10471975511966+phase)',
                    {'rpm':prop+'_SPEED', 'phase':prop+'_PHASE'}, 0)
        for name, path in (('fps','render.fps'), ('fpsbase','render.fps_base')):
            v = fc.driver.variables.new()
            v.name = name
            v.targets[0].id_type = 'SCENE'
            v.targets[0].id = scene
            v.targets[0].data_path = path
    mats = {}
    for name, color, metal, rough in (
            ('nacelle',(.49,.55,.58),.8,.25), ('lip',(.65,.70,.73),.92,.2),
            ('casing',(.055,.072,.083),.8,.34), ('compressor',(.29,.38,.43),.88,.28),
            ('fan',(.17,.22,.25),.88,.24), ('hub',(.065,.084,.1),.7,.28),
            ('shaft_n1',(.10,.25,.36),.8,.26), ('shaft_n2',(.23,.34,.20),.8,.26),
            ('combustor',(.33,.20,.095),.85,.33), ('hot',(.25,.14,.11),.8,.3),
            ('bleed',(.56,.29,.075),.8,.26), ('fastener',(.48,.52,.53),.85,.22),
            ('dark',(.014,.024,.032),.4,.43), ('label',(.45,.72,.83),.05,.45)):
        mats[name] = g.material('CFM56 | '+name, color, metal, rough)
        mats[name][OWNER] = True
    for name, color in [('intake',(.005,.24,1)), ('bypass',(.005,.65,1)),
                         ('core',(.02,.45,.9)), ('compressed',(.12,.8,1)),
                         ('combustion',(1,.16,.005)), ('exhaust',(1,.018,.075)),
                         ('bleed_flow',(1,.39,.008))]:
        mats[name] = g.material('CFM56 | '+name, color, .15, .3, 2.5)
        mats[name][OWNER] = True
    # First establish blockout and coaxial shaft architecture, before blade detail.
    g.use(groups['ENGINE_N1'])
    shell('LP_SHAFT_N1',[(.25,.078),(3.19,.078)],mats['shaft_n1'],thickness=.018).parent = n1
    for name, start, end in [('LPC_HUB_DRUM_N1',.70,1.00),('LPT_HUB_DRUM_N1',2.62,3.12)]:
        shell(name,[(start,.158),(end,.158)],mats['shaft_n1'],thickness=.083).parent = n1
    shell('FAN_HUB_N1',[(.045,.008),(.12,.09),(.25,.20),(.49,.255),(.64,.235)],
          mats['hub'],thickness=.006).parent = n1
    spiral = []
    for i in range(120):
        t = i/119
        r = .018+.156*t
        x = .045+(r-.008)*(.075/.082) if r<.09 else .12+(r-.09)*(.13/.11)
        a = TAU*1.6*t
        spiral.append((x-.004,r*math.cos(a),r*math.sin(a)))
    g.curve('FAN_SPINNER_SPIRAL_N1',spiral,mats['label'],.004).parent = n1
    g.use(groups['ENGINE_N2'])
    shell('HP_SHAFT_N2',[(1.035,.125),(2.59,.125)],mats['shaft_n2'],thickness=.022).parent = n2
    shell('HPC_HUB_DRUM_N2',[(1.08,.158),(2.51,.158)],mats['shaft_n2'],thickness=.036).parent = n2
    g.use(groups['ENGINE_STATIC'])
    for i, x in enumerate((.66,1.02,2.58,3.15)):
        shell(f'BEARING_SUPPORT_{i+1}',[(x-.022,.18),(x+.022,.18)],mats['fastener'],thickness=.032)
    # The real Classic has 38 fan blades, with midspan snubbers.
    g.use(groups['ENGINE_N1'])
    row('FAN_N1',.405,.25,.762,.235,38,mats['fan'],n1,sweep=-.09,twist=1.05)
    for i in range(38):
        a = TAU*(i+.5)/38
        obj = g.cube(f'FAN_SNUBBER_{i+1:02}',(.432,.526*math.cos(a),.526*math.sin(a)),
                     (.046,.012,.084),mats['compressor'],.003)
        obj.rotation_euler.x = a
        obj.parent = n1
    stages = [('LPC',3,.73,.095,.25,.44,n1,'ENGINE_N1'),
              ('HPC',9,1.115,.096,.23,.36,n2,'ENGINE_N2'),
              ('HPT',1,2.465,.1,.22,.39,n2,'ENGINE_N2'),
              ('LPT',4,2.655,.125,.20,.43,n1,'ENGINE_N1')]
    for section, count, start, pitch, hub, tip, parent, group in stages:
        for j in range(count):
            x = start+j*pitch
            r = tip-(.065*j/max(1,count-1) if section=='HPC' else 0)
            hot = section in ('HPT','LPT')
            g.use(groups[group])
            name = f'{section}_ROTOR_N{1 if parent==n1 else 2}_STAGE{j+1:02}'
            shell(name+'_DISK',[(x-.028,hub+.012),(x+.028,hub+.012)],
                  mats['hot' if hot else 'compressor'],thickness=hub-.145).parent = parent
            row(name,x,hub,r,pitch*.59,46 if hot else 40+j*2,
                mats['hot' if hot else 'compressor'],parent,sweep=.015,twist=.72)
            g.use(groups['ENGINE_STATIC'])
            # Turbine nozzle vanes guide flow into each rotor from upstream.
            stator_x = x-pitch*.45 if hot else x+pitch*.51
            row(f'{section}_STATOR_STAGE{j+1:02}',stator_x,hub+.007,r+.007,
                pitch*.32,36,mats['casing'],None,sweep=-.012,twist=-.7)
    # Reversible casing segments, including flange seams and fasteners.
    g.use(groups['ENGINE_STATIC'])
    profiles = [('FAN_CASE',[(.29,.79),(.62,.80)]),
                ('BOOSTER_CASE',[(.64,.48),(1.045,.46)]),
                ('HPC_CASE',[(1.055,.397),(1.99,.32)]),
                ('COMBUSTOR_CASE',[(2.00,.34),(2.11,.425),(2.39,.425),(2.43,.41)]),
                ('TURBINE_CASE',[(2.44,.44),(2.59,.47),(3.16,.49)])]
    for name, profile in profiles:
        for q in range(4):
            obj = shell(name+f'_Q{q+1}',profile,mats['casing'],q)
            obj['cutaway_shell'] = q in (1,2)
        for end, (x,r) in enumerate((profile[0],profile[-1])):
            for q in range(4):
                obj = shell(name+f'_FLANGE_{end}_Q{q+1}',[(x-.013,r+.025),(x+.013,r+.025)],
                            mats['fastener'],q,.024)
                obj['cutaway_shell'] = q in (1,2)
            for k in range(24):
                a = TAU*k/24
                obj = g.cylinder(name+f'_BOLT_{end}_{k:02}',
                                 (x-.019,(r+.012)*math.cos(a),(r+.012)*math.sin(a)),
                                 (x+.019,(r+.012)*math.cos(a),(r+.012)*math.sin(a)),
                                 .009,mats['fastener'],6)
                obj['cutaway_shell'] = math.cos(a)<0
    # Annular, stationary combustor: two liners, dome, separate fuel injectors.
    g.use(groups['ENGINE_COMBUSTOR'])
    for q in range(4):
        obj = shell(f'COMBUSTOR_OUTER_LINER_Q{q+1}',[(2.04,.32),(2.11,.37),(2.39,.37)],
                    mats['combustor'],q,.012)
        obj['cutaway_shell'] = q in (1,2)
        shell(f'COMBUSTOR_INNER_LINER_Q{q+1}',[(2.04,.19),(2.13,.205),(2.39,.205)],
              mats['combustor'],q,.012)
    for k in range(20):
        a = TAU*k/20
        g.cylinder(f'FUEL_INJECTOR_{k+1:02}',(2.015,.29*math.cos(a),.29*math.sin(a)),
                   (2.12,.29*math.cos(a),.29*math.sin(a)),.019,mats['fastener'],16,r2=.009)
    # Cooling perforations are small inset dark disks with metal collars.
    for j in range(6):
        for k in range(20):
            a = TAU*(k+.5*(j%2))/20
            if math.cos(a)<0:
                continue
            x = 2.14+j*.043
            g.cylinder(f'LINER_COOLING_HOLE_{j}_{k}',(x,.369*math.cos(a),.369*math.sin(a)),
                       (x,.373*math.cos(a),.373*math.sin(a)),.007,mats['dark'],12)
    # Static outlet guide vanes and exhaust cone.
    g.use(groups['ENGINE_STATIC'])
    row('EXHAUST_SUPPORT',3.18,.145,.45,.11,8,mats['casing'],None,sweep=0,twist=0)
    shell('EXHAUST_CONE',[(3.10,.19),(3.27,.145),(3.4,.012)],mats['hot'],thickness=.009)
    # Nacelle has a rounded polished intake and Classic flattened lower contour.
    g.use(groups['ENGINE_NACELLE'])
    for name, profile, material, thick in [
            ('NACELLE_INTAKE',[(-.035,.786),(-.065,.806),(-.03,.845),(.045,.86),(.21,.856),(.29,.842)],'lip',.018),
            ('NACELLE_FAN_COWL',[(.29,.842),(.64,.865),(.95,.82),(1.31,.765)],'nacelle',.028),
            ('NACELLE_REVERSER',[(1.31,.765),(1.72,.685),(2.12,.585),(2.38,.535)],'nacelle',.026),
            ('CORE_COWLING',[(2.38,.49),(2.84,.51),(3.17,.505)],'casing',.021),
            ('EXHAUST_CASING',[(3.17,.505),(3.32,.465)],'lip',.019)]:
        for q in range(4):
            obj = shell(name+f'_Q{q+1}',profile,mats[material],q,thick,flattened=True)
            obj['cutaway_shell'] = q in (1,2)
    # Bypass exit is an annulus around the core, rather than a tube into HPC.
    g.use(groups['ENGINE_STATIC'])
    for k in range(12):
        a = TAU*k/12
        obj = g.cube(f'FAN_FRAME_STRUT_{k+1:02}',(.655,.625*math.cos(a),.625*math.sin(a)),
                     (.13,.27,.024),mats['casing'],.01)
        obj.rotation_euler.x = a
    # Flattened-nacelle accessory gearbox and short service harnesses.
    gear = g.cube('ACCESSORY_GEARBOX',(.87,.48,-.42),(.42,.22,.16),mats['casing'],.04)
    for k in range(3):
        g.cylinder(f'ACCESSORY_DRIVE_{k}',(.72+k*.13,.49,-.44),(.72+k*.13,.65,-.44),
                   .055,mats['fastener'],24)
    for k in range(4):
        a = -.3+k*.22
        tube(f'SERVICE_LINE_{k}',[(.65,.46,a),(1.1,.44,a),(1.8,.36,a),(2.2,.44,a)],mats['fastener'],.007)
    # Required stage-5 and stage-9 taps align with their actual HPC stages.
    g.use(groups['ENGINE_BLEED'])
    routes = {}
    for stage in (5,9):
        x = 1.115+(stage-1)*.096
        radius = .36-.065*(stage-1)/8
        y = -(radius+.015)
        port = g.cylinder(f'BLEED_STAGE{stage}_PORT',(x,y+.025,-.03),(x,y-.075,-.03),
                          .039,mats['bleed'],32)
        port['HPC_stage'] = stage
        routes[stage] = [(x,y-.075,-.03),(x,-.52,-.13),(x+.07,-.63,-.57),
                         (2.05 if stage==5 else 2.15,-.64,-.72)]
        tube(f'BLEED_DUCT_STAGE{stage}',routes[stage],mats['bleed'],.027)
    tube('BLEED_MANIFOLD_ENGINE',[(2.02,-.64,-.72),(2.18,-.64,-.72),(2.32,-.64,-.72)],mats['bleed'],.047)
    # Stage selection is a presentation control; inlet check/HP valve are distinct.
    for name, x in [('STAGE5_CHECK_VALVE',1.57),('STAGE9_HP_VALVE',1.97)]:
        g.sphere(name,(x,-.60,-.48),(.055,.055,.085),mats['casing'],24,12)
    shell_valve = shell('BLEED_VALVE_ENGINE',[(2.32,.069),(2.47,.069)],mats['fastener'],0,.012)
    shell_valve.location.yz = (-.64,-.72)
    # Other quarters allow inspection of butterfly while preserving its housing.
    for q in (1,2,3):
        obj = shell(f'BLEED_VALVE_HOUSING_Q{q+1}',[(2.32,.069),(2.47,.069)],mats['fastener'],q,.012)
        obj.location.yz = (-.64,-.72)
        if q in (1,2):
            visibility(obj,ctrl,'cut',{'cut':'CUTAWAY_MODE'})
    pivot = empty('BLEED_VALVE_PIVOT',ctrl,(2.395,-.64,-.72))
    disk = g.cylinder('BLEED_VALVE_BUTTERFLY',(-.005,0,0),(.005,0,0),.053,mats['bleed'],48)
    disk.parent = pivot
    driver(pivot,'rotation_euler',ctrl,'v*1.57079632679',{'v':'BLEED_VALVE_OPEN'},2)
    stem = g.cylinder('BLEED_VALVE_STEM',(2.395,-.64,-.80),(2.395,-.64,-.59),.009,mats['fastener'],16)
    g.cube('BLEED_VALVE_ACTUATOR',(2.395,-.64,-.565),(.10,.11,.07),mats['casing'],.012)
    arm = g.cube('BLEED_VALVE_INDICATOR',(0,.028,.143),(.018,.068,.012),mats['bleed'],.003)
    arm.parent = pivot
    tube('BLEED_OUTLET_STUB',[(2.47,-.64,-.72),(2.70,-.64,-.72)],mats['bleed'],.047)
    outlet = empty('BLEED_OUTLET_TO_AIRCRAFT',ctrl,(2.70,-.64,-.72))
    outlet.rotation_euler.y = math.pi/2
    outlet.empty_display_type = 'ARROWS'
    outlet['Connection'] = 'Local +Z downstream; diameter 0.094 m; terminates here'
    flange = shell('BLEED_OUTLET_FLANGE',[(2.685,.066),(2.705,.066)],mats['fastener'],thickness=.02)
    flange.location.yz = (-.64,-.72)
    # All flow is separate and independently hideable, with moving arrowheads.
    g.use(groups['ENGINE_AIRFLOW'])
    flows = [('FLOW_INTAKE',[(-.45,-.38,.26),(.23,-.38,.26)],'intake',None),
             ('FLOW_BYPASS',[(.50,-.45,.58),(.95,-.40,.61),(1.5,-.37,.48),(2.38,-.26,.40)],'bypass',None),
             ('FLOW_CORE',[(.50,-.30,.05),(.8,-.35,.05),(1.07,-.31,.05)],'core',None),
             ('FLOW_COMPRESSED',[(1.09,-.33,.08),(1.60,-.28,.08),(2.04,-.265,.08)],'compressed',None),
             ('FLOW_COMBUSTION',[(2.08,-.30,.03),(2.27,-.32,.05),(2.43,-.29,.04)],'combustion',None),
             ('FLOW_EXHAUST',[(2.62,-.32,.14),(3.15,-.36,.15),(3.76,-.35,.15)],'exhaust',None),
             ('FLOW_BLEED_STAGE5',routes[5],'bleed_flow',5),
             ('FLOW_BLEED_STAGE9',routes[9],'bleed_flow',9),
             ('FLOW_BLEED_OUTPUT',[(2.18,-.69,-.72),(2.4,-.69,-.72),(2.82,-.69,-.72)],'bleed_flow',0)]
    for name, points, material, source in flows:
        # Bleed overlay runs just outside the opaque physical duct for legibility.
        if source in (5,9):
            points = [(x,y-.034,z) for x,y,z in points]
        obj = tube(name,points,mats[material],.009 if source is not None else .014)
        hidden = 'not show'
        props = {'show':'SHOW_AIRFLOW'}
        if source is not None:
            props.update(valve='BLEED_VALVE_OPEN',source='BLEED_SOURCE')
            hidden += ' or valve<=0.001'
            if source in (5,9):
                hidden += ' or source!='+str(0 if source==5 else 1)
        visibility(obj,ctrl,hidden,props)
        obj.data.path_duration = 48
        for k in range(3 if source is None else 1):
            arrow = g.cylinder(name+f'_ARROW_{k+1}',(0,0,-.035),(0,0,.035),.033,
                               mats[material],16,r2=.001)
            constraint = arrow.constraints.new('FOLLOW_PATH')
            constraint.target = obj
            constraint.use_fixed_location = True
            constraint.use_curve_follow = True
            constraint.forward_axis = 'FORWARD_Z'
            constraint.up_axis = 'UP_Y'
            flow_driver = constraint.driver_add('offset_factor').driver
            flow_driver.type = 'SCRIPTED'
            flow_driver.expression = f'fmod((frame-1)/48+{k/3},1)'
            visibility(arrow,ctrl,hidden,props)
    # Local, unobtrusive optional labels; no reference image frames or logos.
    g.use(groups['ENGINE_LABELS'])
    for name, x in [('FAN',.39),('LPC',.82),('HPC',1.55),('COMBUSTOR',2.22),('HPT',2.46),('LPT',2.86)]:
        obj = g.text('LABEL_'+name,name,(x,-.10,1.04),.046,mats['label'],(math.pi/2,0,0))
        visibility(obj,ctrl,'not show',{'show':'SHOW_LABELS'})
    for name,body,loc in [('STAGE5','5TH STAGE / PRIMARY',(1.3,-.71,-.97)),
                          ('STAGE9','9TH STAGE / HIGH PRESSURE',(2.0,-.71,-1.08)),
                          ('OUTLET','ENGINE BLEED OUTLET',(2.75,-.71,-.97))]:
        obj = g.text('LABEL_'+name,body,loc,.04,mats['label'],(math.pi/2,0,0))
        visibility(obj,ctrl,'not show',{'show':'SHOW_LABELS'})
    g.use(groups['ENGINE_CAMERAS'])
    for name, loc, target, scale in [('CAM_ENGINE_TECH_SIDE',(1.65,-7.5,1.1),(1.65,0,-.03),4.45),
                                    ('CAM_ENGINE_CINEMATIC_3Q',(-3.4,-5.8,2.5),(1.55,0,0),4.65),
                                    ('CAM_ENGINE_FAN',(-4.5,-.08,.12),(.5,0,0),2.15),
                                    ('CAM_ENGINE_BLEED_DETAIL',(1.8,-3,-.15),(2,-.5,-.4),1.8)]:
        data = bpy.data.cameras.new(name)
        obj = bpy.data.objects.new(name,data)
        g.COL.objects.link(obj)
        obj.location = loc
        obj.rotation_euler = (Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler()
        data.type = 'ORTHO'
        data.ortho_scale = scale
        data.clip_start = .01
        if name=='CAM_ENGINE_TECH_SIDE':
            scene.camera = obj
    g.use(groups['ENGINE_LIGHTS'])
    for name, loc, energy, size, color in [
            ('KEY',(.4,-3,4),950,4,(.76,.88,1)), ('FILL',(2.5,-3,.4),600,3,(.65,.81,1)),
            ('RIM',(2.3,2.0,3.2),1200,3,(1,.66,.34)), ('INTAKE',(-2,-1,.5),450,2,(.75,.87,1))]:
        data = bpy.data.lights.new('CFM56_LIGHT_'+name,'AREA')
        data.energy, data.size, data.color = energy,size,color
        obj = bpy.data.objects.new(data.name,data)
        g.COL.objects.link(obj)
        obj.location = loc
        obj.rotation_euler = (Vector((1.6,0,0))-obj.location).to_track_quat('-Z','Y').to_euler()
    world = bpy.data.worlds.new('CFM56_STUDIO_WORLD')
    world[OWNER] = True
    world.use_nodes = True
    world.node_tree.nodes['Background'].inputs[0].default_value = (.013,.026,.038,1)
    world.node_tree.nodes['Background'].inputs[1].default_value = .35
    scene.world = world
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 48
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = 1600,900
    scene.render.resolution_percentage = 100
    scene.render.fps = 24
    scene.frame_start, scene.frame_end = 1,240
    scene.view_settings.view_transform = 'AgX'
    scene.render.image_settings.file_format = 'PNG'
    internals = ('ENGINE_STATIC','ENGINE_N1','ENGINE_N2','ENGINE_COMBUSTOR')
    for group, col in groups.items():
        for obj in col.objects:
            obj[OWNER] = True
            if obj.data:
                obj.data[OWNER] = True
            if obj.parent is None and obj != ctrl and obj.type not in ('CAMERA','LIGHT'):
                obj.parent = ctrl
            if group in internals:
                hidden = 'not inside'
                props = {'inside':'SHOW_INTERNALS'}
                if obj.get('cutaway_shell'):
                    hidden += ' or cut'
                    props['cut'] = 'CUTAWAY_MODE'
                visibility(obj,ctrl,hidden,props)
            elif group=='ENGINE_NACELLE':
                visibility(obj,ctrl,'not show or cut' if obj.get('cutaway_shell') else 'not show',
                           {'show':'SHOW_NACELLE','cut':'CUTAWAY_MODE'})
    script = bpy.data.texts.get(SCRIPT) or bpy.data.texts.new(SCRIPT)
    script.clear()
    script.write(Path(__file__).with_name('cfm56_engine_control.py').read_text(encoding='utf-8'))
    script.use_module = True
    script[OWNER] = True
    readme = bpy.data.texts.get('CFM56_ENGINE_README') or bpy.data.texts.new('CFM56_ENGINE_README')
    readme.clear()
    readme.write((Path(__file__).parents[1]/'docs'/'CFM56_ENGINE.md').read_text(encoding='utf-8'))
    readme[OWNER] = True
    bpy.context.view_layer.update()
    if previous_name in bpy.data.scenes:
        bpy.context.window.scene = bpy.data.scenes[previous_name]
    g.COL = previous_col if previous_col and previous_col.name in bpy.data.collections else None
    return scene

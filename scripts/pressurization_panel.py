"""Editable reference-based panel, in its own scene; metres, face in XY, +Z out.

Pixel coordinates below refer to the supplied 1088 x 1444 illustration. Physical
width is an assumed 272 mm, not a certified equipment dimension. All animation
uses native simple-expression drivers, with no Python handlers or dependencies.
"""
import math
from pathlib import Path

import bpy
from mathutils import Vector

import geometry as g

SCENE = '06 | Pressurization panel'
COLLECTION = 'B737_300_PRESSURIZATION_PANEL'
CONTROLLER = 'CTRL_PRESSURIZATION_PANEL'
SCRIPT = 'PRESSURIZATION_PANEL_CONTROL.py'
SCALE = .00025
GROUPS = ('PRESS_PANEL_BODY', 'CONTROLS', 'DISPLAYS', 'ANNUNCIATORS',
          'LABELS', 'FASTENERS', 'CONTROL_SYSTEM')
DEFAULTS = {'flight_altitude': 35000, 'landing_altitude': 0, 'mode': 0,
            'valve_position': .8, 'auto_fail': False, 'off_sched_descent': False}


def point(x, y, z=0):
    return ((x - 544) * SCALE, (722 - y) * SCALE, z)


def driver(owner, path, ctrl, prop, expression, index=None):
    if len(expression) > 255:
        raise ValueError('Panel driver expression exceeds Blender limit: '+expression)
    curve = owner.driver_add(path) if index is None else owner.driver_add(path, index)
    curve.driver.type = 'SCRIPTED'
    variable = curve.driver.variables.new()
    variable.name = 'v'
    variable.type = 'SINGLE_PROP'
    variable.targets[0].id = ctrl
    variable.targets[0].data_path = '["' + prop + '"]'
    curve.driver.expression = expression
    return curve


def attach(obj, parent):
    # Keep geometry in place while moving the local origin under its shaft.
    obj.parent = parent
    obj.location = Vector(obj.location) - parent.location
    return obj


def empty(name, xy, z=0):
    obj = bpy.data.objects.new(name, None)
    g.COL.objects.link(obj)
    obj.location = point(*xy, z)
    obj.empty_display_type = 'PLAIN_AXES'
    obj.empty_display_size = .009
    return obj


def box(name, x, y, w, h, z, depth, material, bevel=2):
    return g.cube(name, point(x, y, z), (w*SCALE, h*SCALE, depth),
                  material, bevel*SCALE)


def disk(name, x, y, radius, z, depth, material):
    obj = g.cylinder(name, point(x, y, z-depth/2), point(x, y, z+depth/2),
                     radius*SCALE, material, 64)
    g.bevel(obj, .00035, 2)
    return obj


def label(name, body, x, y, size, material, z=.008):
    obj = g.text('LABEL_' + name, body, point(x, y, z), size*SCALE, material)
    obj.data.align_y = 'CENTER'
    obj.data.space_line = .9
    obj.data.extrude = .000035
    obj.data.bevel_depth = .00001
    return obj


def line(name, a, b, width, material, z=.008):
    return g.curve(name, [point(*a, z), point(*b, z)], material, width*SCALE/2)


def polygon(name, coords, z, depth, material):
    verts = [point(x, y, layer) for layer in (z-depth/2, z+depth/2) for x, y in coords]
    n = len(coords)
    faces = [tuple(range(n-1, -1, -1)), tuple(range(n, 2*n))]
    faces += [(i, (i+1) % n, (i+1) % n+n, i+n) for i in range(n)]
    return g.mesh(name, verts, faces, material, smooth=False)


def clear():
    old = bpy.data.collections.get(COLLECTION)
    if old:
        children = list(old.children_recursive)
        for obj in list(old.all_objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        for col in reversed(children):
            bpy.data.collections.remove(col)
        bpy.data.collections.remove(old)
    scene = bpy.data.scenes.get(SCENE)
    if scene:
        bpy.data.scenes.remove(scene)
    for mat in list(bpy.data.materials):
        if mat.name.startswith('PRESS |'):
            bpy.data.materials.remove(mat)
    # Remove only orphaned panel data left by the previous generation.
    for datablocks in (bpy.data.meshes, bpy.data.curves, bpy.data.cameras, bpy.data.lights, bpy.data.worlds):
        for data in list(datablocks):
            if data.users == 0 and data.get('press_panel_asset'):
                datablocks.remove(data)


def build():
    previous = bpy.context.window.scene
    previous_name = previous.name
    clear()
    scene = bpy.data.scenes.new(SCENE)
    bpy.context.window.scene = scene
    scene.unit_settings.system = 'METRIC'
    scene['Reference'] = 'User supplied 737-300_pressurization_board.png, 1088 x 1444'
    scene['Dimensions'] = 'Assumed 0.272 x 0.361 m; visual reconstruction, not engineering CAD'
    scene['Operation'] = 'Animate CTRL_PRESSURIZATION_PANEL custom properties. N > Pressurization.'
    root = g.collection(COLLECTION)
    groups = {name: g.collection(name, root) for name in GROUPS}
    g.use(groups['CONTROL_SYSTEM'])
    ctrl = empty(CONTROLLER, (544, 722), -.025)
    # Master stays at world origin so all top-level coordinates remain readable.
    ctrl.location = (0, 0, 0)
    limits = {'flight_altitude': (0, 42000, 'Flight altitude in feet; display rounded to 100 ft'),
              'landing_altitude': (-1000, 14000, 'Landing altitude in feet; display rounded to 50 ft'),
              'mode': (0, 2, '0 AUTO, 1 ALTN, 2 MAN; three detents'),
              'valve_position': (0., 1., '0 CLOSED, 1 OPEN; presentation control, not a pressure simulation')}
    for key, value in DEFAULTS.items():
        ctrl[key] = value
        if key in limits:
            low, high, description = limits[key]
            ctrl.id_properties_ui(key).update(min=low, max=high, soft_min=low, soft_max=high,
                                              description=description, default=value)
        else:
            ctrl.id_properties_ui(key).update(default=False, description='Independent warning light')

    mats = {}
    for name, color, metallic, roughness in (
            ('paint', (.115, .155, .175), .35, .4),
            ('edge', (.055, .075, .085), .5, .36),
            ('black', (.008, .011, .014), .1, .33),
            ('rubber', (.018, .022, .024), 0, .65),
            ('ivory', (.68, .68, .59), .05, .32),
            ('white', (.86, .9, .87), .05, .42),
            ('steel', (.23, .27, .28), .75, .29),
            ('blue', (.009, .023, .105), .1, .35),
            ('seal', (.24, .046, .014), .05, .46)):
        mats[name] = g.material('PRESS | ' + name, color, metallic, roughness)
    paint, edge, black, ivory, white = [mats[n] for n in ('paint', 'edge', 'black', 'ivory', 'white')]

    g.use(groups['PRESS_PANEL_BODY'])
    box('PRESS_PANEL_BODY', 544, 722, 1084, 1440, -.009, .022, edge, 10)
    box('PRESS_PANEL_ANNUNCIATOR_RAIL', 544, 76, 1050, 140, .003, .006, paint, 8)
    box('PRESS_PANEL_MAIN_FACE', 544, 604, 1050, 896, .002, .008, paint, 8)
    box('PRESS_PANEL_BLANK_LOWER', 544, 1158, 1048, 206, .002, .008, paint, 6)
    box('PRESS_PANEL_SCALE_RAIL', 544, 1350, 1050, 174, .002, .008, paint, 6)
    box('PRESS_PANEL_SCHEDULE_PLATE', 541, 1339, 918, 153, .007, .002, mats['rubber'], 15)
    # Raised cast surrounds follow the asymmetric shoulder of each display recess.
    for title, y in [('FLT', 310), ('LAND', 700)]:
        outline = [(139,y-61), (177,y-93), (211,y-100), (559,y-100),
                   (583,y-75), (583,y+57), (166,y+57), (154,y+43)]
        obj = polygon('PRESS_PANEL_' + title + '_CAST_SURROUND', outline, .007, .004, paint)
        g.bevel(obj, .002, 4)

    g.use(groups['LABELS'])
    line('LABEL_AUTO_MANUAL_DIVIDER', (627,161), (627,1048), 6, white)
    line('LABEL_MODE_DIVIDER', (628,710), (1068,710), 6, white)
    for name, body, x, y, size in [
            ('AUTO_HEADING','AUTO',381,184,50), ('MANUAL_HEADING','MANUAL',815,184,50),
            ('FLT_ALT','FLT ALT',376,420,42), ('LAND_ALT','LAND ALT',376,810,42),
            ('PLUS','+',555,527,40), ('VALVE','V\nA\nL\nV\nE',971,421,43),
            ('CLOSE','C\nL\nO\nS\nE',712,604,43), ('OPEN','O\nP\nE\nN',908,613,43),
            ('MODE_ALTN','ALTN',765,742,43), ('MODE_AUTO','AUTO',689,784,43),
            ('MODE_MAN','MAN',835,784,43),
            ('SCHEDULE_CAPTION','ALTITUDE X 1000 FEET - MAX PRESS SCHEDULE',543,1398,26),
            ('CAB','CAB',117,1316,27), ('FLT','FLT',116,1357,27)]:
        label(name, body, x, y, size, white, .009)
    for i, (a,b) in enumerate([((700,807),(718,838)), ((762,789),(761,823)), ((820,807),(804,836))]):
        line('LABEL_MODE_DETENT_' + str(i), a, b, 5, white)
    line('LABEL_SCHEDULE_BASE', (96,1335), (990,1335), 3, white, .009)
    for i in range(20):
        x = 156+i*42.7
        line('LABEL_SCHEDULE_TICK_%02d' % i, (x,1301 if i % 2 == 0 else 1312),
             (x,1354 if i % 2 == 0 else 1362), 2.5, white, .009)
    for i, (x, value) in enumerate(zip([156,241,327,412,497,583,668,754,839,925],
                                      ['10','20','22','24','26','28','31','37','41','45'])):
        label('SCHEDULE_FLT_'+str(i), value, x,1363,27,white,.009)
    for i, (x,y,value) in enumerate([(160,1281,'3'), (200,1305,'1'), (241,1281,'3'),
            (298,1305,'1'), (327,1281,'1.9'), (412,1281,'2.9'), (497,1281,'3.9'),
            (583,1281,'5.0'), (625,1306,'4.0'), (668,1281,'5.1'), (754,1281,'6.0'),
            (839,1281,'6.8'), (925,1281,'7.4'), (968,1305,'8.0')]):
        label('SCHEDULE_CAB_'+str(i),value,x,y,27,white,.009)

    g.use(groups['FASTENERS'])
    for i, (x,y) in enumerate([(54,43),(1037,43),(57,254),(1039,254),
                               (54,963),(1037,963),(54,1305),(1037,1305)]):
        prefix = 'FASTENER_QUARTER_TURN_%02d' % i
        disk(prefix+'_WELL', x,y,43,.007,.003,black)
        disk(prefix+'_RIM', x,y,36,.009,.004,mats['steel'])
        disk(prefix+'_HEAD', x,y,31,.012,.003,paint)
        box(prefix+'_SLOT',x,y,5,54,.0138,.0006,black,.6)
    for i, (x,y) in enumerate([(123,106),(979,106),(160,489),(160,920),(949,276),(923,914)]):
        prefix = 'FASTENER_CROSS_%02d' % i
        radius = 19 if y==106 else 32
        disk(prefix+'_WASHER',x,y,radius+4,.008,.002,edge)
        disk(prefix+'_HEAD',x,y,radius-3,.010,.003,mats['steel'])
        box(prefix+'_SLOT_H',x,y,26,8,.0118,.0005,black,2)
        box(prefix+'_SLOT_V',x,y,8,26,.0118,.0005,black,2)

    g.use(groups['CONTROLS'])
    for name, prop, y in [('KNOB_FLT_ALT','flight_altitude',534), ('KNOB_LAND_ALT','landing_altitude',926)]:
        knob = empty(name, (385,y), .009)
        disk(name+'_SHAFT',385,y,25,.012,.010,mats['steel'])
        attach(disk(name+'_CORE',385,y,73,.022,.023,ivory),knob)
        attach(disk(name+'_FACE',385,y,62,.035,.005,ivory),knob)
        if prop == 'landing_altitude':
            attach(disk(name+'_INNER_RING',385,y,48,.038,.003,ivory),knob)
            attach(disk(name+'_INNER_CAP',385,y,40,.040,.003,ivory),knob)
        for i in range(32):
            angle = i*math.tau/32
            tooth = box(name+'_GRIP_%02d' % i,385+72*math.cos(angle),y-72*math.sin(angle),
                        10,14,.023,.022,ivory,2)
            tooth.rotation_euler.z = angle
            attach(tooth,knob)
        # A small molded index makes changes in rotation easy to inspect.
        attach(box(name+'_INDEX',385,y-51,4,13,.038,.0006,white,1),knob)
        driver(knob,'rotation_euler',ctrl,prop,'v * 0.000628318530718',2)

    selector = empty('SELECTOR_MODE',(763,921),.012)
    disk('SELECTOR_MODE_MOUNT',763,921,98,.013,.006,black)
    attach(disk('SELECTOR_MODE_BASE',763,921,94,.023,.019,ivory),selector)
    paddle = polygon('SELECTOR_MODE_HANDLE',[(746,826),(780,826),(803,970),
                                           (805,1034),(783,1050),(741,1050),(722,1034),(724,970)],
                     .041,.025,ivory)
    # Mesh was created in world coordinates; shift its vertices to the shaft pivot.
    for vert in paddle.data.vertices:
        vert.co -= selector.location
    paddle.parent = selector
    g.bevel(paddle,.003,5)
    attach(box('SELECTOR_MODE_INDEX',763,872,8,82,.054,.0012,white,2),selector)
    driver(selector,'rotation_euler',ctrl,'mode',
           '0.523598775598 * (1 - min(2, max(0, floor(v + 0.5))))',2)

    disk('SWITCH_VALVE_WELL',812,615,48,.010,.006,black)
    disk('SWITCH_VALVE_BEZEL',812,615,41,.014,.005,mats['steel'])
    disk('SWITCH_VALVE_SEAL',812,615,34,.018,.005,mats['seal'])
    toggle = empty('SWITCH_VALVE',(812,615),.018)
    attach(disk('SWITCH_VALVE_STEM',812,615,13,.034,.032,mats['steel']),toggle)
    attach(disk('SWITCH_VALVE_GRIP',812,615,27,.054,.035,ivory),toggle)
    driver(toggle,'rotation_euler',ctrl,'valve_position','(min(1, max(0, v)) - 0.5) * 0.9',1)

    disk('INDICATOR_VALVE_OUTER',807,386,103,.011,.009,black)
    disk('INDICATOR_VALVE_BEZEL',807,386,97,.016,.006,mats['steel'])
    disk('INDICATOR_VALVE_FACE',807,386,90,.020,.004,mats['blue'])
    g.use(groups['LABELS'])
    for i in range(7):
        angle = math.radians(145-i*110/6)
        inner, outer = (64,85) if i in (0,3,6) else (71,85)
        a=(807+inner*math.cos(angle),386-inner*math.sin(angle))
        b=(807+outer*math.cos(angle),386-outer*math.sin(angle))
        line('LABEL_VALVE_TICK_'+str(i),a,b,7 if i==3 else 5,white,.023)
    g.use(groups['CONTROLS'])
    needle = empty('INDICATOR_VALVE',(807,386),.024)
    needle_mesh = polygon('INDICATOR_VALVE_NEEDLE',[(802,392),(812,392),(810,322),(807,314),(804,322)],
                          .024,.0006,white)
    for vert in needle_mesh.data.vertices:
        vert.co -= needle.location
    needle_mesh.parent = needle
    driver(needle,'rotation_euler',ctrl,'valve_position','(0.5 - min(1, max(0, v))) * 1.91986217719',2)
    # Lower semicircle hides the real needle shaft, matching the reference mask.
    outline=[(807+89*math.cos(math.radians(a)),386-89*math.sin(math.radians(a)))
             for a in range(180,361,6)]
    outline += [(896,363),(718,363)]
    polygon('INDICATOR_VALVE_LOWER_MASK',outline,.026,.003,mats['rubber'])
    for i,x in enumerate((738,876)):
        disk('FASTENER_INDICATOR_'+str(i),x,387,15,.029,.003,mats['steel'])
        box('FASTENER_INDICATOR_SLOT_H_'+str(i),x,387,19,5,.031,.0005,black,1)
        box('FASTENER_INDICATOR_SLOT_V_'+str(i),x,387,5,19,.031,.0005,black,1)
    disk('INDICATOR_VALVE_LOWER_LUG',887,471,24,.014,.012,black)
    disk('FASTENER_INDICATOR_LUG',887,471,16,.023,.005,mats['steel'])

    def luminous(name, color, prop, expression):
        material = g.material('PRESS | '+name, tuple(c*.012 for c in color), .05,.36)
        bsdf=material.node_tree.nodes['Principled BSDF']
        bsdf.inputs['Emission Color'].default_value=(*color,1)
        driver(bsdf.inputs['Emission Strength'],'default_value',ctrl,prop,expression)
        return material

    g.use(groups['ANNUNCIATORS'])
    for name,body,x,width,prop,expression,color in [
            ('ANN_AUTO_FAIL','AUTO\nFAIL',271,179,'auto_fail','3.0 if v else 0.0',(1,.18,.006)),
            ('ANN_OFF_SCHED_DESCENT','OFF SCHED\nDESCENT',462,180,'off_sched_descent','3.0 if v else 0.0',(1,.18,.006)),
            ('ANN_ALTN','ALTN',649,176,'mode','2.5 if floor(v + 0.5) == 1 else 0.0',(.035,1,.09)),
            ('ANN_MANUAL','MANUAL',858,180,'mode','2.5 if v >= 1.5 else 0.0',(.035,1,.09))]:
        box(name+'_BEZEL',x,69,width,97,.011,.012,edge,5)
        box(name+'_TRIM',x,69,width-10,85,.018,.003,mats['steel'],3)
        window=box(name,x,69,width-18,77,.020,.003,black,2)
        mat=luminous(name,color,prop,expression)
        # Unlit lettering remains readable against the dark lens.
        mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(*[c*.12 for c in color],1)
        text=label(name,body,x,69,34 if name!='ANN_OFF_SCHED_DESCENT' else 31,mat,.022)
        text.data.space_line=.95
        if prop in ('auto_fail','off_sched_descent'):
            for obj in (window,text):
                obj['warning_property']=prop

    g.use(groups['DISPLAYS'])
    # Segment convention is a,b,c,d,e,f,g clockwise from the top, then centre.
    segment_digits = ['02356789','01234789','013456789','0235689','0268','045689','2345689']
    for name,prop,y,step,low,high in [('DISPLAY_FLT_ALT','flight_altitude',310,100,0,42000),
                                   ('DISPLAY_LAND_ALT','landing_altitude',699,50,-1000,14000)]:
        parent=empty(name,(373,y),.011)
        box(name+'_OUTER',373,y,353,119,.011,.010,black,12)
        box(name+'_BEZEL',373,y,342,108,.016,.006,edge,9)
        box(name+'_LENS',373,y,284,92,.021,.004,black,8)
        quantized=f'(floor(min({high}, max({low}, v)) / {step} + 0.5) * {step})'
        for digit in range(5):
            x=270+digit*49
            number=f'fmod(floor(abs({quantized}) / {10**(4-digit)}), 10)'
            for seg in range(7):
                # Compact bit table keeps each native expression below Blender's
                # 256-character limit without custom Python functions.
                mask=sum(2**int(d) for d in segment_digits[seg])
                lit=f'fmod(floor({mask} / pow(2, {number})), 2)'
                if digit==0 and low<0:
                    lit=(f'({quantized} < 0 or ({lit}))' if seg==6
                         else f'({quantized} >= 0 and ({lit}))')
                mat=luminous(f'{name}_D{digit}_{seg}',(1,.06,.001),prop,f'4.0 if ({lit}) else 0.0')
                if seg in (0,3,6):
                    yy=y+{0:-28,3:28,6:0}[seg]
                    coords=[(x-16,yy),(x-11,yy-4),(x+11,yy-4),(x+16,yy),(x+11,yy+4),(x-11,yy+4)]
                else:
                    xx=x+(16 if seg in (1,2) else -16)
                    yy=y+(-14 if seg in (1,5) else 14)
                    coords=[(xx,yy-13),(xx+4,yy-9),(xx+4,yy+9),(xx,yy+13),(xx-4,yy+9),(xx-4,yy-9)]
                obj=polygon(f'{name}_D{digit}_{"abcdefg"[seg]}',coords,.024,.0006,mat)
                for vert in obj.data.vertices:
                    vert.co-=parent.location
                obj.parent=parent

    g.use(groups['CONTROL_SYSTEM'])
    cam_data=bpy.data.cameras.new('PRESS_PANEL_INSPECTION_CAMERA')
    cam=bpy.data.objects.new(cam_data.name,cam_data)
    g.COL.objects.link(cam)
    cam.location=(0,0,1.1)
    cam_data.type='ORTHO'
    cam_data.ortho_scale=.392
    cam_data.clip_start=.001
    scene.camera=cam
    for name,loc,power,size in [('KEY',(-.25,.3,.5),3,.45),('FILL',(.3,-.1,.4),1.5,.35)]:
        data=bpy.data.lights.new('PRESS_PANEL_LIGHT_'+name,'AREA')
        data.energy=power
        data.shape='DISK'
        data.size=size
        obj=bpy.data.objects.new(data.name,data)
        g.COL.objects.link(obj)
        obj.location=loc
        obj.rotation_euler=(-obj.location).to_track_quat('-Z','Y').to_euler()
    world=bpy.data.worlds.new('PRESS_PANEL_STUDIO_WORLD')
    world.use_nodes=True
    world.node_tree.nodes['Background'].inputs[0].default_value=(.065,.08,.10,1)
    world.node_tree.nodes['Background'].inputs[1].default_value=.3
    world['press_panel_asset']=True
    scene.world=world
    scene.render.engine='CYCLES'
    scene.cycles.samples=48
    scene.cycles.use_denoising=True
    scene.render.resolution_x=1088
    scene.render.resolution_y=1444
    scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG'
    scene.view_settings.view_transform='AgX'
    for obj in root.all_objects:
        if obj.data:
            obj.data['press_panel_asset']=True
        if obj != ctrl and obj.parent is None and obj.type not in ('CAMERA','LIGHT'):
            obj.parent=ctrl
    script=bpy.data.texts.get(SCRIPT) or bpy.data.texts.new(SCRIPT)
    script.clear()
    script.write(Path(__file__).with_name('pressurization_panel_control.py').read_text(encoding='utf-8'))
    script.use_module=True
    readme=bpy.data.texts.get('PRESSURIZATION_PANEL_README') or bpy.data.texts.new('PRESSURIZATION_PANEL_README')
    readme.clear()
    readme.write('PRESSURIZATION PANEL\n\nSeparate scene: '+SCENE+'\n'
                 'N > Pressurization > Inspect panel opens the camera and sets near clipping.\n'
                 'If the sidebar is missing, open '+SCRIPT+' in Text Editor and Run Script.\n'
                 'The UI script auto-registers only when Blender permits trusted file scripts.\n'
                 'Native drivers and Object > Custom Properties work without UI initialization.\n'
                 'Animate CTRL_PRESSURIZATION_PANEL properties, not the driven controls.\n'
                 'Flight: 0..42000 ft, rounded to 100. Landing: -1000..14000 ft, rounded to 50.\n'
                 'Five digits include leading zeroes; negative landing altitude uses a minus sign.\n'
                 'Mode 0 AUTO / 1 ALTN / 2 MAN. Valve 0 CLOSED / 1 OPEN.\n'
                 'Warnings default OFF. Sidebar toggles or Enable viewport warning clicks; Esc stops.\n'
                 'Click mode only intercepts warning windows in this scene. Other selections pass through.\n'
                 'Assumed width 272 mm, face XY, +Z outward. Reference-based visual mechanism;\n'
                 'no automatic pressure dynamics, fault detection or operational aircraft simulation.\n')
    bpy.context.view_layer.update()
    if previous_name in bpy.data.scenes:
        bpy.context.window.scene=bpy.data.scenes[previous_name]
    return scene

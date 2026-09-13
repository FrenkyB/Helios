"""Existing cockpit study and passenger cabin in the exterior coordinate system.

Layouts are illustrative visual reconstructions. They are not operator-specific
or simulator-functional. The cabin also shares geometry with the aircraft scene.
"""
import bpy
from math import pi,sin,cos
from mathutils import Vector
import geometry as g
import exterior

def scene_for(name,col,camera_loc,target,lens=30):
    old=bpy.context.scene
    scene=bpy.data.scenes.new(name)
    scene.collection.children.link(col)
    old.collection.children.unlink(col)
    scene.unit_settings.system='METRIC'
    scene['HEL-1 scope']='Editable visual interior study; no operational systems or certified layout.'
    world=bpy.data.worlds.new(name+' world');scene.world=world;world.use_nodes=True
    world.node_tree.nodes['Background'].inputs[0].default_value=(.7,.78,.86,1)
    world.node_tree.nodes['Background'].inputs[1].default_value=.4
    d=bpy.data.cameras.new(name+' camera');d.lens=lens;d.clip_start=.035;d.clip_end=200
    cam=bpy.data.objects.new(name+' camera',d);col.objects.link(cam);cam.location=camera_loc
    cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();scene.camera=cam
    scene.render.engine='CYCLES';scene.cycles.samples=48;scene.cycles.use_denoising=True
    scene.cycles.device=old.cycles.device;scene.render.resolution_x=1600;scene.render.resolution_y=1100
    scene.view_settings.view_transform='AgX'
    return scene

def light(name,loc,target,power,size=1):
    d=bpy.data.lights.new(name,'AREA');d.energy=power;d.shape='DISK';d.size=size
    obj=bpy.data.objects.new(name,d);g.COL.objects.link(obj);obj.location=loc
    obj.rotation_euler=(Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler()

def build(m,cfg):
    m=dict(m)
    m.update({
        'panelblue':g.material('Cockpit | blue-gray instrument panel',(.22,.29,.34),.08,.57),
        'label':g.material('Instrument | ivory lettering',(.85,.83,.70),0,.5),
        'seat':g.material('Cabin | navy upholstery',(.022,.047,.080),0,.61),
        'fabric':g.material('Cockpit | seat wool',(.48,.47,.43),0,.93),
        'carpet':g.material('Cabin | carpet',(.055,.065,.080),0,.95),
        'lining':g.material('Cabin | warm lining',(.69,.67,.59),0,.68),
        'sky':g.material('Instrument | sky',(.075,.30,.48),0,.5),
        'earth':g.material('Instrument | earth',(.31,.20,.075),0,.6),
        'cabinlight':g.material('Cabin | warm lighting',(.9,.76,.48),0,.3,2),
    })
    import passenger_cabin
    return {'cockpit':cockpit(m),**passenger_cabin.build(cfg['cabin'])}

def dial(name,y,z,r,m,attitude=False,x=2.995):
    g.cylinder(name+' bezel',(x-.025,y,z),(x+.004,y,z),r,m['metal'],48)
    g.cylinder(name+' face',(x+.005,y,z),(x+.008,y,z),r*.88,m['dark'],48)
    if attitude:
        for sign,mat in [(1,m['sky']),(-1,m['earth'])]:
            verts=[(x+.010,y,z)]+[(x+.010,y+r*.79*cos(pi*j/32),z+sign*r*.79*sin(pi*j/32)) for j in range(33)]
            g.mesh(name+' horizon_'+str(sign),verts,[tuple(range(len(verts)))],mat,False)
        g.curve(name+' horizon bar',[(x+.013,y-r*.6,z),(x+.013,y+r*.6,z)],m['label'],.003)
        g.curve(name+' attitude wings',[(x+.015,y-r*.4,z+.012),(x+.015,y,z),(x+.015,y+r*.4,z+.012)],m['label'],.004)
    else:
        for i in range(12):
            a=i*2*pi/12
            g.curve(name+f' tick_{i}',[(x+.012,y+r*.70*cos(a),z+r*.70*sin(a)),(x+.012,y+r*.81*cos(a),z+r*.81*sin(a))],m['label'],.002)
        a=(y*7+z*5)%6
        g.curve(name+' pointer',[(x+.015,y,z),(x+.015,y+r*.64*cos(a),z+r*.64*sin(a))],m['label'],.003)
        g.cylinder(name+' spindle',(x+.015,y,z),(x+.022,y,z),r*.08,m['label'],16)

def cockpit(m):
    col=g.collection('B737_300_COCKPIT_STUDY');g.use(col)
    g.cube('Cockpit floor',(3.58,0,2.64),(2.12,2.63,.08),m['carpet'])
    g.cube('Main instrument panel',(2.79,0,3.46),(.36,2.60,.89),m['panelblue'],.08)
    g.cube('Glare shield',(2.79,0,3.965),(.55,2.77,.12),m['dark'],.06)
    g.cube('MCP housing',(2.95,0,4.065),(.22,1.88,.19),m['panelblue'],.025)
    for side in [-1,1]:
        y=side*.77
        for j,(dy,z,r,att) in enumerate([(-.25,3.69,.093,False),(0,3.69,.12,True),(.25,3.69,.093,False),
            (-.25,3.43,.080,False),(0,3.43,.12,False),(.25,3.43,.08,False),(0,3.20,.065,False)]):
            dial(f'Pilot instruments_{side}_{j}',y+dy,z,r,m,att)
            label=['IAS','ATT','ALT','TURN','HSI','VSI','RMI'][j]
            g.text(f'Instrument label_{side}_{j}',label,(3.019,y+dy,z-r*.40),r*.16,m['label'],(pi/2,0,pi/2))
        for j in range(4):
            g.cube(f'Annunciator_{side}_{j}',(3.006,y-.22+j*.145,3.865),(.015,.10,.035),m['dark'],.004)
        g.cube('Side console_'+str(side),(3.55,side*1.25,3.12),(1.12,.32,.35),m['panelblue'],.045)
        # Seats face nose (-X) and share the actual fuselage station coordinates.
        seat(m,'Pilot seat_'+str(side),3.91,side*.74,2.66,True)
        g.cylinder('Control column_'+str(side),(3.40,side*.74,2.69),(3.31,side*.74,3.28),.052,m['wing'])
        g.cylinder('Yoke shaft_'+str(side),(3.27,side*.74,3.25),(3.52,side*.74,3.30),.036,m['dark'])
        g.curve('Classic yoke_'+str(side),[(3.52,side*.74-.19,3.46),(3.52,side*.74-.19,3.29),
            (3.52,side*.74-.11,3.24),(3.52,side*.74+.11,3.24),(3.52,side*.74+.19,3.29),(3.52,side*.74+.19,3.46)],m['dark'],.027)
        for dy in [-.12,.12]:
            pedal=g.cube('Rudder pedal',(3.02,side*.74+dy,2.82),(.12,.17,.15),m['metal'],.013)
            pedal.rotation_euler[1]=-.25
    for row,z in enumerate([3.72,3.52,3.32,3.12]):
        for side in [-1,1]:dial(f'Engine gauge_{row}_{side}',side*.105,z,.061,m)
    for i,y in enumerate([-.68,-.37,0,.37,.68]):
        g.cube(f'MCP display_{i}',(3.066,y,4.089),(.016,.18,.055),m['dark'],.004)
        g.text(f'MCP digits_{i}',['160','110','094','3000','160'][i],(3.078,y,4.078),.027,m['label'],(pi/2,0,pi/2))
        g.cylinder(f'MCP selector_{i}',(3.075,y,4.014),(3.105,y,4.014),.027,m['label'],20)
    g.cube('Center pedestal',(3.74,0,2.965),(1.37,.54,.61),m['panelblue'],.045)
    g.cube('Throttle quadrant',(3.40,0,3.30),(.44,.48,.30),m['wing'],.06)
    for side in [-1,1]:
        g.cylinder('Thrust lever_'+str(side),(3.43,side*.095,3.36),(3.35,side*.095,3.65),.014,m['metal'],16)
        g.cube('Thrust grip_'+str(side),(3.35,side*.095,3.65),(.08,.11,.055),m['label'],.015)
        g.cylinder('Trim wheel_'+str(side),(3.45,side*.25,3.18),(3.45,side*.28,3.18),.16,m['dark'],48)
        # CDU keyboard with individually editable keys.
        g.cube('CDU_'+str(side),(3.17,side*.38,3.16),(.35,.25,.16),m['dark'],.018)
        g.cube('CDU display_'+str(side),(3.09,side*.38,3.245),(.13,.20,.006),m['glass'],.005)
        for r in range(5):
            for c in range(5):g.cube(f'CDU key_{side}_{r}_{c}',(3.18+r*.025,side*.38+(c-2)*.037,3.245),(.016,.024,.006),m['label'],.002)
    for x in [3.85,4.08,4.29]:
        g.cube('Radio panel',(x,0,3.277),(.19,.43,.018),m['dark'],.01)
        g.cube('Radio display',(x-.045,0,3.292),(.043,.20,.005),m['glass'],.002)
        for y in [-.15,.15]:g.cylinder('Radio knob',(x+.035,y,3.29),(x+.035,y,3.32),.024,m['label'],20)
    g.cube('Overhead panel',(3.23,0,4.69),(1.09,.87,.075),m['panelblue'],.04)
    for i in range(7):
        for j in range(5):
            x=2.8+i*.14;y=(j-2)*.15
            g.cube(f'Overhead group_{i}_{j}',(x,y,4.648),(.11,.12,.008),m['dark'],.006)
            g.cylinder(f'Overhead switch_{i}_{j}',(x,y,4.64),(x+.013,y,4.59),.009,m['label'],12)
    # Front windshield panes and posts, independent of exterior shell for inspection.
    for side in [-1,1]:
        poly=[(2.20,side*.05,4.0),(2.32,side*.99,3.95),(2.81,side*1.14,4.42),(2.76,side*.05,4.59)]
        g.mesh('Cockpit windshield study_'+str(side),poly,[(0,1,2,3)],m['glass'])
        g.curve('Windshield structure_'+str(side),poly,m['panelblue'],.035,True)
    for x in [3.2,4.3]:light('Cockpit soft light',(x,0,4.45),(3,0,3.1),65,1.0)
    light('Windshield fill',(1.6,-1,4.4),(3.4,0,3.3),180,2)
    return scene_for('02 | Cockpit study',col,(4.64,0,4.26),(2.90,0,3.58),22)

def seat(m,name,x,y,floor,pilot=False):
    upholstery=m['fabric'] if pilot else m['seat']
    w=.48 if pilot else .43
    g.cube(name+' cushion',(x,y,floor+.43),(.45,w,.15),upholstery,.055)
    back=g.cube(name+' back',(x+.25,y,floor+.82),(.125,w,.74),upholstery,.055)
    back.rotation_euler[1]=.11
    if not pilot:
        g.cube(name+' headrest cover',(x+.176,y,floor+1.075),(.012,w*.69,.22),m['lining'],.014)
        g.cube(name+' tray table',(x+.326,y,floor+.77),(.020,w*.77,.29),m['wing'],.014)
        g.cube(name+' tray latch',(x+.34,y,floor+.94),(.016,.07,.022),m['dark'],.004)
    for dy in [-w*.43,w*.43]:
        g.cube(name+' armrest',(x+.04,y+dy,floor+.65),(.37,.045,.065),m['wing'],.021)
        g.cylinder(name+' leg',(x+.13,y+dy*.7,floor+.05),(x+.13,y+dy*.7,floor+.37),.022,m['metal'],12)

"""Deterministic, metre-scale LCLK scenery. No network or third-party dependencies.

Geometry is authored in runway coordinates (U along 04->22, V northwest),
then parented to one georeferencing empty. Aircraft datablocks stay untouched.
"""
import math
import random
from pathlib import Path

import bpy
from mathutils import Vector
import geometry as g

PREFIX = 'LCA | '
COLLECTION = 'LARNACA_AIRPORT'
SCENE = '05 | Larnaca - Helios Flight 522'
ROOT = Path(__file__).resolve().parents[1]
MATS = {}
COL = None
CACHE = {}
SURFACE_INDEX = 0


def group(name, parent):
    global COL
    COL = g.collection(PREFIX + name, parent)
    g.use(COL)
    return COL


def mesh(name, vertices, faces, material, smooth=False):
    return g.mesh(PREFIX + name, vertices, faces, MATS[material], smooth, uv=False)


def box(name, center, size, material, bevel=0):
    # Repeated facade mullions, lights and cars share mesh data.
    key = (tuple(size), material, bevel)
    if key in CACHE:
        obj = bpy.data.objects.new(PREFIX + name, CACHE[key])
        COL.objects.link(obj)
        obj.location = center
        if bevel:
            g.bevel(obj, bevel, 2)
        return obj
    obj = g.cube(PREFIX + name, center, size, MATS[material], 0)
    CACHE[key] = obj.data
    if bevel:
        g.bevel(obj, bevel, 2)
    return obj


def beam(name, a, b, radius, material, vertices=12, r2=None):
    return g.cylinder(PREFIX + name, a, b, radius, MATS[material], vertices, r2)


def label(name, text, pos, size, material='white', rotation=(0, 0, 0)):
    obj = g.text(PREFIX + name, text, pos, size, MATS[material], rotation)
    obj.data.extrude = 0
    return obj


def polygon(name, points, z, material):
    if material in {'salt', 'lagoon'}:
        # Corner-cutting yields quiet, irregular shorelines without dense terrain.
        for _ in range(3):
            refined=[]
            for a,b in zip(points,points[1:]+points[:1]):
                refined.extend([(a[0]*.75+b[0]*.25,a[1]*.75+b[1]*.25),
                                (a[0]*.25+b[0]*.75,a[1]*.25+b[1]*.75)])
            points=refined
    return mesh(name, [(x, y, z) for x, y in points], [tuple(range(len(points)))], material)


def ribbon(name, points, width, z, material):
    """Flat strip, with bounded miter joints; points are local XY."""
    vertices = []
    for i, point in enumerate(points):
        prev, nxt = Vector(points[max(0, i-1)]), Vector(points[min(len(points)-1, i+1)])
        tangent = (nxt-prev).normalized()
        normal = Vector((-tangent.y, tangent.x)) * width / 2
        vertices.extend([(point[0]+normal.x, point[1]+normal.y, z),
                         (point[0]-normal.x, point[1]-normal.y, z)])
    return mesh(name, vertices, [(2*i, 2*i+1, 2*i+3, 2*i+2) for i in range(len(points)-1)], material)


def bezier(a, b, c, steps=20):
    return [tuple((1-t)**2*a[j]+2*t*(1-t)*b[j]+t*t*c[j] for j in range(2))
            for t in (i/steps for i in range(steps+1))]


def arc(cx, cy, radius, start, end, steps=24):
    return [(cx+radius*math.cos(math.radians(start+(end-start)*i/steps)),
             cy+radius*math.sin(math.radians(start+(end-start)*i/steps))) for i in range(steps+1)]


def material(name, color, roughness=.6, metal=0, noise=0, scale=1):
    mat = g.material(PREFIX + name, color, metal, roughness)
    if noise:
        nodes, links = mat.node_tree.nodes, mat.node_tree.links
        tex = nodes.new('ShaderNodeTexCoord')
        tex.object = bpy.data.objects[PREFIX + 'Airport origin - east north']
        grain = nodes.new('ShaderNodeTexNoise')
        grain.inputs['Scale'].default_value = scale
        grain.inputs['Detail'].default_value = 3
        links.new(tex.outputs['Object'], grain.inputs['Vector'])
        ramp = nodes.new('ShaderNodeValToRGB')
        for element, factor in zip(ramp.color_ramp.elements, [1-noise, 1+noise]):
            element.color = (*[min(1, v*factor) for v in color], 1)
        links.new(grain.outputs['Fac'], ramp.inputs[0])
        bs = nodes.get('Principled BSDF')
        links.new(ramp.outputs[0], bs.inputs['Base Color'])
        bump = nodes.new('ShaderNodeBump')
        bump.inputs['Strength'].default_value = .15
        bump.inputs['Distance'].default_value = .025
        links.new(grain.outputs['Fac'], bump.inputs['Height'])
        links.new(bump.outputs['Normal'], bs.inputs['Normal'])
    MATS[name] = mat
    return mat


def materials():
    material('soil', (.38, .29, .16), noise=.5, scale=.055)
    material('scrub', (.23, .25, .105), noise=.6, scale=.10)
    material('asphalt', (.105, .12, .13), noise=.32, scale=2.2)
    material('shoulder', (.18, .175, .145), noise=.25, scale=.4)
    material('concrete', (.52, .51, .45), noise=.2, scale=.7)
    for i in range(6):
        material('slab'+str(i), (.46+i*.013, .455+i*.013, .405+i*.013), noise=.1, scale=1)
    material('joint', (.18, .18, .16))
    material('white', (.84, .84, .76))
    material('yellow', (.95, .59, .025))
    material('red', (.63, .055, .025))
    material('rubber', (.047, .052, .053), noise=.45, scale=2)
    material('wall', (.74, .72, .63), noise=.07, scale=.6)
    material('roof', (.48, .55, .60), .32, .55)
    material('steel', (.58, .62, .62), .28, .7)
    material('darksteel', (.095, .12, .12), .38, .65)
    material('glass', (.055, .18, .21), .18, .48)
    material('blue', (.02, .15, .34), .32, .15)
    material('green', (.105, .18, .055), noise=.3, scale=.8)
    material('trunk', (.26, .19, .09), noise=.3, scale=3)
    material('sand', (.61, .53, .35), noise=.2, scale=.08)
    material('salt', (.62, .59, .45), noise=.3, scale=.03)
    material('water', (.035, .20, .26), .23, .25, noise=.22, scale=.013)
    material('lagoon', (.20, .28, .25), .38, .1, noise=.35, scale=.012)
    MATS['light'] = g.material(PREFIX+'light', (1, .85, .55), 0, .3, emission=3)
    MATS['greenlight'] = g.material(PREFIX+'greenlight', (.08, 1, .22), 0, .3, emission=3)


def terrain(cfg):
    polygon('Mediterranean sea', [(-4500,-4500),(8500,-4500),(8500,8500),(-4500,8500)], -1.3, 'water')
    coast = [(2600,-2200),(2610,-1500),(2710,-1000),(2770,-650),(2900,-470),
             (3010,-230),(3100,-75),(3300,50),(3590,350),(4010,780),(4500,1800),(5700,4200)]
    polygon('Cyprus coastal terrain', [(-4500,-2200),*coast,(5700,8500),(-4500,8500)], -.06, 'soil')
    ribbon('Beach sand', coast, 42, -.05, 'sand')
    polygon('Orphani salt pan', [(-1500,-1300),(1200,-1400),(2400,-750),(2180,-460),
                               (900,-260),(-300,-410)], -.049, 'salt')
    polygon('Orphani shallow water', [(-1000,-1100),(950,-1170),(2030,-750),(1800,-570),
                                    (800,-400),(-120,-550)], -.048, 'lagoon')
    polygon('Airport salt lake', [(1150,760),(1470,740),(1600,950),(1550,1600),(1120,1480),(990,1000)], -.048, 'salt')
    polygon('Airport salt lake water', [(1220,820),(1430,810),(1510,1020),(1450,1440),(1190,1370),(1110,1020)], -.047, 'lagoon')
    rng = random.Random(522)
    for i in range(85):
        u = rng.uniform(-850, 3300)
        v = rng.choice([rng.uniform(-240, -110), rng.uniform(45, 150)])
        points = [(u+math.cos(j*math.tau/9)*rng.uniform(12, 36),
                   v+math.sin(j*math.tau/9)*rng.uniform(8, 23)) for j in range(9)]
        if u < 2820:polygon('Dry grass patch %03d'%i, points, -.045, 'scrub')
    for i in range(12):
        u=-650+(i%4)*190; v=1100+(i//4)*260
        polygon('Agricultural plot %02d'%i, [(u,v),(u+176,v+10),(u+160,v+224),(u+4,v+219)], -.044,
                'scrub' if i%3 else 'soil')


def runway(cfg):
    length, width = cfg['runway_length'], cfg['runway_width']
    box('Runway shoulders', (length/2,0,-.065), (length,width+15,.11), 'shoulder')
    surface=box('Runway 04-22 asphalt', (length/2,0,-.025), (length,width,.05), 'asphalt')
    surface['length_m']=length; surface['width_m']=width; surface['true_bearing']=cfg['runway_true_bearing']
    for side in [-1,1]:
        ribbon('Runway edge stripe', [(0,side*(width/2-.7)),(length,side*(width/2-.7))], .45, .009, 'white')
        for u in range(0,int(length)+1,60):
            box('Runway edge light', (u,side*(width/2+1.3),.18), (.28,.28,.36), 'light')
    thrs = [(cfg['threshold_04_offset'],1,'04'),(length-cfg['threshold_22_displacement'],-1,'22')]
    for threshold, direction, number in thrs:
        marker=bpy.data.objects.new(PREFIX+'Threshold '+number,None);COL.objects.link(marker)
        marker.location=(threshold,0,0);marker['runway_direction']=direction
        box('Threshold bar '+number,(threshold,0,.012),(1.8,width,.014),'white')
        for side in [-1,1]:
            for j in range(6):
                box('Threshold piano key '+number,(threshold+direction*18,side*(3+j*3),.012),(30,1.75,.014),'white')
            box('Aiming point '+number,(threshold+direction*330,side*12,.012),(45,6,.014),'white')
            for dist,pairs in [(150,3),(450,2),(600,2),(750,1),(900,1)]:
                for j in range(pairs):
                    box('Touchdown zone '+number,(threshold+direction*dist,side*(9+j*3),.012),(22.5,1.8,.014),'white')
        num=label('Runway designation '+number,number,(threshold+direction*62,0,.017),20,
                  rotation=(0,0,-direction*math.pi/2))
        num.data.align_y='CENTER';num.scale=(1,1.3,1)
        for v in range(-21,22,3):
            box('Threshold green light '+number,(threshold,v,.06),(.22,.35,.12),'greenlight')
        for j in range(1,5):
            u=threshold-direction*j*34
            if 0 < u < length:
                ribbon('Displaced arrow stem '+number,[(u-direction*13,0),(u,0)],.55,.015,'white')
                ribbon('Displaced arrow head '+number,[(u-direction*5,-2.8),(u,0),(u-direction*5,2.8)],.55,.015,'white')
        for j in range(4):
            box('PAPI '+number,(threshold+direction*300,-direction*(29+j*8),.6),(1.2,1.6,1.2),'white')
            box('PAPI lens '+number,(threshold+direction*299.35,-direction*(29+j*8),.6),(.1,1.1,.4),'red' if j<2 else 'light')
        for dist in range(30,901 if number=='04' else 271,30):
            u=threshold-direction*dist
            beam('Approach mast '+number,(u,0,-.4),(u,0,.7),.09,'steel',8)
            for v in [-2,0,2]:box('Approach light '+number,(u,v,.76),(.3,.3,.22),'light')
    for u in range(int(thrs[0][0])+110,int(thrs[1][0])-95,60):
        box('Runway centerline dash',(u,0,.013),(30,.65,.012),'white')
    rng=random.Random(4)
    for threshold,direction,number in thrs:
        for i in range(100):
            start=threshold+direction*rng.uniform(200,670);end=start+direction*rng.uniform(35,170)
            v=rng.choice([-1,1])*rng.uniform(1.8,4)
            ribbon('Rubber deposit '+number,[(start,v),(end,v+rng.uniform(-.13,.13))],rng.uniform(.03,.18),.023,'rubber')


def taxi_path(name, points, width=23, shoulders=True, z=.031):
    global SURFACE_INDEX
    # Intersection surfaces need distinct heights: coplanar crossing strips
    # create dark ray-tracing artifacts even when they have identical materials.
    SURFACE_INDEX+=1
    z+=SURFACE_INDEX*.0007
    if shoulders:ribbon(name+' shoulders',points,width+10,z-.0043,'shoulder')
    ribbon(name+' pavement',points,width,z,'asphalt')
    ribbon(name+' centerline',points,.22,z+.015,'yellow')


def taxiways(cfg):
    length=cfg['runway_length']
    for name,v in zip(['C','L'],cfg['parallel_taxiways_v']):
        taxi_path('Taxiway '+name,[(65,v),(length-55,v)],cfg['taxiway_width'])
    for tag,u in [('G',410),('D',1550),('B',2250),('A',length-60)]:
        pts=bezier((u-45,0),(u,0),(u,50))+[(u,150)]+bezier((u,150),(u,195),(u-45,195))[1:]
        taxi_path('Runway exit '+tag,pts)
        for vv in [85,86.5,88.5,90]:
            if vv<88:ribbon('Hold short '+tag,[(u-11.5,vv),(u+11.5,vv)],.28,.055,'yellow')
            else:
                for x in range(-11,11,2):box('Hold dash '+tag,(u+x,vv,.055),(1,.28,.012),'yellow')
        box('Runway sign '+tag,(u+18,84,1),(6,.3,1.5),'red')
        label('Runway sign text '+tag,'04 - 22',(u+18,83.83,1),.85,rotation=(math.pi/2,0,0))
    for tag,pts in [('H',bezier((190,0),(115,50),(75,110))+bezier((75,110),(20,195),(100,195))[1:]),
                    ('E',bezier((1090,0),(1000,10),(875,95))+bezier((875,95),(735,195),(830,195))[1:])]:
        taxi_path('Rapid exit '+tag,pts)
    for tag,u in [('U',70),('V',220),('W',680),('Y',1160),('Z',1800)]:
        taxi_path('Link '+tag,bezier((u-30,195),(u,195),(u,230))+bezier((u,230),(u,295),(u+40,295))[1:])
    for tag,u in [('LA',135),('LB',208),('LC',678)]:
        taxi_path('Apron taxilane '+tag,[(u,295),(u,640)],40,False,z=.10)
    taxi_path('West apron turn',arc(171.5,640,36.5,0,180),40,False,z=.10)
    for u in [2380,2530,2700,2830]:
        taxi_path('Old apron access',[(u,195),(u,530)],35,False,z=.10)


def apron(cfg):
    z=cfg['apron_height']
    # Broad apron base, then jointed slab areas either side of the pier.
    polygon('Apron 1 base',[(-20,330),(730,330),(740,710),(610,725),(520,675),(275,675),(190,720),(-20,720)],z,'concrete')
    for tag,(x0,x1,y0,y1) in {'West':(230,374,350,650),'East':(426,662,350,685),
                             'Remote':(-12,114,350,705)}.items():
        verts=[];faces=[];inds=[];rng=random.Random(tag)
        for x in range(x0,x1,10):
            for y in range(y0,y1,10):
                k=len(verts);gap=.025
                verts.extend([(x+gap,y+gap,z+.005),(min(x+10,x1)-gap,y+gap,z+.005),
                              (min(x+10,x1)-gap,min(y+10,y1)-gap,z+.005),(x+gap,min(y+10,y1)-gap,z+.005)])
                faces.append((k,k+1,k+2,k+3));inds.append(rng.randrange(6))
        obj=mesh('Jointed concrete '+tag,verts,faces,'slab0')
        for i in range(1,6):obj.data.materials.append(MATS['slab'+str(i)])
        for p,idx in zip(obj.data.polygons,inds):p.material_index=idx
    polygon('Apron 2',[(2130,210),(2930,210),(2970,580),(2750,650),(2170,620)],z,'concrete')
    for i in range(10):
        u=2200+i*70
        ribbon('Old stand lead',[(u,230),(u,475)],.24,z+.02,'yellow')
        ribbon('Old stand safety',[(u-27,310),(u-27,525),(u+27,525),(u+27,310)],.2,z+.021,'white')
        label('Old stand number',str(61+i),(u,440,z+.022),6,'yellow')
    for side,tags in [(-1,['27','26','25','24','23']), (1,['47','46','45','44','42'])]:
        for i,tag in enumerate(tags):
            v=460+i*42; nose=400+side*64; lane=208 if side<0 else 678
            ribbon('Stand '+tag+' lead',[(lane,v),(nose,v)],.28,z+.024,'yellow')
            ribbon('Stand '+tag+' stop',[(nose,v-3),(nose,v+3)],.35,z+.024,'yellow')
            ribbon('Stand '+tag+' envelope',[(nose-side*45,v-19),(nose+side*9,v-19),
                                            (nose+side*9,v+19),(nose-side*45,v+19)],.18,z+.025,'red')
            label('Stand '+tag+' marking',tag,(nose-side*18,v+3,z+.027),4,'yellow',rotation=(0,0,side*math.pi/2))
            spot=bpy.data.objects.new(PREFIX+'Stand '+tag+' aircraft nose',None);COL.objects.link(spot)
            spot.location=(nose,v,z);spot.rotation_euler.z=math.pi if side<0 else 0
            spot.empty_display_type='ARROWS';spot.empty_display_size=3
            spot['description']='Aircraft nose origin; original B737 local +X points aft.'
    for i,tag in enumerate(['11','12','13','14']):
        v=395+i*85
        ribbon('Remote stand '+tag,[(135,v),(50,v)],.25,z+.024,'yellow')
        label('Remote stand '+tag,tag,(60,v+4,z+.026),5,'yellow')
    # Clear service lanes along the building, outside wingspan and engine zones.
    for u in [358,442]:
        for y in range(438,638,9):box('Service lane dash',(u,y,z+.024),(.15,4,.01),'white')


def barrel_roof(name,cx,y0,y1,width,eaves,rise):
    steps=24
    def section(y):
        return [(cx-width/2+width*i/steps,y,eaves+rise*math.sin(math.pi*i/steps)) for i in range(steps+1)]
    front,back=section(y0),section(y1)
    obj=mesh(name,front+back,[(i,i+1,steps+2+i,steps+1+i) for i in range(steps)],'roof',True)
    mod=obj.modifiers.new('Roof shell thickness','SOLIDIFY');mod.thickness=.35
    for y in [y0,y1]:
        # Real arched end glazing follows the roof silhouette.
        upper=section(y)
        verts=[(cx-width/2,y,3),(cx+width/2,y,3)]+list(reversed(upper))
        mesh(name+' end glazing',verts,[tuple(range(len(verts)))],'glass')
        g.curve(PREFIX+name+' silver edge',upper,MATS['steel'],.20)
        for i in range(1,steps):
            x,z=upper[i][0],upper[i][2]
            beam(name+' end mullion',(x,y,3),(x,y,z),.075,'steel',8)
    for i in range(1,steps,2):
        x,z=front[i][0],front[i][2]
        beam(name+' standing seam',(x,y0,z+.035),(x,y1,z+.035),.045,'steel',6)
    for y in range(int(y0)+35,int(y1),35):
        g.curve(PREFIX+name+' transverse rib',section(y),MATS['steel'],.11)
    return obj


def terminal(cfg):
    cx=cfg['terminal_u'];y0,y1=cfg['pier_v_range'];width=cfg['pier_width'];eaves=cfg['terminal_eaves_height']
    body=box('Terminal pier structure',(cx,(y0+y1)/2,6.8),(width-2,y1-y0,13.6),'wall')
    body['reference']='2022 aerial: long barrel-vault pier, contact stands on both sides.'
    for side in [-1,1]:
        x=cx+side*(width/2)
        box('Pier curtain wall',(x,(y0+y1)/2,8.4),(.18,y1-y0,10.5),'glass')
        for y in range(int(y0),int(y1)+1,5):
            box('Pier glazing mullion',(x+side*.14,y,8.4),(.16,.13,10.6),'steel')
        for z in [3.2,6.5,10,13.5]:
            box('Pier glazing transom',(x+side*.15,(y0+y1)/2,z),(.14,y1-y0,.13),'steel')
        for y in range(int(y0)+8,int(y1),35):
            beam('Pier white structural column',(x+side*.6,y,.08),(x+side*.6,y,14.4),.72,'wall',16)
    barrel_roof('Pier barrel roof',cx,y0-3,y1+12,width+6,eaves,4.3)
    # Head house: two broad vaulted halls and lower flanking blocks.
    box('Terminal headhouse',(cx,725,8),(190,178,16),'wall')
    box('Terminal cross wings',(cx,672,5.5),(258,56,11),'wall')
    for x,w in [(cx-52,69),(cx+40,85)]:
        barrel_roof('Main hall roof',x,642,820,w,17,4.2)
    for side in [-1,1]:
        box('Headhouse side glass',(cx+side*95.15,742,10),(.2,110,13),'glass')
        for y in range(690,799,5):box('Head side mullion',(cx+side*95.3,y,10),(.16,.15,13),'steel')
    box('Landside glass facade',(cx,820.2,9.5),(187,.2,14),'glass')
    for x in range(int(cx)-90,int(cx)+91,5):box('Front facade mullion',(x,820.4,9.5),(.14,.16,14),'steel')
    for z in [3,7,11,15]:box('Front horizontal mullion',(cx,820.4,z),(187,.15,.14),'steel')
    for x in range(int(cx)-75,int(cx)+76,30):
        box('Entrance portal',(x,820.5,3),(6,.6,6),'darksteel')
        box('Entrance door glass',(x,820.85,2.7),(5.5,.15,5.2),'glass')
        label('Entrance sign','DEPARTURES',(x,820.96,5.7),.65,rotation=(math.pi/2,0,math.pi))
    box('Terminal name panel',(cx,820.6,15.5),(126,.3,2.6),'blue')
    label('Airport name','LARNAKA INTERNATIONAL AIRPORT',(cx,820.78,15),1.8,rotation=(math.pi/2,0,math.pi))
    for x in [cx-111,cx+111]:
        for y in [658,677]:
            box('Rooftop plant',(x,y,12.2),(9,5,2.4),'steel')
            for k in [-2,0,2]:box('Plant louver',(x+k,y-2.52,12.2),(.6,.05,1.8),'darksteel')


def bridge(tag,v,side):
    x=400+side*27
    beam('Gate '+tag+' rotunda',(x+side*7,v+10,.08),(x+side*7,v+10,7.8),3.2,'wall',20)
    points=[(x,v+10,5.2),(x+side*24,v+10,5.2),(400+side*68,v+3.1,4.3)]
    for i,(a,b) in enumerate(zip(points,points[1:])):
        mid=(Vector(a)+Vector(b))/2;delta=Vector(b)-Vector(a)
        obj=box('Gate '+tag+' bridge '+str(i),mid,(delta.length,3.2,2.8),'glass')
        obj.rotation_euler=delta.to_track_quat('X','Z').to_euler()
        for z in [-1.48,1.48]:
            deck=box('Gate '+tag+' bridge frame',(mid.x,mid.y,mid.z+z),(delta.length+.25,3.5,.18),'steel')
            deck.rotation_euler=obj.rotation_euler
        n=int(delta.length/2.5)
        for j in range(n+1):
            p=Vector(a).lerp(Vector(b),j/n)
            beam('Bridge mullion',(p.x,p.y-1.65,p.z-1.35),(p.x,p.y-1.65,p.z+1.35),.065,'steel',6)
            beam('Bridge mullion',(p.x,p.y+1.65,p.z-1.35),(p.x,p.y+1.65,p.z+1.35),.065,'steel',6)
    end=points[-1]
    box('Gate '+tag+' accordion',(end[0],end[1],end[2]),(3.4,3.9,3.2),'rubber')
    for i in range(6):box('Gate '+tag+' bellows rib',(end[0]-1.5+i*.6,end[1],end[2]),(.13,4,3.3),'darksteel')
    beam('Gate '+tag+' telescopic leg',(end[0]-side*5,end[1],.7),(end[0]-side*5,end[1],4),.35,'steel')
    for yy in [-1.25,1.25]:beam('Bridge wheel',(end[0]-side*5,end[1]+yy-.18,.5),(end[0]-side*5,end[1]+yy+.18,.5),.42,'rubber')
    box('Gate '+tag+' identification',(x+side*7,v+6.65,6.8),(2.8,.1,1.5),'blue')
    label('Gate '+tag+' number',tag,(x+side*7,v+6.58,6.3),1,rotation=(math.pi/2,0,0))


def tower(cfg):
    u,v=cfg['tower_uv'];height=cfg['tower_height']
    box('Tower service building',(u,v,3.5),(48,32,7),'wall')
    shaft=beam('Control tower shaft',(u,v,.08),(u,v,height-9),6.3,'wall',48)
    shaft['height_to_cab_roof_m']=height
    beam('Tower upper collar',(u,v,height-10),(u,v,height-8),7,'wall',48)
    beam('Tower balcony',(u,v,height-8),(u,v,height-7.3),8.4,'steel',12)
    beam('Tower splayed glass cab',(u,v,height-7.3),(u,v,height-1),6.7,'glass',12,r2=9.0)
    for i in range(12):
        a=math.tau*i/12
        beam('Tower angled mullion',(u+6.75*math.cos(a),v+6.75*math.sin(a),height-7.3),
             (u+9.03*math.cos(a),v+9.03*math.sin(a),height-1),.16,'steel')
    beam('Tower cab roof',(u,v,height-1),(u,v,height),9.5,'wall',12)
    beam('Tower roof equipment',(u,v,height),(u,v,height+1.5),2,'steel',16)
    beam('Tower antenna',(u,v,height+1.5),(u,v,height+8),.12,'steel',8)
    box('Tower beacon',(u,v,height+8),(.5,.5,.6),'light')
    for y in [-16.1,16.1]:
        box('Tower base glazing',(u,v+y,3.5),(34,.2,4.2),'glass')
    for a in range(0,360,30):
        x=u+8*math.cos(math.radians(a));y=v+8*math.sin(math.radians(a))
        beam('Tower balcony post',(x,y,height-7.3),(x,y,height-6.1),.06,'steel',6)
    g.curve(PREFIX+'Tower safety rail',[(x,y,height-6.1) for x,y in arc(u,v,8,0,360)],MATS['steel'],.08)


def palm(u,v,height=8):
    beam('Palm trunk',(u,v,.15),(u+.35,v,height),.24,'trunk',9,r2=.14)
    for i in range(9):
        a=math.tau*i/9;dx,dy=math.cos(a),math.sin(a)
        verts=[];faces=[]
        spine=[]
        for j in range(15):
            t=j/14;r=4*t;z=height+.9*math.sin(math.pi*t)-1.15*t
            spine.append((u+.35+dx*r,v+dy*r,z))
            if j in [0,14]:continue
            width=.72*math.sin(math.pi*t)
            for side in [-1,1]:
                x,y=spine[-1][:2];k=len(verts)
                verts.extend([(x-dx*.10,y-dy*.10,z),
                              (x+dx*.65-side*dy*width,y+dy*.65+side*dx*width,z-.2),
                              (x+dx*.10,y+dy*.10,z+.045)])
                faces.append((k,k+1,k+2))
        mesh('Palm feathered frond',verts,faces,'green')
        g.curve(PREFIX+'Palm rachis',spine,MATS['green'],.025)


def car(u,v,color='white',angle=0):
    for name,offset,size,mat in [('body',.7,(4.4,1.8,1.05),color),('windows',1.35,(2.6,1.68,.85),'glass'),
                                 ('roof',1.83,(2.4,1.66,.12),color)]:
        obj=box('Car '+name,(u,v,offset),size,mat,.10);obj.rotation_euler.z=angle
    for x in [-1.35,1.35]:
        for y in [-.89,.89]:
            xx=u+x*math.cos(angle)-y*math.sin(angle);yy=v+x*math.sin(angle)+y*math.cos(angle)
            beam('Car tire',(xx-.1*math.sin(angle),yy+.1*math.cos(angle),.43),
                 (xx+.1*math.sin(angle),yy-.1*math.cos(angle),.43),.34,'rubber',10)


def forecourt(cfg):
    existing=set(COL.objects)
    cx=cfg['terminal_u']
    box('Forecourt paving',(cx,1060,-.01),(264,94,.16),'concrete')
    box('Departure dropoff elevated deck',(cx,1037,6.45),(240,29,.9),'concrete')
    box('Departure lanes',(cx,1038,6.92),(236,14,.045),'asphalt')
    for x in range(int(cx)-105,int(cx)+106,15):
        beam('Forecourt viaduct column',(x,1048,.08),(x,1048,6.1),.52,'wall',12)
    for side in [-1,1]:
        x=cx+side*117
        for y in [1023,1050]:
            beam('Departure deck column',(x,y,0),(x,y,6.2),.6,'wall',16)
        ramp=box('Departure ramp',(cx+side*179,1040,3.43),(125,14,.7),'concrete')
        ramp.rotation_euler.y=side*math.atan2(6.4,125)
        for yy in [-6,6]:
            g.curve(PREFIX+'Ramp barrier',[(cx+side*117,1040+yy,7.55),(cx+side*241,1040+yy,1.15)],MATS['steel'],.1)
    for y in [1022,1052]:
        for x in range(int(cx)-117,int(cx)+118,5):beam('Deck balustrade',(x,y,6.9),(x,y,8.1),.05,'steel',6)
        beam('Deck handrail',(cx-119,y,8.1),(cx+119,y,8.1),.075,'steel',8)
    box('Entrance canopy',(cx,1022,11.5),(213,17,.5),'roof')
    for x in range(int(cx)-100,int(cx)+101,10):
        beam('Canopy column',(x,1028,6.9),(x,1028,11.3),.18,'steel')
        beam('Canopy rafter',(x,1014,11.2),(x,1030,11.2),.14,'darksteel')
    # Forecourt circuit and parking, with a readable central approach.
    road=[(cx-300,1120),(cx-180,1080),(cx+180,1080),(cx+300,1120),(cx+300,1400),
          (cx,1470),(cx-300,1400),(cx-300,1120)]
    taxi_path('Forecourt access loop',road,15,False,z=.10)
    taxi_path('Airport approach road',[(cx,1470),(cx,2200)],20,False)
    for x in [cx-145,cx+145]:
        box('Public parking',(x,1260,-.01),(246,280,.11),'asphalt')
        for row in range(9):
            y=1137+row*29
            for col in range(30):
                xx=x-113+col*7.5
                ribbon('Parking bay',[(xx,y),(xx,y+5.5),(xx+2.7,y+5.5)],.10,.052,'white')
                if (col*7+row*11)%5<2:car(xx+1.35,y+2.7,['white','steel','blue','darksteel','red'][(col+row)%5],math.pi/2)
        for yy in [1122,1400]:
            box('Parking planting strip',(x,yy,.12),(242,3,.25),'scrub')
            for xx in range(int(x)-110,int(x)+111,28):palm(xx,yy,6)
    for x in range(int(cx)-110,int(cx)+111,22):
        box('Forecourt planter',(x,1064,.45),(8,4,.9),'wall')
        box('Planter soil',(x,1064,.92),(7.5,3.5,.1),'soil');palm(x,1064,8)
        beam('Forecourt light pole',(x+7,1060,.1),(x+7,1060,7),.09,'steel')
        box('Forecourt lamp',(x+7,1060,7.1),(.7,.7,.2),'light')
    box('Forecourt wayfinding pylon',(cx,1110,7),(3,3,14),'steel')
    box('Forecourt pylon blue',(cx,1108.45,8),(2.7,.1,10),'blue')
    label('Pylon LCA','LCA',(cx,1108.37,10),1.15,rotation=(math.pi/2,0,0))
    for x in range(int(cx)-90,int(cx)+90,40):
        for d in range(8):box('Pedestrian crossing',(x+d*.65,1080,.12),(.35,11,.012),'white')
    for x in [cx-81,cx-26,cx+34,cx+78]:car(x,1083,'darksteel')
    # Head house is 200 m closer to the runway than the initial study blockout.
    # Shift every landside feature together, including absolute-coordinate meshes.
    for obj in set(COL.objects)-existing:obj.location.y-=200


def airside(cfg):
    for u,v in [(110,360),(705,360),(110,715),(735,700),(920,390),(2280,580),(2780,560)]:
        beam('Apron floodlight mast',(u,v,.08),(u,v,23),.28,'steel',12,r2=.13)
        box('Floodlight crossbar',(u,v,23),(4,.3,.3),'steel')
        for i in range(5):box('Floodlight head',(u-1.6+i*.8,v,23.2),(.6,.9,.6),'light')
    for name,u,v,w,d,h in [('Fire station',1220,440,75,38,9),('Operations',950,565,48,42,8),
                            ('Old terminal',2540,690,330,68,12),('Maintenance hangar',2940,510,100,75,20),
                            ('Cargo',2200,780,110,62,13),('Service depot',820,905,80,48,9)]:
        box(name,(u,v,h/2),(w,d,h),'wall')
        box(name+' roof',(u,v,h+.2),(w+2,d+2,.4),'roof')
        box(name+' frontage',(u,v-d/2-.1,h*.55),(w*.86,.2,h*.55),'glass')
        for x in range(int(u-w/2+5),int(u+w/2),10):box(name+' facade pier',(x,v-d/2-.25,h/2),(1,.5,h),'wall')
    taxi_path('Airside perimeter road',[(-140,845),(-140,100),(0,-170),(2200,-170),(2980,70),(3020,650),(2700,850)],7,False)
    fence=[(-150,850),(-150,110),(0,-190),(2200,-190),(3005,55),(3050,640)]
    for a,b in zip(fence,fence[1:]):
        n=max(1,int(math.dist(a,b)/12))
        for i in range(n+1):
            t=i/n;x=a[0]+t*(b[0]-a[0]);y=a[1]+t*(b[1]-a[1])
            beam('Fence post',(x,y,-.3),(x,y,2.1),.045,'steel',6)
        for z in [.6,1.4,2.1]:beam('Perimeter fence wire',(*a,z),(*b,z),.017,'darksteel',6)
    # Equipment is clear of the parked aircraft's wing/engine footprint.
    for u,v in [(360,522),(358,604),(445,482),(449,642),(343,434)]:
        box('Ground power unit',(u,v,1),(3,1.6,1.8),'white',.12)
        for x in [-1,1]:beam('GPU wheel',(u+x,v-.9,.42),(u+x,v+.9,.42),.33,'rubber',10)
        box('Baggage tug',(u-6,v,.85),(3,1.6,1.5),'white',.15)
        box('Tug windshield',(u-6.6,v,1.65),(1.1,1.4,.7),'glass',.04)
        for i in range(3):
            x=u-11-i*4
            box('Baggage cart bed',(x,v,.6),(3,1.8,.25),'steel')
            box('Baggage cart canopy',(x,v,1.55),(2.8,1.7,1.4),'blue',.12)
            for yy in [-.85,.85]:beam('Cart axle wheel',(x, v+yy-.1,.35),(x,v+yy+.1,.35),.27,'rubber',8)
    box('Airside bus',(550,690,1.55),(12,2.7,2.9),'white',.3)
    box('Airside bus windows',(550,688.61,2),(10.8,.06,1.2),'glass')
    for x in [-4,4]:beam('Bus wheels',(550+x,688.5,.55),(550+x,691.5,.55),.5,'rubber',12)
    for u,v in [(305,525),(308,544),(305,563)]:
        beam('Safety cone base',(u,v,.08),(u,v,.18),.28,'rubber',12)
        beam('Safety cone',(u,v,.18),(u,v,.78),.20,'red',12,r2=.035)


def world_point(local,cfg):
    a=math.radians(90-cfg['runway_true_bearing']);u,v,z=local
    return Vector((u*math.cos(a)-v*math.sin(a),u*math.sin(a)+v*math.cos(a),z))


def cameras(scene,cfg):
    specs={
        'airport_overview':((2050,-2050,2450),(1370,350,0),55,4600),
        'layout':((1350,420,4200),(1350,420,0),50,4500),
        'terminal_aerial':((-150,-20,450),(390,565,5),46,None),
        'helios_gate':((266,505,7.5),(337,548,6),43,None),
        'forecourt':((555,928,14),(400,810,10),32,None),
        'tower':((930,405,34),(1090,570,21),52,None),
        'runway_04':((-155,-57,13),(760,0,2),40,None),
    }
    for name,(loc,target,lens,ortho) in specs.items():
        data=bpy.data.cameras.new(PREFIX+name)
        obj=bpy.data.objects.new(PREFIX+'Camera '+name,data);COL.objects.link(obj)
        obj.location=world_point(loc,cfg);obj.rotation_euler=(world_point(target,cfg)-obj.location).to_track_quat('-Z','Y').to_euler()
        data.lens=lens;data.clip_start=.2;data.clip_end=20000
        if ortho:data.type='ORTHO';data.ortho_scale=ortho
        obj['airport_camera']=name
    scene.camera=bpy.data.objects[PREFIX+'Camera helios_gate']
    world=bpy.data.worlds.new(PREFIX+'Cyprus clear sky');scene.world=world;world.use_nodes=True
    nodes=world.node_tree.nodes
    sky=nodes.new('ShaderNodeTexSky')
    sky_types=sky.bl_rna.properties['sky_type'].enum_items.keys()
    sky.sky_type='MULTIPLE_SCATTERING' if 'MULTIPLE_SCATTERING' in sky_types else 'NISHITA'
    sky.sun_elevation=math.radians(38);sky.sun_rotation=math.radians(210)
    sky.altitude=.02;sky.air_density=1
    if hasattr(sky,'aerosol_density'):sky.aerosol_density=1.7
    else:sky.dust_density=1.7
    sky.sun_disc=False
    world.node_tree.links.new(sky.outputs[0],nodes['Background'].inputs[0]);nodes['Background'].inputs[1].default_value=.035
    sun_data=bpy.data.lights.new(PREFIX+'Mediterranean sun','SUN');sun_data.energy=3.1;sun_data.angle=.025
    sun=bpy.data.objects.new(PREFIX+'Mediterranean sun',sun_data);COL.objects.link(sun);sun.rotation_euler=(.5,-.4,-.5)
    scene.render.engine='CYCLES';scene.cycles.samples=cfg['render_samples'];scene.cycles.use_denoising=True;scene.cycles.max_bounces=5
    scene.render.resolution_x,scene.render.resolution_y=cfg['render_resolution'];scene.render.resolution_percentage=100
    scene.view_settings.view_transform='AgX';scene.render.image_settings.file_format='PNG'
    scene.view_settings.look='AgX - Medium High Contrast'
    prefs=bpy.context.preferences.addons['cycles'].preferences
    for backend in ['OPTIX','CUDA','HIP','ONEAPI']:
        try:
            prefs.compute_device_type=backend;prefs.get_devices()
            if any(d.type==backend for d in prefs.devices):
                for d in prefs.devices:d.use=d.type==backend
                scene.cycles.device='GPU';print('Render device:',backend,flush=True);break
        except Exception:
            continue
    scene.render.filepath=str(ROOT/'renders'/'larnaca'/'helios_gate.png')


def remove_previous():
    for scene in list(bpy.data.scenes):
        if scene.name==SCENE:bpy.data.scenes.remove(scene)
    for obj in list(bpy.data.objects):
        if obj.name.startswith(PREFIX):bpy.data.objects.remove(obj,do_unlink=True)
    for col in list(bpy.data.collections):
        if col.name.startswith(PREFIX) or col.name==COLLECTION:bpy.data.collections.remove(col)
    for container in [bpy.data.meshes,bpy.data.curves,bpy.data.materials,bpy.data.cameras,bpy.data.lights,bpy.data.worlds]:
        for item in list(container):
            if item.name.startswith(PREFIX) and item.users==0:container.remove(item)


def build(cfg):
    global SURFACE_INDEX
    SURFACE_INDEX=0
    CACHE.clear();MATS.clear();remove_previous()
    scene=bpy.data.scenes.new(SCENE);bpy.context.window.scene=scene
    scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1
    scene['task']=cfg['task']
    scene['appearance']=cfg['appearance'];scene['reference']=cfg['reference'];scene['accuracy_notes']=cfg['accuracy_notes']
    root=g.collection(COLLECTION)
    group('00 Georeference',root)
    origin=bpy.data.objects.new(PREFIX+'Airport origin - east north',None);COL.objects.link(origin)
    origin.rotation_euler.z=math.radians(90-cfg['runway_true_bearing'])
    origin.empty_display_type='ARROWS';origin.empty_display_size=40
    origin['coordinates']=cfg['coordinate_notes'];origin['runway_true_bearing']=cfg['runway_true_bearing']
    materials()
    for name,fn in [('01 Terrain coastline salt lakes',terrain),('02 Runway 04-22',runway),
                    ('03 Aprons stands',apron),('04 Taxiways',taxiways),('05 Terminal exterior',terminal),
                    ('07 Control tower',tower),('08 Forecourt roads parking',forecourt),('09 Airside equipment',airside)]:
        group(name,root);print('BUILD LARNACA',name,flush=True);fn(cfg)
    group('06 Passenger boarding bridges',root)
    for side,tags in [(-1,['27','26','25','24','23']),(1,['47','46','45','44','42'])]:
        for i,tag in enumerate(tags):bridge(tag,460+i*42,side)
    # The wrapper is instanced, never linked directly to a scene. Its children
    # are the original aircraft collections; no object transform is altered.
    group('10 Helios placement',root)
    wrapper=bpy.data.collections.new(PREFIX+'Aircraft reusable assembly')
    for name in ['B737_300_EXTERIOR','08_HELIOS_Livery','B737_300_CABIN_STUDY','B737_300_COCKPIT_STUDY']:
        col=bpy.data.collections.get(name)
        if col:wrapper.children.link(col)
    aircraft=bpy.data.objects.new(PREFIX+'Helios 737-300 - stand '+cfg['helios_stand'],None);COL.objects.link(aircraft)
    aircraft.instance_type='COLLECTION';aircraft.instance_collection=wrapper
    aircraft.location=(*cfg['helios_nose_uv'],cfg['apron_height']+.005);aircraft.rotation_euler.z=math.pi
    aircraft['placement']='Move this collection instance to another named stand; aircraft study geometry stays unchanged.'
    for obj in root.all_objects:
        if obj!=origin:obj.parent=origin
    group('11 Cameras and daylight',root);cameras(scene,cfg)
    readme=bpy.data.texts.get('LARNACA_README') or bpy.data.texts.new('LARNACA_README')
    readme.clear()
    readme.write(
        'LARNACA INTERNATIONAL AIRPORT | '+cfg['task']+'\n\n'
        +cfg['appearance']+'\n\n'+cfg['coordinate_notes']+'\n\n'
        'Scene 05 contains the airport and a linked Helios aircraft instance.\n'
        'Move LCA | Helios 737-300 - stand 25 to reposition the aircraft.\n'
        'Original aircraft and interior study scenes retain their coordinates.\n'
        'Separate collections contain terrain, runway, taxiways, apron, terminal,\n'
        'bridges, tower, forecourt, equipment and seven inspection cameras.\n\n'
        'Build everything: python run_all.py\n'
        'Update airport only: python run_all.py --airport-only\n'
        'Add --skip-render to omit previews or --draft for faster previews.\n'
        'Configuration: config/larnaca.json; previews: renders/larnaca/.\n\n'
        'Reference basis: '+cfg['reference']+'\n'
        'Reference packs were used during modeling and are not build inputs.\n'
        'Accuracy: '+cfg['accuracy_notes']+'\n')
    bpy.context.view_layer.update()
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':
                # Thousands of child-to-origin guides obscure the airport.
                area.spaces.active.overlay.show_relationship_lines=False
                area.spaces.active.clip_end=20000;area.spaces.active.clip_start=.1
                area.spaces.active.region_3d.view_distance=165
                area.spaces.active.region_3d.view_location=world_point((360,544,8),cfg)
                area.spaces.active.region_3d.view_rotation=scene.camera.rotation_euler.to_quaternion()
                area.spaces.active.shading.color_type='MATERIAL'
    return scene

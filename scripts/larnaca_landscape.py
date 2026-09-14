"""Reusable Mediterranean landscape context; visual scenery, not surveyed buildings."""
import math
import random

import bpy


def tree(api, x, y, rng, height=8):
    """One shared mesh per crown variant, including trunk and layered foliage."""
    variant = rng.randrange(8)
    key = ('landscape_tree', variant)
    if key not in api.CACHE:
        local = random.Random(710 + variant)
        vertices, faces, materials = [], [], []
        # Trunk and crown lobes share an object to keep scene traversal inexpensive.
        for center, radii, mat in [((0,0,2),(.2,.2,2),0)] + [
            ((local.uniform(-1.4,1.4),local.uniform(-1.4,1.4),local.uniform(4.7,6.4)),
             (local.uniform(1.8,2.8),local.uniform(1.8,2.8),local.uniform(1.7,2.5)),
             1 + (variant+i)%4) for i in range(5)]:
            bottom = len(vertices)
            vertices.append((center[0],center[1],center[2]-radii[2]))
            rings = []
            for j in range(1,5):
                phi = -math.pi/2 + j*math.pi/5
                ring = []
                for k in range(9):
                    a = math.tau*k/9
                    ring.append(len(vertices))
                    vertices.append((center[0]+radii[0]*math.cos(phi)*math.cos(a),
                                     center[1]+radii[1]*math.cos(phi)*math.sin(a),
                                     center[2]+radii[2]*math.sin(phi)))
                rings.append(ring)
            top = len(vertices)
            vertices.append((center[0],center[1],center[2]+radii[2]))
            new_faces = []
            for k in range(9):
                n=(k+1)%9
                new_faces.extend([(bottom,rings[0][n],rings[0][k]),(rings[-1][k],rings[-1][n],top)])
                for a,b in zip(rings,rings[1:]):
                    new_faces.append((a[k],a[n],b[n],b[k]))
            faces.extend(new_faces)
            materials.extend([mat]*len(new_faces))
        obj = api.mesh('Landscape tree', vertices, faces, 'trunk', smooth=True)
        for i in range(4):
            obj.data.materials.append(api.MATS['foliage'+str(i)])
        for face,index in zip(obj.data.polygons,materials):
            face.material_index=index
        api.CACHE[key]=obj.data
    else:
        obj=bpy.data.objects.new(api.PREFIX+'Landscape tree',api.CACHE[key])
        api.COL.objects.link(obj)
    obj.location=(x,y,-.25)
    obj.scale=(height/8,height/8,height/8)
    obj.rotation_euler.z=rng.uniform(0,math.tau)
    return obj


def build(api, cfg):
    rng=random.Random(52226)
    # Fields around, rather than through, the operational airfield and salt pans.
    regions=[(-1850,-800,-500,1800),(-750,900,1900,3150),(-1200,2300,-2150,-1550)]
    for region,(x0,x1,y0,y1) in enumerate(regions):
        for row,y in enumerate(range(y0,y1,230)):
            for col,x in enumerate(range(x0,x1,270)):
                dx,dy=rng.uniform(-10,10),rng.uniform(-10,10)
                points=[(x+8,y+8),(x+253,y+8+dy),(x+250+dx,y+212),(x+8,y+215)]
                api.polygon(f'Countryside field {region}-{row}-{col}',points,-.25,'field'+str(rng.randrange(5)))
                # Planted groves provide readable scale and depth in aerial shots.
                if (row+col+region)%3==0:
                    for yy in range(y+24,y+200,16):
                        for xx in range(x+25,x+230,18):
                            tree(api,xx+rng.uniform(-2,2),yy+rng.uniform(-2,2),rng,rng.uniform(5,8))
            api.ribbon('Rural access lane',[(x0,y),(x1+230,y)],5,-.12,'sand')
    # Irregular woodland at the southwest boundary; clear of runway and approaches.
    for i in range(2400):
        x,y=rng.uniform(-1150,-260),rng.uniform(-150,800)
        if x > -900 and abs(y) < 130:
            continue
        if rng.random() < .6+.25*math.sin(x*.013)*math.sin(y*.018):
            tree(api,x,y,rng,rng.uniform(9,15))
    # Low-rise urban context on the landside of the old terminal.
    for row in range(8):
        y=1050+row*135
        api.ribbon('Landside district street',[(1740,y),(2970,y)],9,-.08,'asphalt')
        for col in range(9):
            x=1800+col*132
            if row==0:
                api.ribbon('Landside cross street',[(x-53,1000),(x-53,2110)],8,-.08,'asphalt')
            for k in range(5):
                if rng.random()<.12:
                    continue
                xx=x+(k%3)*30-25+rng.uniform(-7,7)
                yy=y+35+(k//3)*40+rng.uniform(-5,5)
                w,d,h=rng.choice([13,16,20]),rng.choice([14,18,22]),rng.choice([5,7,10])
                api.box('Landside house',(xx,yy,h/2),(w,d,h),'wall')
                api.box('Landside roof',(xx,yy,h+.22),(w+.5,d+.5,.44),'terracotta' if (col+k)%4==0 else 'concrete')
                if k%2==0:
                    tree(api,xx+14,yy+12,rng,rng.uniform(5,9))
    # Sparse roadside planting ties forecourt and distant fields together.
    for y in range(1320,1950,24):
        for x in (370,430):
            tree(api,x+rng.uniform(-3,3),y,rng,rng.uniform(7,10))

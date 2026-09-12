"""Small deterministic Blender geometry toolkit. Coordinates and radii in metres."""
import bpy
import bmesh
import math
from mathutils import Vector

COL = None

def collection(name, parent=None):
    col = bpy.data.collections.new(name)
    (parent or bpy.context.scene.collection).children.link(col)
    return col

def use(col):
    global COL
    COL = col

def link(obj):
    for col in list(obj.users_collection):
        col.objects.unlink(obj)
    COL.objects.link(obj)
    return obj

def material(name, color, metallic=0, roughness=.4, emission=0):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color, 1)
    m.use_nodes = True
    bs = m.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Base Color'].default_value = (*color, 1)
    bs.inputs['Metallic'].default_value = metallic
    bs.inputs['Roughness'].default_value = roughness
    if emission:
        bs.inputs['Emission Color'].default_value = (*color, 1)
        bs.inputs['Emission Strength'].default_value = emission
    return m

def mesh(name, verts, faces, mat, smooth=True, uv=True):
    data = bpy.data.meshes.new(name + '_Mesh')
    data.from_pydata(verts, [], faces)
    data.update()
    bm = bmesh.new()
    bm.from_mesh(data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(data)
    bm.free()
    obj = bpy.data.objects.new(name, data)
    COL.objects.link(obj)
    if mat:
        data.materials.append(mat)
    for p in data.polygons:
        p.use_smooth = smooth
    if uv:
        # A predictable box projection seed, intended for further UV refinement.
        layer = data.uv_layers.new(name='UV_Base')
        for poly in data.polygons:
            normal = poly.normal
            axis = max(range(3), key=lambda k: abs(normal[k]))
            axes = [k for k in range(3) if k != axis]
            for li in poly.loop_indices:
                co = data.vertices[data.loops[li].vertex_index].co
                layer.data[li].uv = (co[axes[0]] * .1, co[axes[1]] * .1)
    return obj

def bevel(obj, amount=.025, segments=3):
    mod = obj.modifiers.new('Edge radii', 'BEVEL')
    mod.width = amount
    mod.segments = segments
    return obj

def cube(name, loc, size, mat, radius=.025):
    verts=[(sx*size[0]/2,sy*size[1]/2,sz*size[2]/2) for sx,sy,sz in
        [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]]
    obj=mesh(name,verts,[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],mat,False)
    obj.location=loc
    if radius:
        bevel(obj, radius)
    return obj

def cylinder(name, a, b, radius, mat, vertices=32, r2=None):
    delta = Vector(b) - Vector(a)
    rings=[]
    for z,r in [(-delta.length/2,radius),(delta.length/2,radius if r2 is None else r2)]:
        rings.append([(r*math.cos(j*2*math.pi/vertices),r*math.sin(j*2*math.pi/vertices),z) for j in range(vertices)])
    obj=loft(name,rings,mat)
    obj.location=(Vector(a)+Vector(b))/2
    obj.rotation_euler = delta.to_track_quat('Z', 'Y').to_euler()
    for p in obj.data.polygons:
        p.use_smooth = len(p.vertices) == 4
    return obj

def sphere(name, loc, scale, mat, segments=32, rings=16):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=rings, location=loc)
    obj = link(bpy.context.object)
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    for p in obj.data.polygons:
        p.use_smooth = True
    return obj

def curve(name, points, mat, radius=.005, closed=False):
    data = bpy.data.curves.new(name, 'CURVE')
    data.dimensions = '3D'
    data.resolution_u = 1
    data.bevel_depth = radius
    data.bevel_resolution = 2
    sp = data.splines.new('POLY')
    sp.points.add(len(points)-1)
    for p, co in zip(sp.points, points):
        p.co = (*co, 1)
    sp.use_cyclic_u = closed
    obj = bpy.data.objects.new(name, data)
    COL.objects.link(obj)
    data.materials.append(mat)
    return obj

def text(name, body, loc, size, mat, rotation=(0,0,0)):
    data = bpy.data.curves.new(name, 'FONT')
    data.body = body
    data.size = size
    data.extrude = .0003
    data.align_x = 'CENTER'
    obj = bpy.data.objects.new(name, data)
    COL.objects.link(obj)
    obj.location = loc
    obj.rotation_euler = rotation
    data.materials.append(mat)
    return obj

def loft(name, rings, mat, caps=True):
    n = len(rings[0])
    faces = []
    for j in range(len(rings)-1):
        for k in range(n):
            kn = (k+1)%n
            faces.append((j*n+k, j*n+kn, (j+1)*n+kn, (j+1)*n+k))
    if caps:
        faces.extend([tuple(range(n-1,-1,-1)), tuple((len(rings)-1)*n+k for k in range(n))])
    return mesh(name, [v for ring in rings for v in ring], faces, mat)

def interp(stations, x):
    """Shape-preserving cubic Hermite interpolation (one scalar column)."""
    if x <= stations[0][0]: return stations[0][1]
    if x >= stations[-1][0]: return stations[-1][1]
    for i in range(len(stations)-1):
        x0, y0 = stations[i]
        x1, y1 = stations[i+1]
        if x0 <= x <= x1:
            d = (y1-y0)/(x1-x0)
            def slope(j):
                if j == 0: return (stations[1][1]-stations[0][1])/(stations[1][0]-stations[0][0])
                if j == len(stations)-1: return (stations[-1][1]-stations[-2][1])/(stations[-1][0]-stations[-2][0])
                a = (stations[j][1]-stations[j-1][1])/(stations[j][0]-stations[j-1][0])
                b = (stations[j+1][1]-stations[j][1])/(stations[j+1][0]-stations[j][0])
                return 0 if a*b <= 0 else 2*a*b/(a+b)
            m0, m1 = slope(i), slope(i+1)
            t = (x-x0)/(x1-x0)
            return (2*t**3-3*t**2+1)*y0+(t**3-2*t**2+t)*(x1-x0)*m0+(-2*t**3+3*t**2)*y1+(t**3-t**2)*(x1-x0)*m1

def rounded_rect(cx, cy, w, h, radius, steps=7):
    pts=[]
    for sx,sy,start in [(1,1,0),(-1,1,90),(-1,-1,180),(1,-1,270)]:
        for i in range(steps+1):
            a=math.radians(start+i*90/steps)
            pts.append((cx+sx*(w/2-radius)+radius*math.cos(a),cy+sy*(h/2-radius)+radius*math.sin(a)))
    dense=[]
    for i,a in enumerate(pts):
        b=pts[(i+1)%len(pts)]
        count=max(1,math.ceil(math.dist(a,b)/.04))
        for j in range(count):
            t=j/count;dense.append((a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1])))
    return dense

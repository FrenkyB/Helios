"""Apply the 5B-DBY Olympia livery to the saved, corrected 737 Classic.

Existing mesh geometry and cockpit glazing are never rebuilt. Tail artwork is
UV sampled from the user-supplied photograph, packed inside the final .blend.
"""
from pathlib import Path
import argparse, sys, json, hashlib, math
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'assets'/'helios'

def mesh_signature(o):
    import struct
    h=hashlib.sha256(o.type.encode())
    h.update(str(tuple(v for r in o.matrix_world for v in r)).encode())
    if o.type=='MESH':
        for v in o.data.vertices:h.update(struct.pack('<3f',*v.co))
        for p in o.data.polygons:h.update(str(tuple(p.vertices)).encode())
    elif o.type=='CURVE':
        for s in o.data.splines:
            for v in s.points:h.update(str(tuple(v.co)).encode())
    return h.hexdigest()

def srgb(v):return v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4
def rgb(h):return tuple(srgb(int(h[i:i+2],16)/255) for i in (0,2,4))

def solid(name,color,rough=.32):
    m=bpy.data.materials.new(name);m.diffuse_color=(*rgb(color),1);m.use_nodes=True
    p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=m.diffuse_color
    p.inputs['Roughness'].default_value=rough;p.inputs['Metallic'].default_value=.05
    return m

def paint(name,all_blue=False):
    m=solid(name,'F5F3E9');n=m.node_tree.nodes;l=m.node_tree.links
    def node(t):return n.new(t)
    def op(t,a,b=None):
        q=node('ShaderNodeMath');q.operation=t
        for i,v in enumerate((a,b)):
            if v is None:continue
            if isinstance(v,(float,int)):q.inputs[i].default_value=v
            else:l.new(v,q.inputs[i])
        return q.outputs[0]
    # Stored aircraft coordinates keep the paint attached when the aircraft is
    # moved, rotated or collection-instanced into an airport scene.
    pos=node('ShaderNodeAttribute');pos.attribute_name='Helios_rest_position'
    sep=node('ShaderNodeSeparateXYZ');l.new(pos.outputs['Vector'],sep.inputs[0])
    x,z=sep.outputs['X'],sep.outputs['Z']
    # The diagonal blue boundary wraps continuously around the aft fuselage.
    mask=1 if all_blue else op('GREATER_THAN',op('ADD',x,op('MULTIPLY',z,.40)),25.6)
    dx=op('SUBTRACT',x,31.1);dz=op('SUBTRACT',z,8.75)
    radius=op('SQRT',op('ADD',op('MULTIPLY',dx,dx),op('MULTIPLY',dz,dz)))
    stripe=op('LESS_THAN',op('MODULO',radius,.78),.047)
    mix=node('ShaderNodeMixRGB');mix.blend_type='MIX';l.new(stripe,mix.inputs[0])
    mix.inputs[1].default_value=(*rgb('086DA3'),1);mix.inputs[2].default_value=(*rgb('DAB64B'),1)
    outer=node('ShaderNodeMixRGB');outer.inputs[1].default_value=(*rgb('F5F3E9'),1)
    l.new(mix.outputs[0],outer.inputs[2])
    if all_blue:outer.inputs[0].default_value=1
    else:l.new(mask,outer.inputs[0])
    l.new(outer.outputs[0],n.get('Principled BSDF').inputs['Base Color'])
    return m

def main():
    p=argparse.ArgumentParser();p.add_argument('--source',default=str(ROOT/'models'/'Boeing_737-300.blend'))
    p.add_argument('--skip-render',action='store_true');p.add_argument('--draft',action='store_true')
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    output=ROOT/'models'/'Boeing_737-300_Helios_Livery.blend'
    for d in ['models','reports','renders/helios']:(ROOT/d).mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(Path(a.source).resolve()))
    scene=bpy.data.scenes['HEL-1 | Boeing 737-300'];bpy.context.window.scene=scene
    for s in bpy.data.scenes:
        for vl in s.view_layers:vl.update()
    before={o.name:mesh_signature(o) for o in bpy.data.objects}
    material_slots={o.name:[m.name if m else None for m in o.data.materials] for o in bpy.data.objects if hasattr(o.data,'materials')}
    collection=bpy.data.collections.new('08_HELIOS_Livery');scene.collection.children.link(collection)
    gold=solid('HELIOS | golden yellow','EFC642');black=solid('HELIOS | title outline','302D23')
    ink=solid('HELIOS | small lettering','333C42');white=solid('HELIOS | door on blue','E8E6DA')
    blue=solid('HELIOS | nacelle blue','0875B2');fuselage=paint('HELIOS | fuselage white blue gold')
    tail=paint('HELIOS | fin blue gold rings',True)
    bpy.data.objects['Fuselage | continuous quad loft'].data.materials[0]=fuselage
    for name in ['Vertical fin with dorsal fillet','Rudder']:bpy.data.objects[name].data.materials[0]=tail
    for name in ['Fuselage | continuous quad loft','Vertical fin with dorsal fillet','Rudder']:
        obj=bpy.data.objects[name]
        attribute=obj.data.attributes.get('Helios_rest_position') or obj.data.attributes.new('Helios_rest_position','FLOAT_VECTOR','POINT')
        for vertex,value in zip(obj.data.vertices,attribute.data):value.vector=obj.matrix_world@vertex.co
    for side in ['L','R']:
        bpy.data.objects['CFM56-3 nacelle_'+side].data.materials[0]=blue
        for name in ['Aft door_'+side,'Exit stencil_Aft door_'+side]:
            bpy.data.objects[name].data.materials[0]=white
    def bvh_for(obj):
        return BVHTree.FromPolygons([obj.matrix_world@v.co for v in obj.data.vertices],[tuple(p.vertices) for p in obj.data.polygons])
    shell=bvh_for(bpy.data.objects['Fuselage | continuous quad loft'])
    fins=[bvh_for(bpy.data.objects[n]) for n in ['Vertical fin with dorsal fillet','Rudder']]
    def project(x,z,side,trees,offset):
        hits=[]
        for tree in trees:
            loc,norm,idx,dist=tree.ray_cast(Vector((x,side*8,z)),Vector((0,-side,0)),16)
            if loc is not None:hits.append((dist,loc,norm))
        if not hits and trees is fins:
            # Bridge the existing narrow fin/rudder hinge gap for the decal.
            for shift in [-.025,.025]:
                for tree in trees:
                    loc,norm,idx,dist=tree.ray_cast(Vector((x+shift,side*8,z)),Vector((0,-side,0)),16)
                    if loc is not None:
                        loc.x=x;hits.append((dist,loc,norm))
        if not hits:raise ValueError(f'Livery misses surface: {x}, {z}')
        _,loc,norm=min(hits,key=lambda h:h[0]);return tuple(loc+norm*offset)
    def mesh(name,verts,faces,mat):
        d=bpy.data.meshes.new(name);d.from_pydata(verts,[],faces);d.update()
        o=bpy.data.objects.new(name,d);collection.objects.link(o);d.materials.append(mat)
        for f in d.polygons:f.use_smooth=True
        return o
    # Vector glyphs are cached as mesh outlines, so future builds need no fonts.
    cache_path=ASSETS/'lettering_geometry.json'
    cache=json.loads(cache_path.read_text()) if cache_path.exists() else {}
    font_path=Path('C:/Windows/Fonts/ROCKEB.TTF')
    font=bpy.data.fonts.load(str(font_path)) if font_path.exists() else None
    used_keys=set()
    def letters(text,border=False,title=False):
        key=f'{text}|{border}|{title}|'+('rockwell-extra-bold' if title else 'bfont')
        used_keys.add(key)
        if key in cache:return cache[key]
        d=bpy.data.curves.new('Lettering template','FONT');d.body=text;d.size=1
        d.resolution_u=16;d.offset=.009 if border else 0;d.extrude=0
        if title and font:d.font=font
        o=bpy.data.objects.new('Lettering template',d);collection.objects.link(o)
        bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.context.view_layer.objects.active=o
        bpy.ops.object.convert(target='MESH');o=bpy.context.object
        import bmesh
        bm=bmesh.new();bm.from_mesh(o.data);bmesh.ops.triangulate(bm,faces=list(bm.faces))
        bmesh.ops.subdivide_edges(bm,edges=list(bm.edges),cuts=2,use_grid_fill=True)
        bm.to_mesh(o.data);bm.free()
        data={'verts':[list(v.co) for v in o.data.vertices],'faces':[list(p.vertices) for p in o.data.polygons]}
        bpy.data.objects.remove(o,do_unlink=True);cache[key]=data;return data
    def text_decal(label,text,x,z,width,height,side,mat,border=False,title=False):
        data=letters(text,border,title);base=letters(text,False,title)['verts']
        xmin=min(v[0] for v in base);xmax=max(v[0] for v in base)
        zmin=min(v[1] for v in base);zmax=max(v[1] for v in base)
        verts=[]
        for vx,vy,_ in data['verts']:
            u=(vx-xmin)/(xmax-xmin)
            px=x+width*(u if side==-1 else 1-u);pz=z+height*(vy-zmin)/(zmax-zmin)
            verts.append(project(px,pz,side,[shell],.005 if border else .008))
        return mesh(f'HELIOS | {label} {side}',verts,data['faces'],mat)
    for side in [-1,1]:
        text_decal('title outline','HELIOS',5.7,3.00,8.25,1.59,side,black,True,True)
        text_decal('title','HELIOS',5.7,3.00,8.25,1.59,side,gold,False,True)
        text_decal('website aft','www.flyhelios.com',18.1,4.06,4.2,.26,side,ink)
        text_decal('website nose','www.flyhelios.com',1.9,2.54,2.12,.15,side,ink)
        text_decal('aircraft name','OLYMPIA',1.85,3.33,1.03,.14,side,ink)
        text_decal('registration','5B-DBY',22.2,2.64,1.63,.24,side,ink)
    ASSETS.mkdir(parents=True,exist_ok=True)
    cache_path.write_text(json.dumps({k:cache[k] for k in sorted(used_keys)},separators=(',',':')),encoding='utf-8')
    # Trace only the gold head, leaving the blue and rings procedural and crisp.
    im=bpy.data.images.load(str(ASSETS/'helios_tail_reference.webp'),check_existing=True);im.pack()
    m=solid('HELIOS | photographic gold head','D8B34A',.44)
    tex=m.node_tree.nodes.new('ShaderNodeTexImage');tex.image=im;tex.interpolation='Linear'
    bs=m.node_tree.nodes.get('Principled BSDF');m.node_tree.links.new(tex.outputs['Color'],bs.inputs['Base Color'])
    # Outline in pixels of the supplied 1038 x 632 side photograph.
    outline=[(844,253),(849,246),(858,240),(870,235),(883,235),(896,240),(905,246),(911,258),(908,275),(902,291),(895,306),(885,316),(873,314),(862,307),(854,296),(849,279)]
    cx,cy=878,274
    for side in [-1,1]:
        verts=[];uvs=[];rings=18;n=len(outline)
        for j in range(rings+1):
            r=j/rings
            for px,py in outline:
                ix=cx+r*(px-cx);iy=cy+r*(py-cy)
                # Mirror installation, but retain readable artwork on each side.
                x=31.1+(ix-cx)*.022*(1 if side==-1 else -1);z=8.75-(iy-cy)*.027
                verts.append(project(x,z,side,fins,.011));uvs.append((ix/1038,1-iy/632))
        faces=[(j*n+k,j*n+(k+1)%n,(j+1)*n+(k+1)%n,(j+1)*n+k) for j in range(rings) for k in range(n)]
        o=mesh(f'HELIOS | tail head {side}',verts,faces,m);uv=o.data.uv_layers.new(name='Photo decal')
        for loop in o.data.loops:uv.data[loop.index].uv=uvs[loop.vertex_index]
    bpy.context.view_layer.update()
    assert before=={n:mesh_signature(bpy.data.objects[n]) for n in before},'Original geometry changed'
    scene['livery']='Helios Airways 5B-DBY Olympia; supplied photographic references'
    scene['livery_notes']='Gold head sampled from supplied side photo; rings and markings reconstructed visually.'
    if not a.skip_render:
        saved=(scene.camera,scene.render.resolution_x,scene.render.resolution_y,scene.render.resolution_percentage,scene.render.filepath,scene.cycles.samples)
        specs=[('port','Camera | port orthographic'),('hero','Camera | front three-quarter'),('tail','Camera | rear three-quarter')]
        qa_data=bpy.data.cameras.new('Temporary livery QA');qa=bpy.data.objects.new('Temporary livery QA',qa_data)
        scene.collection.objects.link(qa);qa_data.type='ORTHO'
        specs.extend([('starboard',None),('tail_detail',None)])
        for label,cam in specs:
            if cam:scene.camera=bpy.data.objects[cam]
            else:
                loc,target,scale=((16.7,65,5.4),(16.7,0,5.4),37.5) if label=='starboard' else ((27.6,-30,8.4),(28.5,0,7.1),10)
                qa.location=loc;qa.rotation_euler=(Vector(target)-qa.location).to_track_quat('-Z','Y').to_euler();qa_data.ortho_scale=scale
                scene.camera=qa
            scene.render.resolution_x=1800;scene.render.resolution_y=1100
            scene.render.resolution_percentage=65 if a.draft else 100;scene.cycles.samples=24 if a.draft else 64
            scene.render.filepath=str(ROOT/'renders'/'helios'/f'{label}.png');print('RENDER',label,flush=True)
            bpy.ops.render.render(write_still=True)
        scene.camera,scene.render.resolution_x,scene.render.resolution_y,scene.render.resolution_percentage,scene.render.filepath,scene.cycles.samples=saved
        bpy.data.objects.remove(qa,do_unlink=True);bpy.data.cameras.remove(qa_data)
    bpy.ops.object.select_all(action='DESELECT')
    # Open with shader materials visible, including the procedural aft paint.
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':area.spaces.active.shading.type='MATERIAL'
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(output))
    bpy.ops.wm.open_mainfile(filepath=str(output))
    for s in bpy.data.scenes:
        for vl in s.view_layers:vl.update()
    unchanged=before=={n:mesh_signature(bpy.data.objects[n]) for n in before}
    changed_material_objects=sorted(n for n,slots in material_slots.items() if slots!=[m.name if m else None for m in bpy.data.objects[n].data.materials])
    expected={'Fuselage | continuous quad loft','Vertical fin with dorsal fillet','Rudder'}|{f'{n}{s}' for n in ['CFM56-3 nacelle_','Aft door_','Exit stencil_Aft door_'] for s in ['L','R']}
    material_scope=set(changed_material_objects)==expected
    packed=all(i.packed_file is not None for i in bpy.data.images if i.name=='helios_tail_reference.webp')
    report={'output':str(output),'original_objects_preserved':len(before),'all_original_geometry_unchanged':unchanged,
            'changed_material_objects':changed_material_objects,'material_changes_within_livery_scope':material_scope,'photograph_packed':packed,
            'scenes':sorted(s.name for s in bpy.data.scenes),'passed':unchanged and material_scope and packed}
    (ROOT/'reports'/'helios_livery.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('LIVERY_VERIFIED',json.dumps(report),flush=True)
    if not report['passed']:raise RuntimeError('Saved livery verification failed')

if __name__=='__main__':main()

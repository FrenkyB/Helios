"""Edit only exterior cockpit glazing on an existing .blend, never rebuild the plane.

Run via python run_all.py --correct-cockpit. Front coordinates are traced visual
proportions from the Norwegian front photograph and NASA/Dryden line drawing.
Surface positions are ray-cast onto the actual saved nose mesh, not regenerated.
"""
from pathlib import Path
import sys, json, hashlib, struct, argparse
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import geometry as g

# Right half front projection: lateral Y and vertical Z, metres.
# Front windshield, sliding side window, rear side window.
PANES=[
    [(.045,3.650),(.790,3.610),(.715,4.015),(.045,4.015)],
    [(.855,3.590),(1.190,3.480),(.975,4.025),(.795,4.020)],
    [(1.245,3.505),(1.365,3.690),(1.115,4.035),(1.030,4.030)],
]

def allowed(name):
    return name.startswith(('Cockpit pane_','Cockpit frame_','Wiper_'))

def fingerprint(obj):
    h=hashlib.sha256()
    def values(vals):h.update(struct.pack('<'+'d'*len(vals),*vals))
    h.update(obj.type.encode());values([v for row in obj.matrix_world for v in row])
    h.update(str(sorted(c.name for c in obj.users_collection)).encode())
    h.update(str((obj.hide_render,obj.hide_viewport,obj.parent.name if obj.parent else None)).encode())
    d=obj.data
    if obj.type=='MESH':
        for v in d.vertices:values(tuple(v.co))
        for p in d.polygons:
            h.update(str((tuple(p.vertices),p.material_index,p.use_smooth)).encode())
        for layer in d.uv_layers:
            h.update(layer.name.encode())
            for uv in layer.data:values(tuple(uv.uv))
    elif obj.type in {'CURVE','FONT'}:
        if obj.type=='FONT':h.update(d.body.encode())
        else:
            for sp in d.splines:
                for p in sp.points:values(tuple(p.co))
                for p in sp.bezier_points:values(tuple(p.co))
        values([d.bevel_depth,d.extrude])
    if d and hasattr(d,'materials'):h.update(str([m.name if m else None for m in d.materials]).encode())
    for mod in obj.modifiers:
        h.update((mod.name+mod.type).encode())
        for prop in mod.bl_rna.properties:
            if prop.type in {'BOOLEAN','INT','FLOAT','STRING','ENUM'} and prop.identifier!='rna_type':
                try:h.update(str((prop.identifier,getattr(mod,prop.identifier))).encode())
                except Exception:pass
    return h.hexdigest()

def snapshot():
    return {o.name:fingerprint(o) for o in bpy.data.objects if not allowed(o.name)}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--source',default=str(ROOT/'models'/'HEL-1_Boeing_737-300.blend'))
    p.add_argument('--skip-render',action='store_true')
    p.add_argument('--draft',action='store_true')
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    source=Path(a.source).resolve()
    output=ROOT/'models'/'Boeing_737-300.blend'
    source_sha256=hashlib.sha256(source.read_bytes()).hexdigest()
    bpy.ops.wm.open_mainfile(filepath=str(source))
    scene=bpy.data.scenes['HEL-1 | Boeing 737-300'];bpy.context.window.scene=scene
    bpy.context.view_layer.update()
    before=snapshot()
    before_targets={o.name:fingerprint(o) for o in bpy.data.objects if allowed(o.name)}
    shell=bpy.data.objects['Fuselage | continuous quad loft']
    verts=[shell.matrix_world@v.co for v in shell.data.vertices]
    bvh=BVHTree.FromPolygons(verts,[tuple(f.vertices) for f in shell.data.polygons])
    fit_errors=[]
    def point(y,z,side,offset=.005):
        loc,normal,face,distance=bvh.ray_cast(Vector((-2,y,z)),Vector((1,0,0)),12)
        if loc is None:raise ValueError(f'Window point misses nose: {y}, {z}')
        fit_errors.append(abs((loc+normal*offset-loc).length-offset))
        fitted=loc+normal*offset
        return (fitted.x,side*fitted.y,fitted.z)
    def uvpoint(poly,u,v):
        w=[(1-u)*(1-v),u*(1-v),u*v,(1-u)*v]
        return [sum(ww*pt[k] for ww,pt in zip(w,poly)) for k in [0,1]]
    def replace_mesh(obj,verts,faces):
        old=obj.data
        new=bpy.data.meshes.new(old.name+'_Corrected')
        new.from_pydata(verts,[],faces);new.update()
        for m in old.materials:new.materials.append(m)
        for f in new.polygons:f.use_smooth=True
        uv=new.uv_layers.new(name='UV_Glazing')
        for loop in new.loops:
            co=new.vertices[loop.vertex_index].co
            uv.data[loop.index].uv=(co.y,co.z)
        obj.data=new
        if old.users==0:bpy.data.meshes.remove(old)
    def replace_curve(obj,points,radius):
        old=obj.data;new=bpy.data.curves.new(old.name+'_Corrected','CURVE')
        new.dimensions='3D';new.resolution_u=1;new.bevel_depth=radius;new.bevel_resolution=3
        sp=new.splines.new('POLY');sp.points.add(len(points)-1)
        for v,co in zip(sp.points,points):v.co=(*co,1)
        sp.use_cyclic_u=not obj.name.startswith('Wiper_')
        for mat in old.materials:new.materials.append(mat)
        obj.data=new
        if old.users==0:bpy.data.curves.remove(old)
    for side,tag in [(-1,'L'),(1,'R')]:
        for i,poly in enumerate(PANES,1):
            # Keep the photographed front silhouette at the corners. For the
            # side panes, interpolate in side elevation to avoid a bowed aft
            # edge when a straight front line wraps over the rounded nose.
            corners=[point(y,z,1,0) for y,z in poly]
            side_poly=[(co[0],co[2]) for co in corners]
            def pane_point(u,v,offset=.005):
                if i==1:return point(*uvpoint(poly,u,v),side,offset)
                x,z=uvpoint(side_poly,u,v)
                loc,normal,face,distance=bvh.ray_cast(Vector((x,4,z)),Vector((0,-1,0)),8)
                if loc is None:raise ValueError(f'Side pane misses nose: {x}, {z}')
                fitted=loc+normal*offset
                return (fitted.x,side*fitted.y,fitted.z)
            n=32
            vv=[pane_point(k/n,j/n) for j in range(n+1) for k in range(n+1)]
            ff=[(j*(n+1)+k,j*(n+1)+k+1,(j+1)*(n+1)+k+1,(j+1)*(n+1)+k) for j in range(n) for k in range(n)]
            if side==1:ff=[tuple(reversed(face)) for face in ff]
            replace_mesh(bpy.data.objects[f'Cockpit pane_{tag}_{i}'],vv,ff)
            outline=[]
            uv_corners=[(0,0),(1,0),(1,1),(0,1)]
            for k,aa in enumerate(uv_corners):
                bb=uv_corners[(k+1)%len(uv_corners)]
                for j in range(32):
                    t=j/32
                    outline.append(pane_point(aa[0]+t*(bb[0]-aa[0]),aa[1]+t*(bb[1]-aa[1]),.008))
            replace_curve(bpy.data.objects[f'Cockpit frame_{tag}_{i}'],outline,.007)
        for i in [4,5]:
            for prefix in ['Cockpit pane_','Cockpit frame_']:
                obj=bpy.data.objects.get(f'{prefix}{tag}_{i}')
                if obj:bpy.data.objects.remove(obj,do_unlink=True)
        # One correctly seated windshield wiper per pilot, parked at the lower edge.
        wiper=bpy.data.objects[f'Wiper_{tag}_0']
        path=[(.66,3.598),(.50,3.670),(.25,3.665),(.08,3.660)]
        replace_curve(wiper,[point(y,z,side,.026) for y,z in path],.010)
        extra=bpy.data.objects.get(f'Wiper_{tag}_1')
        if extra:bpy.data.objects.remove(extra,do_unlink=True)
    bpy.context.view_layer.update()
    after=snapshot()
    if before!=after:raise RuntimeError('An object outside the cockpit-glazing scope changed.')
    # Use existing scene/cameras, restore presentation settings before saving.
    render_dir=ROOT/'renders'/'cockpit_correction';render_dir.mkdir(exist_ok=True)
    if not a.skip_render:
        settings=(scene.camera,scene.render.resolution_x,scene.render.resolution_y,scene.render.resolution_percentage,scene.render.filepath,scene.cycles.samples)
        specs=[('front',(-18,0,3.5),(2,0,3.5),5.6),
               ('side',(2.35,-18,3.2),(2.35,0,3.2),6.5),
               ('three_quarter',(-4,-9,5.8),(2.2,0,3.4),7.2)]
        # Temporary QA camera is removed before the corrected file is saved.
        camdata=bpy.data.cameras.new('Temporary cockpit inspection')
        cam=bpy.data.objects.new('Temporary cockpit inspection',camdata);scene.collection.objects.link(cam)
        camdata.type='ORTHO'
        for name,loc,target,scale in specs:
            cam.location=loc;cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();camdata.ortho_scale=scale
            scene.camera=cam;scene.render.resolution_x=1500;scene.render.resolution_y=1100
            scene.render.resolution_percentage=60 if a.draft else 100;scene.cycles.samples=24 if a.draft else 64
            scene.render.filepath=str(render_dir/f'{name}.png')
            print('RENDER cockpit correction',name,flush=True)
            bpy.ops.render.render(write_still=True)
        bpy.data.objects.remove(cam,do_unlink=True);bpy.data.cameras.remove(camdata)
        scene.camera,scene.render.resolution_x,scene.render.resolution_y,scene.render.resolution_percentage,scene.render.filepath,scene.cycles.samples=settings
    changed=[o.name for o in bpy.data.objects if allowed(o.name) and fingerprint(o)!=before_targets.get(o.name)]
    removed=sorted(set(before_targets)-set(o.name for o in bpy.data.objects if allowed(o.name)))
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(output))
    bpy.ops.wm.open_mainfile(filepath=str(output))
    bpy.context.view_layer.update()
    reopened=snapshot()
    unchanged=before==reopened
    result={'source':str(source),'output':str(output),'source_sha256':source_sha256,
        'output_sha256':hashlib.sha256(output.read_bytes()).hexdigest(),
        'scope':'Exterior cockpit panes, seals, and wipers only. Eyebrow glazing removed to match the two supplied photographs.',
        'changed_objects':changed,'removed_objects':removed,'untouched_object_count':len(before),
        'all_other_objects_identical_after_reopen':unchanged,'nose_mesh_unchanged':before.get('Fuselage | continuous quad loft')==reopened.get('Fuselage | continuous quad loft'),
        'front_coordinates_m':PANES,'max_raycast_offset_error_m':max(fit_errors),'passed':unchanged}
    (ROOT/'reports'/'cockpit_correction.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('CORRECTION_VERIFIED',json.dumps(result),flush=True)
    if not unchanged:raise RuntimeError('Saved-file preservation check failed.')

if __name__=='__main__':main()

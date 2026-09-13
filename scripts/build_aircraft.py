"""Blender entry point. Normally invoked by ../run_all.py."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import argparse
import json
import math
import bpy
import bmesh
from mathutils import Vector
import geometry as g
import exterior

def args():
    p=argparse.ArgumentParser()
    p.add_argument('--skip-render',action='store_true')
    p.add_argument('--views',default='hero,side,front,top,rear,engine')
    p.add_argument('--draft',action='store_true')
    p.add_argument('--exterior-only',action='store_true')
    return p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])

def camera(name,loc,target,scale):
    d=bpy.data.cameras.new(name)
    obj=bpy.data.objects.new(name,d);g.COL.objects.link(obj)
    obj.location=loc;obj.rotation_euler=(Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler()
    d.type='ORTHO';d.ortho_scale=scale;d.clip_end=500
    return obj

def setup_stage(cfg):
    stage=g.collection('90_Studio');g.use(stage)
    floor=g.material('Studio | slate',(.15,.19,.23),.04,.62)
    g.cube('Studio floor',(16,0,-.055),(200,200,.10),floor,0)
    for name,loc,power,size in [('Key softbox',(-8,-20,31),14500,19),('Fill softbox',(12,22,19),12500,17),('Tail rim',(37,8,26),16000,14)]:
        data=bpy.data.lights.new(name,'AREA');data.energy=power;data.shape='DISK';data.size=size
        obj=bpy.data.objects.new(name,data);stage.objects.link(obj);obj.location=loc
        obj.rotation_euler=(Vector((16,0,2))-obj.location).to_track_quat('-Z','Y').to_euler()
    scene=bpy.context.scene
    world=bpy.data.worlds.new('Neutral studio environment');scene.world=world;world.use_nodes=True
    world.node_tree.nodes['Background'].inputs[0].default_value=(.38,.44,.52,1)
    world.node_tree.nodes['Background'].inputs[1].default_value=.40
    g.use(g.collection('91_Cameras'))
    cams={
      'hero':camera('Camera | front three-quarter',(-19,-42,22),(15,0,3.0),43),
      'side':camera('Camera | port orthographic',(16.7,-65,5.4),(16.7,0,5.4),37.5),
      'front':camera('Camera | front orthographic',(-65,0,5.2),(16,0,5.2),33),
      'top':camera('Camera | top orthographic',(16.7,0,70),(16.7,0,0),48),
      'rear':camera('Camera | rear three-quarter',(51,-37,19),(17,0,3.4),42),
      'engine':camera('Camera | CFM56-3 detail',(3.0,-11,4.5),(12.7,-4.7,1.75),8.1),
      'nose':camera('Camera | cockpit glazing',(-3,-9,7),(2.7,0,3.4),8),
    }
    cams['top'].rotation_euler=(0,0,0)
    scene.camera=cams['hero']
    scene.render.engine='CYCLES'
    scene.cycles.samples=cfg['render_samples'];scene.cycles.use_denoising=True
    scene.cycles.max_bounces=6
    scene.render.resolution_x=cfg['render_resolution'][0];scene.render.resolution_y=cfg['render_resolution'][1]
    scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG'
    scene.view_settings.view_transform='AgX'
    # CPU fallback is always available. Use a supported GPU only after discovery.
    prefs=bpy.context.preferences.addons['cycles'].preferences
    for backend in ['OPTIX','CUDA','HIP','ONEAPI']:
        try:
            prefs.compute_device_type=backend;prefs.get_devices()
            available=[d for d in prefs.devices if d.type==backend]
            if available:
                for d in prefs.devices:d.use=d.type==backend
                scene.cycles.device='GPU';print('Render device:',backend,flush=True);break
        except Exception:
            continue
    return stage,cams

def validate(root,cfg):
    bpy.context.view_layer.update()
    objects=list(root.all_objects)
    meshes=[o for o in objects if o.type=='MESH']
    bounds=[o.matrix_world@Vector(v) for o in meshes for v in o.bound_box]
    low=[min(v[i] for v in bounds) for i in range(3)];high=[max(v[i] for v in bounds) for i in range(3)]
    fus=bpy.data.objects['Fuselage | continuous quad loft']
    bm=bmesh.new();bm.from_mesh(fus.data)
    issues={'fuselage_nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),
            'fuselage_degenerate_faces':sum(f.calc_area()<1e-10 for f in bm.faces)}
    bm.free()
    checks={
        'overall_length':abs(high[0]-low[0]-cfg['overall_length'])<.04,
        'wingspan':abs(high[1]-low[1]-cfg['wingspan'])<.06,
        'fuselage_width':abs(fus.dimensions.y-cfg['fuselage_width'])<.01,
        'tail_height':abs(high[2]-cfg['tail_height'])<.02,
        'tires_touch_ground':abs(low[2])<.01,
        'fuselage_closed_manifold':issues['fuselage_nonmanifold_edges']==0,
        'fuselage_no_degenerate_faces':issues['fuselage_degenerate_faces']==0,
        'two_nacelles':sum(o.name.startswith('CFM56-3 nacelle_') for o in meshes)==2,
        'six_tires':sum(o.name.startswith(('Main tire_','Nose tire_')) and not any(k in o.name for k in ['hub','axle','tread']) for o in meshes)==6,
    }
    report={'task':'HEL-1','blender':bpy.app.version_string,'units':'m','object_count':len(objects),
            'mesh_objects':len(meshes),'vertices':sum(len(o.data.vertices) for o in meshes),
            'polygons':sum(len(o.data.polygons) for o in meshes),
            'bounds_min':low,'bounds_max':high,'dimensions':[high[i]-low[i] for i in range(3)],
            'checks':checks,'geometry':issues,'passed':all(checks.values()),
            'limitations':['Exterior base mesh, not engineering CAD.','Windows are surface glazing inserts, not cut-through apertures.',
            'Control surface shapes, airfoils, fan and small fittings are visually reconstructed.',
            'Unrigged, gear down and flaps retracted. UV_Base is a starting projection, not a finished paint atlas.']}
    (ROOT/'reports'/'validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('VALIDATION',json.dumps(report),flush=True)
    if not report['passed']:raise RuntimeError('Dimension or topology check failed; see reports/validation.json')
    return report

def main():
    options=args()
    for name in ['models','renders','reports','logs']:(ROOT/name).mkdir(exist_ok=True)
    cfg=json.loads((ROOT/'config'/'aircraft.json').read_text())
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    for col in list(bpy.data.collections):
        if col.users==0 or col.name=='Collection':bpy.data.collections.remove(col)
    scene=bpy.context.scene;scene.name='HEL-1 | Boeing 737-300'
    scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1
    scene['Jira']='HEL-1';scene['Variant']='737-300 Classic, CFM56-3, no winglets'
    scene['Coordinate system']='X aft from nose, +Y starboard, +Z up, metres, Z=0 ground'
    scene['Reference']='Boeing D6-58325-6 Rev E, 2-12 and 2-17; supplied reference pack'
    root=g.collection('B737_300_EXTERIOR')
    mats=exterior.build(root,cfg)
    stage,cams=setup_stage(cfg)
    validate(root,cfg)
    interior_scenes={}
    if not options.exterior_only:
        import interiors
        print('Building existing cockpit study and integrated passenger cabin',flush=True)
        interior_scenes=interiors.build(mats,cfg)
    readme=bpy.data.texts.new('HEL-1_README')
    readme.write('BOEING 737-300 CLASSIC | HEL-1\n\nEditable exterior base mesh at true scale in metres.\n'+
        'Collections 01-07 organize structural parts and fittings. 90 is the studio.\n'+
        'All cameras are named. Default is front three-quarter.\n'+
        'Surface glazing, unrigged landing gear, reconstructed airfoils.\n'+
        'Passenger geometry is shared with the aircraft; scenes 03 Cabin and 04 Layout expose the interior.\n'+
        'Read ../README.md and ../reports/validation.json for scope and checks.\n'+
        'Regenerate with: python run_all.py\n')
    # Save an immediately useful modeling view and keep studio out of viewport clutter.
    stage.hide_viewport=True
    bpy.ops.object.select_all(action='DESELECT')
    fus=bpy.data.objects['Fuselage | continuous quad loft'];fus.select_set(True);bpy.context.view_layer.objects.active=fus
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':
                area.spaces.active.region_3d.view_distance=45
                area.spaces.active.region_3d.view_location=(16,0,3)
                area.spaces.active.region_3d.view_rotation=cams['hero'].rotation_euler.to_quaternion()
                area.spaces.active.clip_end=1000
                area.spaces.active.shading.color_type='MATERIAL'
    bpy.context.preferences.filepaths.save_version=0
    blend=ROOT/'models'/'HEL-1_Boeing_737-300.blend'
    # Store the final render targets before saving; opening the blend is enough to use F12.
    scene.render.filepath=str(ROOT/'renders'/'HEL-1_hero.png')
    for name,interior_scene in interior_scenes.items():
        interior_scene.render.filepath=str(ROOT/'renders'/f'HEL-1_{name}.png')
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    if not options.skip_render:
        if options.draft:
            scene.render.resolution_percentage=60;scene.cycles.samples=20
        for view in options.views.split(','):
            if view not in cams:raise ValueError('Unknown view: '+view)
            scene.camera=cams[view]
            bpy.data.objects['Studio floor'].hide_render=view in ['top','side','front']
            scene.render.filepath=str(ROOT/'renders'/f'HEL-1_{view}.png')
            print('RENDER',view,flush=True)
            bpy.ops.render.render(write_still=True)
        scene.camera=cams['hero']
        bpy.data.objects['Studio floor'].hide_render=False
        for name,interior_scene in interior_scenes.items():
            if options.draft:
                interior_scene.render.resolution_percentage=60;interior_scene.cycles.samples=20
            interior_scene.render.filepath=str(ROOT/'renders'/f'HEL-1_{name}.png')
            print('RENDER',name,flush=True)
            bpy.ops.render.render(write_still=True,scene=interior_scene.name)
    print('COMPLETE',blend,flush=True)

if __name__=='__main__':main()

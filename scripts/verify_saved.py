"""Reopen the delivered .blend and verify actual persisted geometry and scene data."""
from pathlib import Path
import json
import math
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1]
path=ROOT/'models'/'HEL-1_Boeing_737-300.blend'
bpy.ops.wm.open_mainfile(filepath=str(path))
scene=bpy.data.scenes['HEL-1 | Boeing 737-300']
bpy.context.window.scene=scene
bpy.context.view_layer.update()
root=bpy.data.collections['B737_300_EXTERIOR']
objects=list(root.all_objects)
meshes=[o for o in objects if o.type=='MESH']
extents=[o.matrix_world@Vector(p) for o in meshes for p in o.bound_box]
low=[min(v[k] for v in extents) for k in range(3)]
high=[max(v[k] for v in extents) for k in range(3)]
left=bpy.data.objects['CFM56-3 nacelle_L']
right=bpy.data.objects['CFM56-3 nacelle_R']
left_mirrored=sorted((round(v.co.x,5),round(-v.co.y,5),round(v.co.z,5)) for v in left.data.vertices)
right_sorted=sorted((round(v.co.x,5),round(v.co.y,5),round(v.co.z,5)) for v in right.data.vertices)
checks={
    'file_reopened':True,
    'metric_units':scene.unit_settings.system=='METRIC' and scene.unit_settings.scale_length==1,
    'overall_length_33_40_m':abs(high[0]-low[0]-33.4)<.005,
    'wingspan_28_88_m_with_lights':abs(high[1]-low[1]-28.88)<.01,
    'height_11_13_m':abs(high[2]-11.13)<.005,
    'engine_geometry_mirrored':left_mirrored==right_sorted,
    'engine_clearance_in_boeing_range':.46<min(v.co.z for v in left.data.vertices)<.54,
    'finite_vertices':all(math.isfinite(c) for o in meshes for v in o.data.vertices for c in v.co),
    'no_missing_linked_libraries':all(Path(bpy.path.abspath(lib.filepath)).exists() for lib in bpy.data.libraries),
    'hero_camera_saved':scene.camera.name=='Camera | front three-quarter',
    'studio_hidden_only_in_viewport':bpy.data.collections['90_Studio'].hide_viewport and not bpy.data.collections['90_Studio'].hide_render,
}
if 'B737_300_CABIN_STUDY' in bpy.data.collections:
    cabin=bpy.data.collections['B737_300_CABIN_STUDY']
    seats=[o for o in cabin.all_objects if o.name.startswith('Seat_') and o.name.endswith(' cushion')]
    cfg=json.loads((ROOT/'config'/'aircraft.json').read_text())['cabin']
    checks['configured_seat_count']=len(seats)==cfg['rows']*6
    checks['four_scenes_saved']=len(bpy.data.scenes)==4
    checks['passenger_cabin_in_aircraft_scene']=all(o.name in scene.objects for o in seats)
    checks['cabin_separate_editable_collection']=not any(o.name.startswith('Seat_') for o in objects)
result={'file':str(path),'bytes':path.stat().st_size,'blender':bpy.app.version_string,
    'scenes':[s.name for s in bpy.data.scenes],'checks':checks,'passed':all(checks.values()),
    'engine_ground_clearance_m':min(v.co.z for v in left.data.vertices)}
(ROOT/'reports'/'saved_file_verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print('SAVED_FILE_VERIFICATION',json.dumps(result),flush=True)
if not result['passed']:raise RuntimeError('Saved .blend validation failed')

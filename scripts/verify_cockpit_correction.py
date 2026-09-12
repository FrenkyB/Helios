"""Read-only verification of the final correction against the original aircraft."""
import bpy
import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from correct_cockpit_windows import fingerprint,allowed

def read_state(path):
    bpy.ops.wm.open_mainfile(filepath=str(path))
    for scene in bpy.data.scenes:
        bpy.context.window.scene=scene
        bpy.context.view_layer.update()
    objects={o.name:fingerprint(o) for o in bpy.data.objects}
    scene_names=sorted(s.name for s in bpy.data.scenes)
    materials={}
    unused_materials=[]
    for m in bpy.data.materials:
        if m.users==0:
            unused_materials.append(m.name)
            continue
        nodes=[]
        if m.node_tree:
            for n in m.node_tree.nodes:
                sockets=[]
                for s in n.inputs:
                    if hasattr(s,'default_value'):
                        v=s.default_value
                        try:v=tuple(v)
                        except TypeError:pass
                        sockets.append((s.name,str(v)))
                nodes.append((n.name,n.bl_idname,sockets))
        links=sorted((l.from_node.name,l.from_socket.identifier,l.to_node.name,l.to_socket.identifier) for l in m.node_tree.links) if m.node_tree else []
        materials[m.name]=str((tuple(m.diffuse_color),nodes,links))
    return objects,scene_names,materials,unused_materials

original=ROOT/'models'/'HEL-1_Boeing_737-300.blend'
corrected=ROOT/'models'/'Boeing_737-300.blend'
old,old_scenes,old_materials,old_unused=read_state(original)
new,new_scenes,new_materials,new_unused=read_state(corrected)
out_of_scope=[name for name in set(old)|set(new) if not allowed(name) and old.get(name)!=new.get(name)]
modified=sorted(name for name in set(old)&set(new) if old[name]!=new[name])
removed=sorted(set(old)-set(new))
symmetry=[]
for i in [1,2,3]:
    l=bpy.data.objects[f'Cockpit pane_L_{i}'];r=bpy.data.objects[f'Cockpit pane_R_{i}']
    error=max(abs(a.co.x-b.co.x)+abs(a.co.y+b.co.y)+abs(a.co.z-b.co.z) for a,b in zip(l.data.vertices,r.data.vertices))
    symmetry.append(error)
checks={
    'all_non_cockpit_objects_identical_to_original':not out_of_scope,
    'fuselage_mesh_unchanged':old['Fuselage | continuous quad loft']==new['Fuselage | continuous quad loft'],
    'all_used_materials_unchanged':old_materials==new_materials,
    'all_three_original_scenes_preserved':old_scenes==new_scenes,
    'six_exterior_panes':sum(name.startswith('Cockpit pane_') for name in new)==6,
    'two_wipers':sum(name.startswith('Wiper_') for name in new)==2,
    'bilateral_symmetry':max(symmetry)<.0001,
    'only_cockpit_objects_modified_or_removed':all(allowed(n) for n in modified+removed),
}
report={'passed':all(checks.values()),'checks':checks,'modified_objects':modified,'removed_objects':removed,
        'out_of_scope_changes':out_of_scope,'unchanged_objects':len([n for n in old if old[n]==new.get(n)]),
        'unused_materials_removed_on_save':sorted(set(old_unused)-set(new_unused)),
        'max_pane_mirror_error_m':max(symmetry),'original_sha256':hashlib.sha256(original.read_bytes()).hexdigest(),
        'corrected_sha256':hashlib.sha256(corrected.read_bytes()).hexdigest()}
(ROOT/'reports'/'cockpit_preservation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('COCKPIT_PRESERVATION',json.dumps(report),flush=True)
if not report['passed']:raise RuntimeError('Cockpit preservation verification failed')

"""Saved-file behavioral checks, including native drivers with auto-exec disabled."""
import argparse
import json
import math
from pathlib import Path
import re
import sys

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import pressurization_panel as panel
from correct_cockpit_windows import fingerprint
from verify_passenger_cabin import material_state, update_scenes


def protected_state():
    """Include every pre-existing aircraft AND airport object, material and scene."""
    update_scenes()
    root=bpy.data.collections.get(panel.COLLECTION)
    owned=set(root.all_objects) if root else set()
    objects=[o for o in bpy.data.objects if o not in owned]
    materials={m for o in objects if hasattr(o.data,'materials') for m in o.data.materials if m}
    # Airport trees and cabin seats share meshes. Hash their full geometry once
    # per datablock, while still recording each instance's transforms/modifiers.
    data_hashes={}

    def object_state(obj):
        key=obj.data if obj.data else obj
        if key not in data_hashes:
            data_hashes[key]=fingerprint(obj)
        modifiers=[]
        for mod in obj.modifiers:
            values=[]
            for prop in mod.bl_rna.properties:
                if prop.type in {'BOOLEAN','INT','FLOAT','STRING','ENUM'} and prop.identifier!='rna_type':
                    try:
                        values.append((prop.identifier,str(getattr(mod,prop.identifier))))
                    except (AttributeError,TypeError):
                        pass
            modifiers.append((mod.name,mod.type,values))
        return (data_hashes[key],tuple(v for row in obj.matrix_world for v in row),
                sorted(c.name for c in obj.users_collection),obj.parent.name if obj.parent else None,
                obj.hide_viewport,obj.hide_render,obj.instance_type,
                obj.instance_collection.name if obj.instance_collection else None,
                [(s.link,s.material.name if s.material else None) for s in obj.material_slots],modifiers)

    return {'objects':{o.name:object_state(o) for o in objects},
            'materials':{m.name:material_state(m) for m in materials},
            'scenes':{s.name:{'objects':sorted(o.name for o in s.objects),
                               'camera':s.camera.name if s.camera else None,
                               'world':s.world.name if s.world else None}
                      for s in bpy.data.scenes if s.name!=panel.SCENE}}


def verify(path, before=None):
    bpy.ops.wm.open_mainfile(filepath=str(path))
    scene=bpy.data.scenes[panel.SCENE]
    bpy.context.window.scene=scene
    ctrl=bpy.data.objects[panel.CONTROLLER]
    checks={}

    def check(name, condition):
        checks[name]=bool(condition)

    def update(**values):
        for key,value in values.items():
            ctrl[key]=value
        ctrl.update_tag()
        bpy.context.view_layer.update()

    def rotation(name, axis=2):
        return bpy.data.objects[name].evaluated_get(bpy.context.evaluated_depsgraph_get()).rotation_euler[axis]

    def emission(name):
        mat=bpy.data.materials['PRESS | '+name]
        return mat.node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value

    glyphs={'1111110':'0','0110000':'1','1101101':'2','1111001':'3','0110011':'4',
            '1011011':'5','1011111':'6','1110000':'7','1111111':'8','1111011':'9','0000001':'-'}

    def display(name):
        return ''.join(glyphs.get(''.join('1' if emission(f'{name}_D{digit}_{seg}')>0 else '0'
                                         for seg in range(7)), '?') for digit in range(5))

    update()
    check('defaults_warnings_off',not ctrl['auto_fail'] and not ctrl['off_sched_descent'])
    check('defaults_restored',all(ctrl[k]==v for k,v in panel.DEFAULTS.items()))
    check('reference_proportions',abs(bpy.data.objects['PRESS_PANEL_BODY'].dimensions.x /
                                    bpy.data.objects['PRESS_PANEL_BODY'].dimensions.y - 1084/1440)<1e-5)
    root=bpy.data.collections[panel.COLLECTION]
    check('separate_scene_only',all(sum(o.name in s.objects for s in bpy.data.scenes)==1 for o in root.all_objects))
    check('organized_collections',all(name in root.children for name in panel.GROUPS))
    check('no_duplicate_generated_names',not any(re.search(r'\.\d{3}$',o.name) for o in root.all_objects))
    pivots={'KNOB_FLT_ALT':(385,534,.009),'KNOB_LAND_ALT':(385,926,.009),
            'SELECTOR_MODE':(763,921,.012),'SWITCH_VALVE':(812,615,.018),
            'INDICATOR_VALVE':(807,386,.024)}
    check('controls_have_shaft_pivots',all(
        max(abs(a-b) for a,b in zip(bpy.data.objects[name].location,panel.point(*position)))<1e-6
        and bpy.data.objects[name].parent==ctrl and len(bpy.data.objects[name].children)>0
        for name,position in pivots.items()))
    check('controls_unit_scale',all(tuple(bpy.data.objects[name].scale)==(1.,1.,1.) for name in pivots))
    check('inspection_camera',scene.camera is not None and scene.camera.data.type=='ORTHO')
    check('script_embedded',bpy.data.texts.get(panel.SCRIPT) is not None)
    check('seventy_independent_segments',sum(o.name.startswith(('DISPLAY_FLT_ALT_D','DISPLAY_LAND_ALT_D'))
                                           and o.type=='MESH' for o in root.all_objects)==70)
    check('finite_meshes',all(math.isfinite(c) for o in root.all_objects if o.type=='MESH'
                            for v in o.data.vertices for c in v.co))
    check('nondegenerate_faces',all(p.area>1e-12 for o in root.all_objects if o.type=='MESH' for p in o.data.polygons))
    update(flight_altitude=35000,landing_altitude=1250)
    initial=rotation('KNOB_FLT_ALT')
    check('flight_35000',display('DISPLAY_FLT_ALT')=='35000')
    check('landing_01250',display('DISPLAY_LAND_ALT')=='01250')
    update(flight_altitude=12000)
    check('flight_knob_and_display',abs(rotation('KNOB_FLT_ALT')-initial)>1 and display('DISPLAY_FLT_ALT')=='12000')
    check('landing_independent',display('DISPLAY_LAND_ALT')=='01250')
    initial=rotation('KNOB_LAND_ALT')
    update(landing_altitude=-1000)
    check('negative_landing_and_knob',display('DISPLAY_LAND_ALT')=='-1000' and abs(rotation('KNOB_LAND_ALT')-initial)>.1)
    check('flight_independent',display('DISPLAY_FLT_ALT')=='12000')
    for value,expected in [(0,'00000'),(1234,'01250'),(14000,'14000')]:
        update(landing_altitude=value)
        check('landing_'+str(value),display('DISPLAY_LAND_ALT')==expected)
    for value,expected in [(0,'00000'),(12349,'12300'),(42000,'42000')]:
        update(flight_altitude=value)
        check('flight_'+str(value),display('DISPLAY_FLT_ALT')==expected)
    for mode in range(3):
        update(mode=mode)
        check('mode_'+str(mode),abs(rotation('SELECTOR_MODE')-(1-mode)*math.pi/6)<1e-5
              and (emission('ANN_ALTN')>0)==(mode==1) and (emission('ANN_MANUAL')>0)==(mode==2))
        check('warnings_independent_mode_'+str(mode),emission('ANN_AUTO_FAIL')==0 and emission('ANN_OFF_SCHED_DESCENT')==0)
    poses=[]
    for value in (0,.25,.5,.75,1):
        update(valve_position=value)
        poses.append((rotation('SWITCH_VALVE',1),rotation('INDICATOR_VALVE')))
    check('valve_smooth_and_linked',all(a[0]<b[0] and a[1]>b[1] for a,b in zip(poses,poses[1:])))
    # Keyframes on the master must update multiple driven outputs at once.
    for frame,value in [(1,0.),(11,1.)]:
        ctrl['valve_position']=value
        ctrl.keyframe_insert(data_path='["valve_position"]',frame=frame)
    scene.frame_set(6)
    check('animation_midpoint',abs(rotation('SWITCH_VALVE',1))<.001 and abs(rotation('INDICATOR_VALVE'))<.001)
    ctrl.animation_data_clear()
    scene.frame_set(1)
    # Explicitly initialize the embedded UI, also testing idempotent registration.
    namespace={'__name__':'press_panel_verification'}
    exec(compile(bpy.data.texts[panel.SCRIPT].as_string(),panel.SCRIPT,'exec'),namespace)
    namespace['register']()
    for prop,name in [('auto_fail','ANN_AUTO_FAIL'),('off_sched_descent','ANN_OFF_SCHED_DESCENT')]:
        bpy.ops.pressurization.warning(warning=prop)
        check(prop+'_toggle_on',bool(ctrl[prop]) and emission(name)>0)
        bpy.ops.pressurization.warning(warning=prop)
        check(prop+'_toggle_off',not ctrl[prop] and emission(name)==0)
    update(auto_fail=True,off_sched_descent=True)
    bpy.ops.pressurization.reset_warnings()
    check('reset_operator',not ctrl['auto_fail'] and not ctrl['off_sched_descent'])
    # The viewport raycast used by click mode must hit each actual warning region.
    for name,x in [('ANN_AUTO_FAIL',271),('ANN_OFF_SCHED_DESCENT',462)]:
        origin=panel.point(x,88,1)
        hit,loc,normal,index,obj,matrix=scene.ray_cast(bpy.context.evaluated_depsgraph_get(),origin,(0,0,-1))
        check(name+'_click_region',hit and obj.get('warning_property') in ('auto_fail','off_sched_descent'))
    curves=[f for obj in root.all_objects if obj.animation_data for f in obj.animation_data.drivers]
    curves += [f for mat in bpy.data.materials if mat.name.startswith('PRESS |') and mat.node_tree.animation_data
               for f in mat.node_tree.animation_data.drivers]
    check('native_simple_drivers',all(f.driver.is_simple_expression and f.driver.is_valid for f in curves))
    update(**panel.DEFAULTS)
    if before is not None:
        after=protected_state()
        for category in ('objects','materials','scenes'):
            check('existing_'+category+'_preserved',before[category]==after[category])
    report={'file':str(path),'blender':bpy.app.version_string,'passed':all(checks.values()),
            'checks':checks,'panel_objects':len(root.all_objects),'drivers':len(curves),
            'scope':'Reference-based animation asset, not a simulation of aircraft pressure dynamics.'}
    (ROOT/'reports').mkdir(exist_ok=True)
    (ROOT/'reports'/'pressurization_panel_verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('PRESSURIZATION_VERIFIED',json.dumps(report),flush=True)
    if not report['passed']:
        raise RuntimeError('Panel checks failed: '+', '.join(k for k,v in checks.items() if not v))
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',default=str(ROOT/'models'/'Boeing_737-300_Helios_Livery.blend'))
    options=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    verify(Path(options.source))

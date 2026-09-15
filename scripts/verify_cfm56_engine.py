"""Saved-file isolation, geometry, two-spool and animation regression checks."""
import hashlib
import json
import math
from pathlib import Path
import re
import sys

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import cfm56_engine as engine
from correct_cockpit_windows import fingerprint
from verify_passenger_cabin import material_state, update_scenes


def scalar_state(data):
    result = {}
    for prop in data.bl_rna.properties:
        # Blender assigns a fresh session_uid on every load; it is not saved
        # scene content. All persistent geometry and display settings are checked.
        if prop.type in {'BOOLEAN','INT','FLOAT','STRING','ENUM'} and prop.identifier not in {'rna_type','session_uid'}:
            try:
                value = getattr(data,prop.identifier)
                result[prop.identifier] = list(value) if prop.is_array else value
            except (AttributeError,TypeError):
                pass
    return result


def protected_state(raw=False):
    """Hash unrelated objects including the panel; geometry hashed once per mesh."""
    # A file reopened with the engine active has not yet evaluated the airport
    # and panel transforms. Compare evaluated scenes, as the panel verifier does.
    update_scenes()
    objects = [o for o in bpy.data.objects if not o.get(engine.OWNER)]
    data_hashes = {}
    result = {'objects':{},'materials':{},'scenes':{},'collections':{}}
    for obj in objects:
        data = obj.data if obj.data else obj
        if data not in data_hashes:
            data_hashes[data] = fingerprint(obj)
        result['objects'][obj.name] = [data_hashes[data],list(obj.location),list(obj.rotation_euler),
            list(obj.scale),obj.parent.name if obj.parent else None,
            [list(row) for row in obj.matrix_parent_inverse],sorted(c.name for c in obj.users_collection),
            obj.hide_render,obj.hide_viewport,
            [scalar_state(m) for m in obj.modifiers],
            [scalar_state(c) for c in obj.constraints],
            scalar_state(obj.data) if obj.type in {'LIGHT','CAMERA','FONT'} else None,
            sorted((str(k),str(v)) for k,v in obj.items())]
    for mat in bpy.data.materials:
        if not mat.get(engine.OWNER):
            result['materials'][mat.name] = material_state(mat)
    for col in bpy.data.collections:
        if not col.get(engine.OWNER):
            result['collections'][col.name] = [sorted(o.name for o in col.objects),
                sorted(c.name for c in col.children),col.hide_render,col.hide_viewport]
    for scene in bpy.data.scenes:
        if scene.get(engine.OWNER):
            continue
        world = scene.world
        result['scenes'][scene.name] = [sorted(o.name for o in scene.objects),
            sorted(c.name for c in scene.collection.children),scene.camera.name if scene.camera else None,
            world.name if world else None,scalar_state(scene.render),scalar_state(scene.view_settings),
            scalar_state(scene.unit_settings),scalar_state(world) if world else None,
            [(n.name,[str(i.default_value) for i in n.inputs if hasattr(i,'default_value')])
             for n in world.node_tree.nodes] if world and world.use_nodes else [],
            scene.frame_current,scene.frame_start,scene.frame_end]
    if raw:
        return result
    return {key:hashlib.sha256(json.dumps(value,sort_keys=True,default=str).encode()).hexdigest()
            for key,value in result.items()}


def inventory():
    return {name:sorted(b.name for b in getattr(bpy.data,name) if b.get(engine.OWNER))
            for name in ('scenes','collections','objects','meshes','curves','materials','cameras','lights','worlds','texts')}


def verify(path, before=None):
    bpy.ops.wm.open_mainfile(filepath=str(path))
    checks = {}
    if before:
        after = protected_state()
        checks.update({key+'_preserved':before[key]==after[key] for key in before})
    scene = bpy.data.scenes[engine.SCENE]
    bpy.context.window.scene = scene
    ctrl = bpy.data.objects['CTRL_ENGINE']
    root = bpy.data.collections[engine.COLLECTION]

    def check(name, value):
        checks[name] = bool(value)

    def update(**props):
        for key,value in props.items():
            ctrl[key] = value
        ctrl.update_tag()
        bpy.context.view_layer.update()

    def evaluated(name):
        return bpy.data.objects[name].evaluated_get(bpy.context.evaluated_depsgraph_get())

    def rot(name, axis=0):
        return evaluated(name).rotation_euler[axis]

    check('only_one_engine_scene',sum('CFM56_ENGINE' in s.name for s in bpy.data.scenes)==1)
    check('all_objects_isolated',all(sum(o.name in s.objects for s in bpy.data.scenes)==1 for o in root.all_objects))
    check('no_suffix_duplicates',all(not re.search(r'\.\d{3}$',o.name) for o in root.all_objects))
    check('groups_present',set(engine.GROUPS)==set(c.name for c in root.children))
    check('one_primary_controller',sum(o.name=='CTRL_ENGINE' for o in root.all_objects)==1)
    check('coaxial_sibling_spools',all(tuple(bpy.data.objects[n].location)==(0.,0.,0.) and
        bpy.data.objects[n].parent==ctrl for n in ('ROT_N1','ROT_N2')))
    check('fan_38_linked_blades',len([o for o in root.all_objects if o.name.startswith('FAN_N1_BLADE')])==38
          and len({o.data for o in root.all_objects if o.name.startswith('FAN_N1_BLADE')})==1)
    fan = bpy.data.objects['FAN_N1_BLADE_01']
    check('fan_radius',abs(max(v.co.y for v in fan.data.vertices)-.762)<1e-5)
    for section,number in [('LPC',3),('HPC',9),('HPT',1),('LPT',4)]:
        check(section+'_stage_count',sum(o.name.startswith(section+'_ROTOR') and o.name.endswith('_DISK') for o in root.all_objects)==number)
    check('all_meshes_finite',all(math.isfinite(c) for data in {o.data for o in root.all_objects if o.type=='MESH'} for v in data.vertices for c in v.co))
    static = [o for group in ('ENGINE_STATIC','ENGINE_COMBUSTOR','ENGINE_NACELLE') for o in bpy.data.collections[group].objects]
    check('static_parenting',all(o.parent==ctrl for o in static))
    for prefix,spool in [('FAN_N1','ROT_N1'),('LPC_ROTOR','ROT_N1'),('LPT_ROTOR','ROT_N1'),
                          ('HPC_ROTOR','ROT_N2'),('HPT_ROTOR','ROT_N2')]:
        check(prefix+'_parenting',all(o.parent.name==spool for o in root.all_objects if o.name.startswith(prefix)))
    update(N1_SPEED=0.,N2_SPEED=0.)
    scene.frame_set(25)
    check('engine_off',abs(rot('ROT_N1'))<1e-6 and abs(rot('ROT_N2'))<1e-6)
    static_before = {o.name:tuple(v for row in o.matrix_world for v in row) for o in static}
    update(N1_SPEED=60.)
    check('N1_one_turn_per_second',abs(rot('ROT_N1')+math.tau)<1e-5)
    check('N2_stays_stopped',abs(rot('ROT_N2'))<1e-6)
    update(N2_SPEED=120.)
    check('N2_independent_rpm',abs(rot('ROT_N2')+2*math.tau)<1e-5 and abs(rot('ROT_N1')+math.tau)<1e-5)
    check('static_transforms_unchanged',all(static_before[o.name]==tuple(v for row in o.matrix_world for v in row) for o in static))
    scene.frame_set(100001)
    check('long_range_rotation',abs(rot('ROT_N1')+100000/24*math.tau)<.02)
    scene.frame_set(1)
    update(CUTAWAY_MODE=False,SHOW_NACELLE=True,SHOW_INTERNALS=True)
    check('closed_shell_complete',all(not evaluated(o.name).hide_render for o in bpy.data.collections['ENGINE_NACELLE'].objects))
    update(CUTAWAY_MODE=True)
    check('cutaway_reversible',evaluated('NACELLE_FAN_COWL_Q2').hide_render and not evaluated('NACELLE_FAN_COWL_Q1').hide_render)
    check('cutaway_keeps_rotors',not evaluated('HPC_ROTOR_N2_STAGE05_BLADE_01').hide_render)
    update(SHOW_INTERNALS=False)
    check('internals_toggle',evaluated('HPC_ROTOR_N2_STAGE05_BLADE_01').hide_render)
    update(SHOW_INTERNALS=True,SHOW_AIRFLOW=True,BLEED_VALVE_OPEN=0.)
    check('valve_closed',abs(rot('BLEED_VALVE_PIVOT',2))<1e-6)
    check('closed_valve_stops_bleed_flow',evaluated('FLOW_BLEED_OUTPUT').hide_render)
    update(BLEED_VALVE_OPEN=1.,BLEED_SOURCE=0)
    check('valve_opens_physically',abs(rot('BLEED_VALVE_PIVOT',2)-math.pi/2)<1e-5)
    check('stage5_flow',not evaluated('FLOW_BLEED_STAGE5').hide_render and evaluated('FLOW_BLEED_STAGE9').hide_render)
    arrow_start = tuple(evaluated('FLOW_BYPASS_ARROW_1').matrix_world.translation)
    scene.frame_set(13)
    check('airflow_arrows_travel',math.dist(arrow_start,evaluated('FLOW_BYPASS_ARROW_1').matrix_world.translation)>.05)
    scene.frame_set(1)
    update(BLEED_SOURCE=1)
    check('stage9_flow',evaluated('FLOW_BLEED_STAGE5').hide_render and not evaluated('FLOW_BLEED_STAGE9').hide_render)
    update(SHOW_AIRFLOW=False)
    check('flow_off',all(evaluated(o.name).hide_render for o in bpy.data.collections['ENGINE_AIRFLOW'].objects))
    check('flow_does_not_hide_pipe',not evaluated('BLEED_DUCT_STAGE5').hide_render)
    for stage in (5,9):
        obj = bpy.data.objects[f'BLEED_STAGE{stage}_PORT']
        check(f'bleed_stage{stage}_alignment',abs(obj.location.x-(1.115+(stage-1)*.096))<1e-5)
    check('outlet_connection',tuple(round(v,3) for v in bpy.data.objects['BLEED_OUTLET_TO_AIRCRAFT'].location)==(2.7,-.64,-.72))
    namespace = {'__name__':'cfm56_validation'}
    exec(compile(bpy.data.texts[engine.SCRIPT].as_string(),engine.SCRIPT,'exec'),namespace)
    namespace['register']()
    # A linear 0 -> 120 RPM ramp over one second must turn exactly once.
    for frame,value in ((1,0.),(25,120.)):
        ctrl['N1_SPEED'] = value
        ctrl.keyframe_insert(data_path='["N1_SPEED"]',frame=frame)
        ctrl['N2_SPEED'] = value*2
        ctrl.keyframe_insert(data_path='["N2_SPEED"]',frame=frame)
        ctrl['BLEED_VALVE_OPEN'] = value/120
        ctrl.keyframe_insert(data_path='["BLEED_VALVE_OPEN"]',frame=frame)
    for fc in namespace['action_curves'](ctrl):
        for point in fc.keyframe_points:
            point.interpolation = 'LINEAR'
    scene.frame_end = 25
    namespace['bake_rpm'](scene,ctrl)
    scene.frame_set(13)
    check('ramp_integrates_midpoint',abs(rot('ROT_N1')+math.pi/2)<1e-4)
    check('N2_ramp_independent',abs(rot('ROT_N2')+math.pi)<1e-4)
    check('valve_keyframes_interpolate',abs(rot('BLEED_VALVE_PIVOT',2)-math.pi/4)<1e-4)
    scene.frame_set(25)
    check('ramp_integrates_one_turn',abs(rot('ROT_N1')+math.tau)<1e-4)
    # Save and reopen the animated candidate too, to test persistent integration.
    animated = ROOT/'reports'/'CFM56_animation_test.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(animated))
    bpy.ops.wm.open_mainfile(filepath=str(animated))
    scene = bpy.data.scenes[engine.SCENE]
    bpy.context.window.scene = scene
    ctrl = bpy.data.objects['CTRL_ENGINE']
    scene.frame_set(13)
    check('baked_animation_reopens',abs(rot('ROT_N1')+math.pi/2)<1e-4)
    ctrl.animation_data_clear()
    scene.frame_end = 240
    scene.frame_set(1)
    update(**engine.DEFAULTS)
    root = bpy.data.collections[engine.COLLECTION]
    curves = [f for obj in root.all_objects if obj.animation_data for f in obj.animation_data.drivers]
    check('native_drivers_valid',all(fc.driver.is_simple_expression and fc.driver.is_valid for fc in curves))
    invalid_drivers = [(fc.id_data.name,fc.data_path,fc.driver.type,fc.driver.expression,
                        fc.driver.is_valid,fc.driver.is_simple_expression) for fc in curves
                       if not fc.driver.is_valid or not fc.driver.is_simple_expression]
    if before:
        after = protected_state()
        checks.update({key+'_preserved_after_animation':before[key]==after[key] for key in before})
    report = {'passed':all(checks.values()),'blender':bpy.app.version_string,'checks':checks,
              'objects':len(root.all_objects),'unique_meshes':len({o.data for o in root.all_objects if o.type=='MESH'}),
              'native_drivers':len(curves),'file':str(path)}
    report['invalid_drivers'] = invalid_drivers
    (ROOT/'reports'/'cfm56_engine_verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    animated.unlink(missing_ok=True)
    print('CFM56_VERIFY',json.dumps(report),flush=True)
    if not report['passed']:
        raise RuntimeError('Engine checks failed: '+', '.join(k for k,v in checks.items() if not v))
    return report


if __name__=='__main__':
    verify(ROOT/'models'/'Boeing_737-300_Helios_Livery.blend')

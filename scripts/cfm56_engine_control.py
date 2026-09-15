"""Optional engine sidebar. Native controls and baked animation need no auto-exec."""
import math
import bpy

SCENE = '07 | CFM56_ENGINE'


def action_curves(obj):
    animation = obj.animation_data
    if not animation or not animation.action:
        return []
    action = animation.action
    if hasattr(action, 'fcurves'):
        return list(action.fcurves)
    return [fc for layer in action.layers for strip in layer.strips
            for bag in strip.channelbags if bag.slot_handle == animation.action_slot_handle
            for fc in bag.fcurves]


def bake_rpm(scene, ctrl, samples=4):
    """Integrate evaluated RPM curves; save correction as ordinary native F-curves.

    The live RPM drivers remain connected. Corrections are zero for constant RPM.
    Re-bake after editing RPM keyframes, frame range, or frame rate.
    """
    curves = action_curves(ctrl)
    start, end = scene.frame_start, scene.frame_end
    fps = scene.render.fps/scene.render.fps_base
    for spool in ('N1','N2'):
        speed_path = '["'+spool+'_SPEED"]'
        phase_path = '["'+spool+'_PHASE"]'
        source = next((fc for fc in curves if fc.data_path==speed_path),None)
        speed = source.evaluate if source else lambda frame: ctrl[spool+'_SPEED']
        for fc in curves:
            if fc.data_path==phase_path:
                fc.keyframe_points.clear()
        time = start
        rpm = speed(time)
        integral = rpm*(start-1)/fps*math.tau/60
        for index in range((end-start)*samples+1):
            frame = start+index/samples
            current = speed(frame)
            if index:
                integral += (rpm+current)/2/samples/fps*math.tau/60
            ctrl[spool+'_PHASE'] = integral-current*(frame-1)/fps*math.tau/60
            ctrl.keyframe_insert(data_path=phase_path,frame=frame,group='RPM integration (generated)')
            rpm = current
        for fc in action_curves(ctrl):
            if fc.data_path==phase_path:
                for point in fc.keyframe_points:
                    point.interpolation = 'LINEAR'
        ctrl[spool+'_PHASE'] = 0.
    ctrl['RPM bake range'] = f'{start}..{end}, {fps:g} fps, {samples} samples/frame; re-bake after RPM edits'
    ctrl.animation_data.action['cfm56_asset'] = True
    scene.frame_set(scene.frame_current)
    ctrl.update_tag()
    bpy.context.view_layer.update()


class CFM56_OT_inspect(bpy.types.Operator):
    bl_idname = 'cfm56.inspect'
    bl_label = 'Inspect engine'
    camera: bpy.props.StringProperty(default='CAM_ENGINE_TECH_SIDE')

    def execute(self, context):
        scene = bpy.data.scenes.get(SCENE)
        if not scene:
            return {'CANCELLED'}
        context.window.scene = scene
        scene.camera = bpy.data.objects[self.camera]
        ctrl = bpy.data.objects['CTRL_ENGINE']
        for obj in context.selected_objects:
            obj.select_set(False)
        ctrl.select_set(True)
        context.view_layer.objects.active = ctrl
        for area in context.screen.areas:
            if area.type=='VIEW_3D':
                space = area.spaces.active
                space.clip_start, space.clip_end = .005,100
                space.overlay.show_relationship_lines = False
                space.overlay.show_floor = False
                space.shading.color_type = 'MATERIAL'
                space.region_3d.view_perspective = 'CAMERA'
        return {'FINISHED'}


class CFM56_OT_bake(bpy.types.Operator):
    bl_idname = 'cfm56.bake_rpm'
    bl_label = 'Bake RPM animation'
    bl_description = 'Integrate speed keyframes; re-run after changing speeds, frame rate or shot range'
    bl_options = {'REGISTER','UNDO'}

    def execute(self, context):
        bake_rpm(bpy.data.scenes[SCENE],bpy.data.objects['CTRL_ENGINE'])
        self.report({'INFO'},'RPM curves integrated and saved as native animation')
        return {'FINISHED'}


class CFM56_PT_controls(bpy.types.Panel):
    bl_label = 'CFM56-3 engine'
    bl_idname = 'CFM56_PT_controls'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'CFM56'

    def draw(self, context):
        layout = self.layout
        layout.operator('cfm56.inspect')
        if context.scene.name != SCENE:
            return
        ctrl = bpy.data.objects.get('CTRL_ENGINE')
        if not ctrl:
            return
        row = layout.row()
        row.operator('cfm56.inspect',text='Three-quarter').camera = 'CAM_ENGINE_CINEMATIC_3Q'
        row.operator('cfm56.inspect',text='Fan').camera = 'CAM_ENGINE_FAN'
        for prop in ('N1_SPEED','N2_SPEED'):
            layout.prop(ctrl,'["'+prop+'"]',text=prop.replace('_',' ')+' (RPM)')
        layout.operator('cfm56.bake_rpm')
        layout.label(text='Re-bake after RPM keyframe edits.',icon='INFO')
        for prop in ('BLEED_VALVE_OPEN','BLEED_SOURCE','CUTAWAY_MODE','SHOW_NACELLE',
                     'SHOW_INTERNALS','SHOW_AIRFLOW','SHOW_LABELS'):
            layout.prop(ctrl,'["'+prop+'"]',text=prop.replace('_',' ').title())
        layout.label(text='Bleed: 0 = stage 5; 1 = stage 9')


CLASSES = (CFM56_OT_inspect,CFM56_OT_bake,CFM56_PT_controls)


def register():
    for cls in reversed(CLASSES):
        if issubclass(cls,bpy.types.Operator):
            prefix, name = cls.bl_idname.split('.')
            old = bpy.types.Operator.bl_rna_get_subclass_py(prefix.upper()+'_OT_'+name)
        else:
            old = getattr(bpy.types,cls.__name__,None)
        if old:
            bpy.utils.unregister_class(old)
    for cls in CLASSES:
        bpy.utils.register_class(cls)


register()

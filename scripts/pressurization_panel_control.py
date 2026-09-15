"""Embedded, dependency-free Blender sidebar. Run Script once to enable the UI.

Native drivers work even when this optional UI script has not been registered.
No handlers or duplicate animation state: every action edits the master object.
"""
import bpy
from bpy.props import IntProperty, StringProperty

SCENE = '06 | Pressurization panel'
CONTROLLER = 'CTRL_PRESSURIZATION_PANEL'


def controller():
    return bpy.data.objects.get(CONTROLLER)


def set_value(prop, value):
    obj=controller()
    obj[prop]=value
    obj.update_tag()
    bpy.context.view_layer.update()
    for screen in bpy.data.screens:
        for area in screen.areas:
            area.tag_redraw()


class PRESS_OT_warning(bpy.types.Operator):
    bl_idname='pressurization.warning'
    bl_label='Toggle warning'
    bl_options={'REGISTER','UNDO'}
    warning: StringProperty()

    def execute(self, context):
        if controller() is None or self.warning not in ('auto_fail','off_sched_descent'):
            return {'CANCELLED'}
        set_value(self.warning, not controller()[self.warning])
        return {'FINISHED'}


class PRESS_OT_reset(bpy.types.Operator):
    bl_idname='pressurization.reset_warnings'
    bl_label='Reset warnings'
    bl_options={'REGISTER','UNDO'}

    def execute(self, context):
        if controller() is None:
            return {'CANCELLED'}
        set_value('auto_fail',False)
        set_value('off_sched_descent',False)
        return {'FINISHED'}


class PRESS_OT_mode(bpy.types.Operator):
    bl_idname='pressurization.mode'
    bl_label='Set mode detent'
    bl_options={'REGISTER','UNDO'}
    mode: IntProperty(min=0,max=2)

    def execute(self, context):
        if controller() is None:
            return {'CANCELLED'}
        set_value('mode',self.mode)
        return {'FINISHED'}


class PRESS_OT_inspect(bpy.types.Operator):
    bl_idname='pressurization.inspect'
    bl_label='Inspect panel'

    def execute(self, context):
        scene=bpy.data.scenes.get(SCENE)
        if scene is None:
            return {'CANCELLED'}
        context.window.scene=scene
        for area in context.screen.areas:
            if area.type=='VIEW_3D':
                space=area.spaces.active
                space.clip_start=.001
                space.clip_end=100
                space.region_3d.view_perspective='CAMERA'
                space.region_3d.view_camera_zoom=0
                space.shading.type='MATERIAL'
                space.shading.use_scene_world=True
                space.shading.use_scene_lights=True
                space.overlay.show_relationship_lines=False
                space.overlay.show_floor=False
        bpy.ops.object.select_all(action='DESELECT')
        obj=controller()
        obj.select_set(True)
        context.view_layer.objects.active=obj
        return {'FINISHED'}


class PRESS_OT_click_warnings(bpy.types.Operator):
    bl_idname='pressurization.click_warnings'
    bl_label='Enable viewport warning clicks (Esc stops)'
    bl_description='In this view, left-click a warning window to toggle it. Esc or right-click stops'
    _running=False

    def invoke(self, context, event):
        if context.area.type!='VIEW_3D' or context.scene.name!=SCENE or type(self)._running:
            return {'CANCELLED'}
        self._area=context.area
        type(self)._running=True
        context.window_manager.modal_handler_add(self)
        self.report({'INFO'},'Warning clicks enabled. Esc or right-click stops.')
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type in {'ESC','RIGHTMOUSE'} or context.scene.name!=SCENE or controller() is None:
            type(self)._running=False
            return {'CANCELLED'}
        if event.type!='LEFTMOUSE' or event.value!='PRESS':
            return {'PASS_THROUGH'}
        region=next((r for r in self._area.regions if r.type=='WINDOW'),None)
        if region is None:
            type(self)._running=False
            return {'CANCELLED'}
        xy=(event.mouse_x-region.x,event.mouse_y-region.y)
        if not (0<=xy[0]<region.width and 0<=xy[1]<region.height):
            return {'PASS_THROUGH'}
        from bpy_extras import view3d_utils
        rv3d=self._area.spaces.active.region_3d
        origin=view3d_utils.region_2d_to_origin_3d(region,rv3d,xy)
        direction=view3d_utils.region_2d_to_vector_3d(region,rv3d,xy)
        hit,loc,normal,index,obj,matrix=context.scene.ray_cast(context.evaluated_depsgraph_get(),origin,direction)
        prop=obj.get('warning_property') if hit else None
        if prop in ('auto_fail','off_sched_descent'):
            bpy.ops.pressurization.warning(warning=prop)
            return {'RUNNING_MODAL'}
        return {'PASS_THROUGH'}

    def cancel(self, context):
        type(self)._running=False


class PRESS_PT_panel(bpy.types.Panel):
    bl_label='PRESSURIZATION PANEL'
    bl_idname='PRESS_PT_panel'
    bl_space_type='VIEW_3D'
    bl_region_type='UI'
    bl_category='Pressurization'

    @classmethod
    def poll(cls, context):
        return controller() is not None

    def draw(self, context):
        layout=self.layout
        obj=controller()
        layout.operator('pressurization.inspect',icon='VIEW_CAMERA')
        layout.prop(obj,'["flight_altitude"]',text='Flight altitude (ft)')
        layout.prop(obj,'["landing_altitude"]',text='Landing altitude (ft)')
        row=layout.row(align=True)
        for i,name in enumerate(('AUTO','ALTN','MAN')):
            row.operator('pressurization.mode',text=name,depress=obj['mode']==i).mode=i
        layout.prop(obj,'["valve_position"]',text='Valve position',slider=True)
        layout.label(text='Warning lights')
        for prop,title in [('auto_fail','AUTO FAIL'),('off_sched_descent','OFF SCHED DESCENT')]:
            state=bool(obj[prop])
            layout.operator('pressurization.warning',text=title+(' : ON' if state else ' : OFF'),
                            depress=state).warning=prop
        layout.operator('pressurization.reset_warnings')
        if context.scene.name==SCENE:
            layout.operator('pressurization.click_warnings',icon='RESTRICT_SELECT_OFF')
        layout.label(text='Animate master custom properties.',icon='KEY_HLT')


CLASSES=(PRESS_OT_warning,PRESS_OT_reset,PRESS_OT_mode,PRESS_OT_inspect,
         PRESS_OT_click_warnings,PRESS_PT_panel)


def registered_class(cls):
    if issubclass(cls,bpy.types.Operator):
        prefix,name=cls.bl_idname.split('.')
        return bpy.types.Operator.bl_rna_get_subclass_py(prefix.upper()+'_OT_'+name)
    return getattr(bpy.types,cls.__name__,None)


def register():
    # Re-running the embedded script is safe; do not replace an active modal tool.
    for cls in CLASSES:
        old=registered_class(cls)
        if old:
            if getattr(old,'_running',False):
                continue
            bpy.utils.unregister_class(old)
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        old=registered_class(cls)
        if old:
            bpy.utils.unregister_class(old)


register()

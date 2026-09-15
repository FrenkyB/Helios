"""Optional ECS overview sidebar; native scene properties need no UI script.

The two installed engines share an overview-owned presentation template.
Controls here never target the independent standalone engine controller.
"""
import bpy

SCENE = '08 | ECS_OVERVIEW'
CONTROLLER = 'CTRL_ECS_OVERVIEW'
ENGINE_CONTROLLER = 'ECS ENG | CTRL_ENGINE'
CAMERAS = ('CAM_OVERVIEW_WIDE', 'CAM_OVERVIEW_3Q', 'CAM_OVERVIEW_SIDE')


class ECS_OVERVIEW_OT_inspect(bpy.types.Operator):
    bl_idname = 'ecs_overview.inspect'
    bl_label = 'Inspect overview'
    bl_description = 'Open the ECS overview and select its presentation controller'
    camera: bpy.props.StringProperty(default='CAM_OVERVIEW_WIDE')

    def execute(self, context):
        scene = bpy.data.scenes.get(SCENE)
        ctrl = bpy.data.objects.get(CONTROLLER)
        camera = bpy.data.objects.get(self.camera)
        if (scene is None or ctrl is None or context.window is None
                or self.camera not in CAMERAS or camera is None
                or camera.type != 'CAMERA' or camera.name not in scene.objects):
            self.report({'WARNING'}, 'Build the ECS overview before inspecting it')
            return {'CANCELLED'}
        context.window.scene = scene
        scene.camera = camera
        for obj in context.selected_objects:
            obj.select_set(False)
        if ctrl.name in context.view_layer.objects:
            ctrl.select_set(True)
            context.view_layer.objects.active = ctrl
        if context.screen:
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    space = area.spaces.active
                    space.clip_start, space.clip_end = .02, 500
                    space.overlay.show_relationship_lines = False
                    space.overlay.show_floor = False
                    space.overlay.show_axis_x = False
                    space.overlay.show_axis_y = False
                    space.overlay.show_axis_z = False
                    if hasattr(space.overlay, 'show_ortho_grid'):
                        space.overlay.show_ortho_grid = False
                    space.shading.color_type = 'MATERIAL'
                    space.shading.type = 'MATERIAL'
                    space.shading.use_scene_world = True
                    space.shading.use_scene_lights = True
                    space.region_3d.view_perspective = 'CAMERA'
                    space.region_3d.view_camera_zoom = 0
        return {'FINISHED'}


class ECS_OVERVIEW_PT_controls(bpy.types.Panel):
    bl_label = 'ECS overview | Phase 1'
    bl_idname = 'ECS_OVERVIEW_PT_controls'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'ECS Overview'

    @classmethod
    def poll(cls, context):
        return bpy.data.scenes.get(SCENE) is not None

    def draw(self, context):
        layout = self.layout
        layout.operator('ecs_overview.inspect', icon='VIEW_CAMERA')
        if context.scene.name != SCENE:
            return
        row = layout.row(align=True)
        for name, camera in zip(('Wide', '3Q', 'Side'), CAMERAS):
            row.operator('ecs_overview.inspect', text=name).camera = camera
        ctrl = bpy.data.objects.get(CONTROLLER)
        if ctrl:
            layout.separator()
            layout.label(text='Aircraft presentation')
            for prop, title in (('SHOW_SHELL', 'Transparent shell'),
                                ('SHOW_WIREFRAME', 'Wireframe')):
                if prop in ctrl:
                    layout.prop(ctrl, '["'+prop+'"]', text=title)
            wire_settings = layout.column(align=True)
            wire_settings.enabled = bool(ctrl.get('SHOW_WIREFRAME',False))
            if 'WIREFRAME_THICKNESS' in ctrl:
                wire_settings.prop(ctrl,'["WIREFRAME_THICKNESS"]',text='Wireframe thickness',slider=True)
            if 'WIREFRAME_COLOR' in ctrl:
                wire_settings.prop(ctrl,'["WIREFRAME_COLOR"]',text='Wireframe color')
        engine = bpy.data.objects.get(ENGINE_CONTROLLER)
        if engine:
            layout.separator()
            layout.label(text='Both installed engines')
            for prop, title in (('CUTAWAY_MODE', 'Engine cutaway'),
                                ('SHOW_NACELLE', 'Show nacelle'),
                                ('SHOW_INTERNALS', 'Show internals'),
                                ('N1_SPEED', 'N1 speed (RPM)'),
                                ('N2_SPEED', 'N2 speed (RPM)')):
                if prop in engine:
                    layout.prop(engine, '["'+prop+'"]', text=title)
            layout.label(text='Shared state; constant RPM playback.', icon='INFO')


CLASSES = (ECS_OVERVIEW_OT_inspect, ECS_OVERVIEW_PT_controls)


def registered_class(cls):
    if issubclass(cls, bpy.types.Operator):
        prefix, name = cls.bl_idname.split('.')
        return bpy.types.Operator.bl_rna_get_subclass_py(prefix.upper()+'_OT_'+name)
    return getattr(bpy.types, cls.__name__, None)


def unregister():
    for cls in reversed(CLASSES):
        old = registered_class(cls)
        if old:
            bpy.utils.unregister_class(old)


def register():
    # Embedded scripts may be run repeatedly in the same Blender session.
    unregister()
    for cls in CLASSES:
        bpy.utils.register_class(cls)


register()

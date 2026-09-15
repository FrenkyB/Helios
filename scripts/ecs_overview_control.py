"""Optional ECS overview sidebar; native scene properties need no UI script.

Installed engines share RPM controls and have independent presentation states.
Controls here never target the independent standalone engine controller.
"""
import bpy

SCENE = '08 | ECS_OVERVIEW'
CONTROLLER = 'CTRL_ECS_OVERVIEW'
ENGINE_CONTROLLER = 'ECS ENG | CTRL_ENGINE'
ENGINE_PRESENTATION_CONTROLLER = 'CTRL_ECS_ENGINE_PRESENTATION'
PHASE2_CONTROLLER = 'CTRL_ECS_PHASE2'
CAMERAS = ('CAM_OVERVIEW_WIDE', 'CAM_OVERVIEW_3Q', 'CAM_OVERVIEW_SIDE')
PHASE2_CAMERAS = ('CAM_ECS_PHASE2_LEFT', 'CAM_ECS_PHASE2_RIGHT', 'CAM_ECS_PHASE2_PACKS')
ENGINE_MODES = ((0, 'Closed'), (1, 'Cutaway'), (2, 'Fully open'))
SHELL_SECTIONS = (('INNER', 'Inner side'), ('OUTER', 'Outer side'),
                  ('TOP', 'Top'), ('BOTTOM', 'Bottom'),
                  ('FRONT', 'Intake / front'), ('AFT', 'Aft / core'))


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
                or self.camera not in CAMERAS+PHASE2_CAMERAS or camera is None
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


class ECS_OVERVIEW_OT_engine_presentation(bpy.types.Operator):
    bl_idname = 'ecs_overview.engine_presentation'
    bl_label = 'Set installed engine presentation'
    bl_description = ('Set the shell opening for the selected installed engine; '
                      'keep its individual shell switches')
    bl_options = {'REGISTER', 'UNDO'}

    side: bpy.props.EnumProperty(
        name='Engine',
        items=(('LEFT', 'Left engine', 'Change the left installed engine'),
               ('RIGHT', 'Right engine', 'Change the right installed engine'),
               ('BOTH', 'Both engines', 'Change both installed engines')),
        default='BOTH')
    mode: bpy.props.IntProperty(name='Mode', default=0, min=0, max=2)

    @classmethod
    def poll(cls, context):
        return (context.scene is not None and context.scene.name == SCENE
                and bpy.data.objects.get(ENGINE_PRESENTATION_CONTROLLER) is not None)

    def execute(self, context):
        ctrl = bpy.data.objects.get(ENGINE_PRESENTATION_CONTROLLER)
        sides = ('LEFT', 'RIGHT') if self.side == 'BOTH' else (self.side,)
        if (ctrl is None or self.mode not in (0, 1, 2)
                or any(side not in ('LEFT', 'RIGHT')
                       for side in sides)
                or any(side+'_ENGINE_MODE' not in ctrl for side in ('LEFT', 'RIGHT'))):
            self.report({'WARNING'}, 'Build installed engine presentation first')
            return {'CANCELLED'}
        engine = bpy.data.objects.get(ENGINE_CONTROLLER)
        if engine is not None and engine.get('CUTAWAY_MODE', False):
            # Keep the other engine's effective appearance when leaving the
            # legacy shared cutaway switch for independent mode controls.
            for side in ('LEFT', 'RIGHT'):
                ctrl[side+'_ENGINE_MODE'] = max(1, int(ctrl[side+'_ENGINE_MODE']))
            engine['CUTAWAY_MODE'] = False
            engine.update_tag()
        for side in sides:
            ctrl[side+'_ENGINE_MODE'] = self.mode
        ctrl.update_tag()
        context.view_layer.update()
        return {'FINISHED'}


def draw_engine_presentation(layout, ctrl, engine):
    """Show native property state without requiring UI-side update handlers."""
    layout.separator()
    layout.label(text='Installed engine presentation')
    both = layout.box()
    both.label(text='Both engines')
    row = both.row(align=True)
    for mode, title in ENGINE_MODES:
        active = all(ctrl.get(side+'_ENGINE_MODE') == mode
                     for side in ('LEFT', 'RIGHT'))
        operator = row.operator('ecs_overview.engine_presentation',
                                text=title, depress=active)
        operator.side, operator.mode = 'BOTH', mode
    global_cutaway = bool(engine and engine.get('CUTAWAY_MODE', False))
    if global_cutaway:
        layout.label(text='Global cutaway is active.', icon='INFO')
        layout.label(text='A mode button resumes independent control.')
    layout.label(text='Shell switches hide additional sections.')
    layout.label(text='Closed keeps your shell selections.')
    for side, title in (('LEFT', 'Left engine'), ('RIGHT', 'Right engine')):
        prop = side+'_ENGINE_MODE'
        if prop not in ctrl:
            continue
        box = layout.box()
        box.label(text=title)
        row = box.row(align=True)
        mode = int(ctrl[prop])
        for value, label in ENGINE_MODES:
            operator = row.operator('ecs_overview.engine_presentation',
                                    text=label, depress=mode == value)
            operator.side, operator.mode = side, value
        box.label(text='Shell refinements')
        fine = box.column(align=True)
        show_nacelle = bool(engine is None or engine.get('SHOW_NACELLE', True))
        show_internals = bool(engine is None or engine.get('SHOW_INTERNALS', True))
        fine.enabled = mode != 2
        effective_mode = 1 if global_cutaway and mode == 0 else mode
        for index in range(0, len(SHELL_SECTIONS), 2):
            row = fine.row(align=True)
            for section, label in SHELL_SECTIONS[index:index+2]:
                prop = side+'_SHOW_'+section
                if prop in ctrl:
                    cell = row.column(align=True)
                    available = show_nacelle if section in ('FRONT', 'AFT') else show_nacelle or show_internals
                    cell.enabled = available and not (effective_mode == 1 and section in ('OUTER', 'TOP'))
                    cell.prop(ctrl, '["'+prop+'"]', text=label)
        if mode == 2:
            box.label(text='Every shell section is hidden.', icon='INFO')


class ECS_OVERVIEW_PT_controls(bpy.types.Panel):
    bl_label = 'ECS overview'
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
            layout.label(text='Both engines | shared controls')
            for prop, title in (('CUTAWAY_MODE', 'Global cutaway'),
                                ('SHOW_NACELLE', 'Show nacelle'),
                                ('SHOW_INTERNALS', 'Show internals'),
                                ('N1_SPEED', 'N1 speed (RPM)'),
                                ('N2_SPEED', 'N2 speed (RPM)')):
                if prop in engine:
                    layout.prop(engine, '["'+prop+'"]', text=title)
            layout.label(text='Shared RPM; constant-speed playback.', icon='INFO')
        presentation = bpy.data.objects.get(ENGINE_PRESENTATION_CONTROLLER)
        if presentation:
            draw_engine_presentation(layout, presentation, engine)
        phase2 = bpy.data.objects.get(PHASE2_CONTROLLER)
        if phase2:
            layout.separator()
            layout.label(text='Pneumatic system | Phase 2')
            row = layout.row(align=True)
            for side, title in (('LEFT', 'Left branch'), ('RIGHT', 'Right branch')):
                if 'SHOW_'+side in phase2:
                    row.prop(phase2, '["SHOW_'+side+'"]', text=title)
            for prop, title in (('SHOW_DUCTS', 'Show ducts'),
                                ('SHOW_PRECOOLERS', 'Show precoolers'),
                                ('SHOW_PACKS', 'Show packs'),
                                ('SHOW_AIRFLOW', 'Show airflow')):
                if prop in phase2:
                    layout.prop(phase2, '["'+prop+'"]', text=title)
            if 'ECS_FLOW_SPEED' in phase2:
                row = layout.row()
                row.enabled = bool(phase2.get('SHOW_AIRFLOW', False))
                row.prop(phase2, '["ECS_FLOW_SPEED"]', text='Flow speed (m/s)')
            row = layout.row(align=True)
            for title, camera in zip(('Left', 'Right', 'Packs'), PHASE2_CAMERAS):
                if camera in context.scene.objects:
                    row.operator('ecs_overview.inspect', text=title).camera = camera


CLASSES = (ECS_OVERVIEW_OT_inspect, ECS_OVERVIEW_OT_engine_presentation,
           ECS_OVERVIEW_PT_controls)


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

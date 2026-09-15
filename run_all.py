"""Open this file in Blender's Text Editor and click Run Script.

Builds, verifies, saves and opens Helios, Larnaca and a separate functional panel.
No external Python installation, command-line arguments or preview renders needed.
"""
from pathlib import Path
import datetime
import shutil
import subprocess
import traceback

import bpy


def project_root():
    # Blender may set __file__ to the text block name rather than its full path.
    text = getattr(bpy.context.space_data, 'text', None)
    path = bpy.path.abspath(text.filepath) if text and text.filepath else __file__
    return Path(path).resolve().parent


ROOT = project_root()
OUTPUT = ROOT / 'models' / 'Boeing_737-300_Helios_Livery.blend'
STATE_KEY = '_helios_run_all_build'
STAGES = (
    ('Letalo in kabina', 'build_aircraft.py', 'run_all.log', ['--skip-render']),
    ('Preverjanje letala', 'verify_saved.py', 'verification.log', []),
    ('Pilotska okna', 'correct_cockpit_windows.py', 'cockpit_correction.log', ['--skip-render']),
    ('Preverjanje oken', 'verify_cockpit_correction.py', 'cockpit_preservation.log', []),
    ('Helios poslikava', 'apply_helios_livery.py', 'helios_livery.log', ['--skip-render']),
    ('Cockpit 737 Classic', 'update_classic_cockpit.py', 'classic_cockpit.log', ['--skip-render']),
    ('Preverjanje kabine', 'verify_passenger_cabin.py', 'passenger_verification.log', []),
    ('Letalisce Larnaca', 'build_larnaca.py', 'larnaca.log', ['--skip-render']),
    ('Panel tlaka kabine', 'build_pressurization_panel.py', 'pressurization_panel.log', ['--skip-render']),
)


def message(title, lines, icon='INFO'):
    print(title + ': ' + ' | '.join(lines), flush=True)

    def draw(self, context):
        for line in lines:
            self.layout.label(text=line)

    windows = bpy.context.window_manager.windows
    if windows:
        with bpy.context.temp_override(window=windows[0]):
            bpy.context.window_manager.popup_menu(draw, title=title, icon=icon)


def main():
    if bpy.app.background:
        raise RuntimeError('Open run_all.py in Blender Text Editor and click Run Script.')
    namespace = bpy.app.driver_namespace
    if STATE_KEY in namespace:
        message('Helios', ['Izdelava ze poteka. Napredek je v spodnji statusni vrstici.'])
        return
    if not all((ROOT / 'scripts' / stage[1]).is_file() for stage in STAGES):
        message('Mapa projekta ni najdena', [
            'S Text > Open odpri run_all.py iz mape ChatGpt/GitHub.', str(ROOT)], 'ERROR')
        return

    backup = ROOT / 'reports' / 'backups' / datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    try:
        backup.mkdir(parents=True)
        (ROOT / 'logs').mkdir(exist_ok=True)
        for name in ('HEL-1_Boeing_737-300.blend', 'Boeing_737-300.blend', OUTPUT.name):
            path = ROOT / 'models' / name
            if path.exists():
                shutil.copy2(path, backup / name)
    except OSError as exc:
        message('Izdelava se ni zacela', [str(exc)], 'ERROR')
        return

    state = {'index': 0, 'process': None}
    namespace[STATE_KEY] = state
    error_log = ROOT / 'logs' / 'blender_launcher.log'
    error_log.write_text('Helios build started from Blender Text Editor.\n', encoding='utf-8')

    def status(text=None):
        for window in bpy.context.window_manager.windows:
            with bpy.context.temp_override(window=window):
                window.workspace.status_text_set(text)

    def show_result():
        # Loading a .blend invalidates the current UI context until the next tick.
        # This callback must run after open_mainfile has returned to Blender.
        window = bpy.context.window_manager.windows[0]
        with bpy.context.temp_override(window=window):
            configure_result(window)
        return None

    def configure_result(window):
        scene = bpy.data.scenes['05 | Larnaca - Helios Flight 522']
        window.scene = scene
        camera = bpy.data.objects.get('LCA | Camera airport_overview')
        if camera:
            scene.camera = camera
        for screen in bpy.data.screens:
            for area in screen.areas:
                if area.type == 'VIEW_3D':
                    space = area.spaces.active
                    space.overlay.show_relationship_lines = False
                    space.overlay.show_floor = False
                    space.overlay.show_axis_x = False
                    space.overlay.show_axis_y = False
                    space.overlay.show_axis_z = False
                    if hasattr(space.overlay, 'show_ortho_grid'):
                        space.overlay.show_ortho_grid = False
                    space.clip_start = 1.0
                    space.clip_end = 20000
                    space.shading.color_type = 'MATERIAL'
                    space.shading.type = 'MATERIAL'
                    space.shading.use_scene_world = True
                    space.shading.use_scene_lights = True
                    space.region_3d.view_perspective = 'CAMERA'
                elif area.type == 'TEXT_EDITOR':
                    text = bpy.data.texts.get('run_all.py') or bpy.data.texts.load(str(ROOT / 'run_all.py'))
                    area.spaces.active.text = text
        # Initialize our embedded optional panel UI for this freshly built project.
        panel_script = bpy.data.texts.get('PRESSURIZATION_PANEL_CONTROL.py')
        if panel_script:
            exec(compile(panel_script.as_string(), panel_script.name, 'exec'),
                 {'__name__': 'helios_pressurization_ui'})
        # Save the visible airport scene and keep the script available for the next run.
        bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT))
        message('Helios je pripravljen', ['Letalo, Larnaca in panel tlaka so izdelani, preverjeni in shranjeni.',
                                        'Panel: scena 06 ali N > Pressurization > Inspect panel.', str(OUTPUT)])

    def finish():
        # Preserve even edits made while the build was running before opening its result.
        bpy.ops.wm.save_as_mainfile(filepath=str(backup / 'Open_session_before_result.blend'), copy=True)
        bpy.app.timers.register(show_result, first_interval=0.5, persistent=True)
        bpy.ops.wm.open_mainfile(filepath=str(OUTPUT), load_ui=False)

    def poll():
        try:
            process = state['process']
            if process is not None:
                code = process.poll()
                if code is None:
                    return 0.5
                if code:
                    log = ROOT / 'logs' / STAGES[state['index']][2]
                    raise RuntimeError(f'{STAGES[state["index"]][1]}: exit code {code}. Log: {log}')
                state['index'] += 1
                state['process'] = None
            if state['index'] == len(STAGES):
                status()
                namespace.pop(STATE_KEY, None)
                finish()
                return None
            title, script, log_name, arguments = STAGES[state['index']]
            status(f'Helios {state["index"] + 1}/{len(STAGES)}: {title} ...')
            cmd = [bpy.app.binary_path, '--background', '--factory-startup',
                   '--python-exit-code', '1', '--python', str(ROOT / 'scripts' / script)]
            if arguments:
                cmd += ['--', *arguments]
            with (ROOT / 'logs' / log_name).open('w', encoding='utf-8') as log:
                state['process'] = subprocess.Popen(
                    cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            return 0.5
        except Exception as exc:
            namespace.pop(STATE_KEY, None)
            status()
            error_log.write_text(traceback.format_exc(), encoding='utf-8')
            message('Napaka pri izdelavi Helios', [str(exc), str(error_log)], 'ERROR')
            return None

    bpy.app.timers.register(poll, first_interval=0.2, persistent=True)
    status('Helios: pripravljam izdelavo letala in letalisca ...')


if __name__ == '__main__':
    main()

"""Add Larnaca to the existing Helios .blend without changing aircraft geometry."""
import argparse
import json
from pathlib import Path
import sys

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import larnaca
from verify_larnaca import protected_state, verify


def render(draft, views):
    scene = bpy.data.scenes[larnaca.SCENE]
    directory = ROOT/'renders'/'larnaca'
    directory.mkdir(parents=True, exist_ok=True)
    for name in views.split(','):
        cam = bpy.data.objects.get(larnaca.PREFIX+'Camera '+name)
        if cam is None:
            raise ValueError('Unknown airport camera: '+name)
        scene.camera = cam
        scene.render.resolution_percentage = 70 if draft else 100
        scene.cycles.samples = 16 if draft else 40
        scene.render.filepath = str(directory/(name+'.png'))
        print('RENDER Larnaca', name, flush=True)
        bpy.ops.render.render(write_still=True, scene=scene.name)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', default=str(ROOT/'models'/'Boeing_737-300_Helios_Livery.blend'))
    parser.add_argument('--skip-render', action='store_true')
    parser.add_argument('--draft', action='store_true')
    parser.add_argument('--render-only', action='store_true')
    parser.add_argument('--views', default='airport_overview,layout,terminal_aerial,helios_gate,forecourt,tower,runway_04')
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    bpy.ops.wm.open_mainfile(filepath=str(Path(args.source).resolve()))
    if args.render_only:
        render(args.draft, args.views)
        return
    if any(bpy.data.objects.get(n) is None or bpy.data.objects[n].data.attributes.get('Helios_rest_position') is None
           for n in ['Fuselage | continuous quad loft','Vertical fin with dorsal fillet','Rudder']):
        raise RuntimeError('Source needs the instance-safe Helios livery. Run python run_all.py --skip-render first, '
                           'or apply the current --helios-livery stage to the saved aircraft source.')
    before = protected_state()
    cfg = json.loads((ROOT/'config'/'larnaca.json').read_text(encoding='utf-8'))
    larnaca.build(cfg)
    if protected_state() != before:
        raise RuntimeError('Airport stage changed an existing aircraft object, material or scene')
    output = ROOT/'models'/'Boeing_737-300_Helios_Livery.blend'
    pending = ROOT/'reports'/'Larnaca_pending.blend'
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(pending))
    verify(pending, before=before)
    # Save from the verified reopened project, retaining valid packed resources.
    bpy.context.window.scene = bpy.data.scenes[larnaca.SCENE]
    bpy.ops.wm.save_as_mainfile(filepath=str(output))
    report = json.loads((ROOT/'reports'/'larnaca_verification.json').read_text())
    report['file'] = str(output)
    (ROOT/'reports'/'larnaca_verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    pending.unlink()
    if not args.skip_render:
        render(args.draft, args.views)
    print('COMPLETE Larnaca', output, flush=True)


if __name__ == '__main__':
    main()

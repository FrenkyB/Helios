"""Render saved passenger views without changing the delivered file."""
import argparse
from pathlib import Path
import sys
import bpy

ROOT = Path(__file__).resolve().parents[1]


def render(draft=False):
    directory = ROOT / 'renders' / 'passenger'
    directory.mkdir(parents=True, exist_ok=True)
    cabin = next(s for s in bpy.data.scenes if s.name.startswith('03 | Passenger cabin'))
    layout = bpy.data.scenes['04 | Passenger cabin layout']
    views = [('aisle_forward', cabin, cabin.camera),
             ('aisle_aft', cabin, bpy.data.objects['Passenger camera | forward looking aft']),
             ('seat_detail', cabin, bpy.data.objects['Passenger camera | seat detail']),
             ('layout', layout, layout.camera)]
    for label, scene, camera in views:
        scene.camera = camera
        scene.render.resolution_percentage = 65 if draft else 100
        scene.cycles.samples = 20 if draft else 64
        scene.render.filepath = str(directory / f'{label}.png')
        print('RENDER', label, flush=True)
        bpy.ops.render.render(write_still=True, scene=scene.name)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', default=str(ROOT / 'models' / 'Boeing_737-300_Helios_Livery.blend'))
    parser.add_argument('--draft', action='store_true')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    bpy.ops.wm.open_mainfile(filepath=str(Path(args.source).resolve()))
    render(args.draft)

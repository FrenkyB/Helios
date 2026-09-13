"""Build the Helios 737-300, passenger cabin and Classic flight deck with one command."""
from pathlib import Path
import argparse
import datetime
import os
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent


def find_blender(explicit):
    candidates = [explicit, os.environ.get('BLENDER_EXE'), shutil.which('blender')]
    base = Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Blender Foundation'
    if base.exists():
        candidates.extend(str(p) for p in sorted(base.glob('Blender */blender.exe'), reverse=True)
                          if 'out_of_service' not in str(p))
    candidates.append('/Applications/Blender.app/Contents/MacOS/Blender')
    for path in candidates:
        if path and Path(path).is_file():
            return str(Path(path).resolve())
    raise SystemExit('Blender not found. Use --blender "C:/path/to/blender.exe"')


def run(blender, script, log_name, arguments=()):
    cmd = [blender, '--background', '--factory-startup', '--python-exit-code', '1',
           '--python', str(ROOT / 'scripts' / script)]
    if arguments:
        cmd += ['--', *arguments]
    print('BUILD', script, flush=True)
    with (ROOT / 'logs' / log_name).open('w', encoding='utf-8') as log:
        with subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              encoding='utf-8', errors='replace') as process:
            for line in process.stdout:
                log.write(line)
                log.flush()
                if any(token in line for token in ['VALIDATION', 'VERIFIED', 'RENDER', 'COMPLETE',
                                                   'Error', 'Traceback', 'Saved', 'Render device']):
                    print(line.rstrip(), flush=True)
            code = process.wait()
    if code:
        raise SystemExit(f'{script} failed ({code}). Read logs/{log_name}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--blender', help='Path to Blender executable (validated with 5.2)')
    parser.add_argument('--skip-render', action='store_true', help='Build and verify without previews')
    parser.add_argument('--draft', action='store_true', help='Faster previews')
    parser.add_argument('--views', default='hero,side,front,top,rear,engine,nose', help='Exterior views for --base-only')
    parser.add_argument('--exterior-only', action='store_true', help='Omit interior scenes on regeneration')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--base-only', action='store_true', help='Build only the unpainted base model')
    mode.add_argument('--correct-cockpit', action='store_true', help='Run the existing glazing correction only')
    mode.add_argument('--helios-livery', action='store_true', help='Run the existing livery stage only')
    mode.add_argument('--passenger-cabin', action='store_true', help='Upgrade only the cabin in an existing Helios model')
    mode.add_argument('--cockpit-interior', action='store_true', help='Build only the fitted 737 Classic cockpit interior')
    parser.add_argument('--source', help='Input .blend for an individual correction, livery, cabin or cockpit stage')
    args = parser.parse_args()
    if args.source and not (args.correct_cockpit or args.helios_livery or args.passenger_cabin or args.cockpit_interior):
        parser.error('--source requires an individual correction, livery, cabin or cockpit stage')
    if args.exterior_only and (args.correct_cockpit or args.helios_livery or args.passenger_cabin or args.cockpit_interior):
        parser.error('--exterior-only applies to regeneration, not individual edit stages')
    blender = find_blender(args.blender)
    (ROOT / 'logs').mkdir(exist_ok=True)
    (ROOT / 'reports').mkdir(exist_ok=True)
    names = (['Boeing_737-300_Helios_Livery.blend'] if args.helios_livery or args.passenger_cabin or args.cockpit_interior else
             ['Boeing_737-300.blend'] if args.correct_cockpit else
             ['HEL-1_Boeing_737-300.blend'] if args.base_only else
             ['HEL-1_Boeing_737-300.blend', 'Boeing_737-300.blend', 'Boeing_737-300_Helios_Livery.blend'])
    backup = ROOT / 'reports' / 'backups' / datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    for name in names:
        path = ROOT / 'models' / name
        if path.exists():
            backup.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, backup / name)
    common = (['--skip-render'] if args.skip_render else []) + (['--draft'] if args.draft else [])
    source = ['--source', str(Path(args.source).resolve())] if args.source else []
    if args.cockpit_interior:
        run(blender, 'update_classic_cockpit.py', 'classic_cockpit.log', source + common)
        run(blender, 'verify_passenger_cabin.py', 'passenger_verification.log')
        return
    if args.passenger_cabin:
        run(blender, 'update_passenger_cabin.py', 'passenger_cabin.log', source + common)
        return
    if args.helios_livery:
        run(blender, 'apply_helios_livery.py', 'helios_livery.log', source + common)
        return
    if args.correct_cockpit:
        run(blender, 'correct_cockpit_windows.py', 'cockpit_correction.log', source + common)
        run(blender, 'verify_cockpit_correction.py', 'cockpit_preservation.log', source)
        return
    build_args = (common + ['--views', args.views]) if args.base_only else ['--skip-render']
    if args.exterior_only:
        build_args.append('--exterior-only')
    run(blender, 'build_aircraft.py', 'run_all.log', build_args)
    run(blender, 'verify_saved.py', 'verification.log')
    if args.base_only:
        print('Finished:', ROOT / 'models' / 'HEL-1_Boeing_737-300.blend')
        return
    run(blender, 'correct_cockpit_windows.py', 'cockpit_correction.log', ['--skip-render'])
    run(blender, 'verify_cockpit_correction.py', 'cockpit_preservation.log')
    run(blender, 'apply_helios_livery.py', 'helios_livery.log', common)
    if not args.exterior_only:
        run(blender, 'update_classic_cockpit.py', 'classic_cockpit.log', common)
        run(blender, 'verify_passenger_cabin.py', 'passenger_verification.log')
        if not args.skip_render:
            run(blender, 'render_passenger_cabin.py', 'passenger_renders.log', ['--draft'] if args.draft else [])
    print('Finished:', ROOT / 'models' / 'Boeing_737-300_Helios_Livery.blend')


if __name__ == '__main__':
    main()

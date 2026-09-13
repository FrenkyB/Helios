"""Editable Classic passenger cabin, shared with the aircraft scene.

Uses the supplied local photographs for shapes, not an operator seating chart.
All stations are in the exterior's coordinate system: +X aft, +Y starboard.
This module never edits cockpit objects, exterior geometry or their materials.
"""
import math
from pathlib import Path

import bpy
from mathutils import Vector

import exterior
import geometry as g

ROOT = Path(__file__).resolve().parents[1]
CABIN_COLLECTION = 'B737_300_CABIN_STUDY'
CABIN_SCENE = '03 | Passenger cabin - 138 seats'
LAYOUT_SCENE = '04 | Passenger cabin layout'


def row_stations(cfg):
    return [cfg['first_row_x'] + i * cfg['seat_pitch'] +
            (cfg['exit_extra_pitch'] if i >= cfg['exit_after_row'] else 0)
            for i in range(cfg['rows'])]


def materials():
    specs = {
        'blue': ((.012, .022, .068), 0, .72),
        'seam': ((.08, .115, .23), 0, .85),
        'cloth': ((.83, .82, .76), 0, .94),
        'plastic': ((.29, .32, .35), .05, .46),
        'dark': ((.025, .029, .035), .05, .64),
        'metal': ((.44, .49, .55), .8, .3),
        'lining': ((.73, .72, .66), 0, .66),
        'white': ((.88, .88, .83), 0, .58),
        'carpet': ((.035, .052, .080), 0, .98),
        'red': ((.47, .018, .012), 0, .53),
    }
    result = {key: g.material('Passenger | ' + key, *spec)
              for key, spec in specs.items()}
    result['light'] = g.material('Passenger | warm fluorescent', (1, .84, .62), 0, .4, 2)
    result['window'] = g.material('Passenger | daylight glazing', (.68, .83, 1), 0, .3, 1.3)
    # Fine fabric grain stays procedural and packed-file independent.
    for key, scale, strength in [('blue', 190, .16), ('carpet', 95, .25)]:
        mat = result[key]
        nodes, links = mat.node_tree.nodes, mat.node_tree.links
        noise = nodes.new('ShaderNodeTexNoise')
        noise.inputs['Scale'].default_value = scale
        bump = nodes.new('ShaderNodeBump')
        bump.inputs['Strength'].default_value = strength
        bump.inputs['Distance'].default_value = .001
        links.new(noise.outputs['Fac'], bump.inputs['Height'])
        links.new(bump.outputs['Normal'], nodes.get('Principled BSDF').inputs['Normal'])
    return result


def seat_prototype(m, width):
    """One upholstered seat, facing -X; copies share meshes but remain editable."""
    before = set(g.COL.objects)
    g.cube('Template cushion', (-.025, 0, .44), (.46, width, .135), m['blue'], .045)
    g.cube('Template seat pan', (0, 0, .345), (.43, width, .045), m['plastic'], .016)
    # A fixed 20-vertex rounded rectangle avoids duplicated resampling vertices.
    sampled = []
    for z, x, w, t in [(.49, .20, width * .88, .11), (.65, .22, width, .13),
                        (.99, .27, width, .14), (1.15, .30, width * .93, .13),
                        (1.19, .305, width * .78, .085)]:
        ring = []
        for sx, sy, start in [(1, 1, 0), (-1, 1, 90), (-1, -1, 180), (1, -1, 270)]:
            for j in range(5):
                angle = math.radians(start + j * 90 / 4)
                ring.append((x + sx * (t / 2 - .025) + .025 * math.cos(angle),
                             sy * (w / 2 - .025) + .025 * math.sin(angle), z))
        sampled.append(ring)
    g.loft('Template back', sampled, m['blue'])
    for y in [-width * .40, width * .40]:
        g.curve('Template upholstery piping', [(.146, y, .58), (.20, y, .96),
                                              (.238, y, 1.12)], m['seam'], .002)
    # Antimacassar drapes over both faces of the headrest, as in the references.
    cover_path = [(.194, .985), (.229, 1.15), (.256, 1.194),
                  (.350, 1.194), (.373, 1.15), (.345, .985)]
    cover = [(x, y, z) for x, z in cover_path for y in [-.135, .135]]
    g.mesh('Template headrest cover', cover,
           [(2*i, 2*i+1, 2*i+3, 2*i+2) for i in range(len(cover_path)-1)], m['cloth'])
    tray = g.cube('Template tray table', (.329, 0, .82), (.025, width * .78, .26), m['plastic'], .018)
    tray.rotation_euler.y = .13
    g.cube('Template tray latch', (.372, 0, .975), (.023, .058, .026), m['dark'], .005)
    g.cube('Template literature pocket', (.307, 0, .595), (.045, width * .75, .19), m['blue'], .012)
    g.cube('Template safety card', (.311, 0, .711), (.01, .18, .07), m['cloth'], .002)
    g.cube('Template safety card stripe', (.319, 0, .730), (.006, .16, .019), m['red'], .001)
    for side in [-1, 1]:
        points = [(.15, side * .185, .518), (.02, side * .09, .518),
                  (-.07, side * .025, .518)]
        verts = [(x + dx, y, z) for x, y, z in points for dx in [-.016, .016]]
        g.mesh('Template lap belt', verts, [(0, 1, 3, 2), (2, 3, 5, 4)], m['dark'], False)
    g.cube('Template belt buckle', (-.067, 0, .523), (.045, .055, .015), m['metal'], .004)
    return [o for o in g.COL.objects if o not in before]


def build_seats(col, cfg, m):
    g.use(col)
    prototype = seat_prototype(m, cfg['cushion_width'])
    floor, cell = cfg['floor_z'], cfg['seat_cell_width']
    inner_arm = cfg['aisle_width'] / 2 + .025
    for row, x in enumerate(row_stations(cfg), 1):
        for side in [-1, 1]:
            # ABC runs window to aisle on port; DEF aisle to window on starboard.
            for j, letter in enumerate('CBA' if side < 0 else 'DEF'):
                y = side * (inner_arm + cell * (j + .5))
                for source in prototype:
                    obj = source.copy()
                    obj.data = source.data
                    obj.name = f'Seat_{row:02}_{letter} ' + source.name.removeprefix('Template ')
                    col.objects.link(obj)
                    obj.location += Vector((x, y, floor))
                    obj['passenger_seat'] = f'{row:02}{letter}'
                    obj['row'] = row
                    obj['seat_letter'] = letter
                # A shared bench has four armrests, avoiding doubled middle arms.
            for j in range(4):
                y = side * (inner_arm + cell * j)
                prefix = f'Bench_{row:02}_{side}_{j}'
                g.cube(prefix + ' armrest', (.02 + x, y, floor + .65),
                       (.40, .05, .064), m['plastic'], .023)
                g.cube(prefix + ' arm support', (.16 + x, y, floor + .52),
                       (.035, .027, .22), m['metal'], .008)
                g.cylinder(prefix + ' recline button', (x - .1, y - .027, floor + .65),
                           (x - .1, y + .027, floor + .65), .012, m['metal'], 12)
            g.cube(f'Bench_{row:02}_{side} crossbeam', (x + .08, side * (inner_arm + 1.5 * cell), floor + .29),
                   (.08, 3 * cell, .065), m['metal'], .01)
            for j in [.5, 2.5]:
                y = side * (inner_arm + cell * j)
                for dx in [-.13, .16]:
                    g.cylinder(f'Bench_{row:02}_{side} leg', (x + dx, y, floor + .035),
                               (x + .08, y, floor + .29), .023, m['metal'], 12)
                    g.cube(f'Bench_{row:02}_{side} rail shoe', (x + dx, y, floor + .025),
                           (.12, .055, .04), m['metal'], .008)
    for obj in prototype:
        bpy.data.objects.remove(obj, do_unlink=True)


def inner_point(x, angle):
    return exterior.surface(x, angle, -.075)


def shell_strip(name, xs, start, end, m):
    rings = [[inner_point(x, start + (end - start) * i / 40) for i in range(41)] for x in xs]
    # An open arc must not be wrapped by loft(): that would add an opaque chord
    # through the cabin and hide the windows behind a false wall.
    faces = [(row * 41 + i, row * 41 + i + 1, (row + 1) * 41 + i + 1, (row + 1) * 41 + i)
             for row in range(len(rings) - 1) for i in range(40)]
    return g.mesh(name, [point for ring in rings for point in ring], faces, m)


def side_point(x, z, side, inset=.095):
    px, py, pz = exterior.sidepoint(x, z, side, -inset)
    return px, py, pz


def build_shell(col, cfg, m):
    g.use(col)
    xs = [cfg['front_x'] + i * (cfg['rear_x'] - cfg['front_x']) / 88 for i in range(89)]
    shell_strip('Passenger sidewall starboard', xs, -.26, 1.08, m['lining'])
    shell_strip('Passenger sidewall port', xs, math.pi - 1.08, math.pi + .26, m['lining'])
    shell_strip('Passenger ceiling crown', xs, 1.08, math.pi - 1.08, m['white'])
    for x in xs[::6]:
        g.curve('Passenger ceiling panel seam', [inner_point(x, 1.07 + i * (math.pi - 2.14) / 32)
                                                for i in range(33)], m['plastic'], .002)
    for side in [-1, 1]:
        for i in range(44):
            x = 5.95 + i * .508
            if x > 26.95 or abs(x - 14.65) < .39:
                continue
            outline = g.rounded_rect(x, 3.65, .285, .42, .085, 6)
            points = [side_point(a, b, side, .103) for a, b in outline]
            g.mesh(f'Passenger window {side} {i:02}', points, [tuple(range(len(points)))], m['window'], False)
            g.curve(f'Passenger window reveal {side} {i:02}', points, m['white'], .025, True)
            g.cube(f'Passenger shade grip {side} {i:02}', side_point(x, 3.83, side, .13),
                   (.075, .025, .018), m['plastic'], .005)
        outline = g.rounded_rect(14.65, 3.63, .51, .96, .10, 6)
        points = [side_point(a, b, side, .11) for a, b in outline]
        g.mesh(f'Passenger overwing hatch {side}', points, [tuple(range(len(points)))], m['white'], False)
        g.curve(f'Passenger overwing hatch seal {side}', points, m['plastic'], .008, True)
        g.cube(f'Passenger overwing handle {side}', side_point(14.65, 3.45, side, .14),
               (.17, .035, .025), m['red'], .006)


def build_bins(col, cfg, m):
    g.use(col)
    start, end, count = 5.75, 24.5, 15
    step = (end - start) / count
    for side in [-1, 1]:
        for i in range(count):
            x = start + (i + .5) * step
            # Classic closed-bin profile, sloping inward toward the aisle.
            cross = [(.82, 4.47), (.88, 4.36), (1.39, 4.25),
                     (1.43, 4.36), (1.10, 4.67), (.93, 4.77)]
            rings = [[(a, side * y, z) for y, z in cross] for a in [x - step / 2 + .009, x + step / 2 - .009]]
            obj = g.loft(f'Passenger overhead bin {side} {i:02}', rings, m['lining'])
            g.bevel(obj, .025, 3)
            g.cube(f'Passenger bin latch {side} {i:02}', (x, side * .857, 4.43),
                   (.17, .027, .030), m['plastic'], .01)
        g.curve(f'Passenger ceiling light cove {side}',
                [(x, side * .81, 4.79) for x in [5.65, 24.5]], m['light'], .021)
        for row, x in enumerate(row_stations(cfg), 1):
            g.cube(f'Passenger PSU {side} {row:02}', (x, side * 1.13, 4.255),
                   (.53, .36, .045), m['white'], .024)
            for dx in [-.16, 0, .16]:
                g.cylinder('Passenger adjustable air vent', (x + dx, side * 1.22, 4.228),
                           (x + dx, side * 1.22, 4.208), .031, m['plastic'], 16)
                g.cylinder('Passenger vent nozzle', (x + dx, side * 1.22, 4.206),
                           (x + dx, side * 1.22, 4.197), .016, m['dark'], 12)
                g.cylinder('Passenger reading light', (x + dx, side * 1.07, 4.228),
                           (x + dx, side * 1.07, 4.207), .026, m['light'], 16)
            g.text(f'Passenger row label {side} {row:02}', f'{row:02}  {"ABC" if side < 0 else "DEF"}',
                   (x, side * .832, 4.51), .044, m['dark'],
                   (math.pi / 2, 0, 0 if side > 0 else math.pi))


def build_floor(col, cfg, m):
    g.use(col)
    rings = []
    for i in range(90):
        x = cfg['front_x'] + i * (cfg['rear_x'] - cfg['front_x']) / 89
        y = abs(side_point(x, cfg['floor_z'], 1, .085)[1])
        rings.append([(x, -y, cfg['floor_z'] - .065), (x, y, cfg['floor_z'] - .065),
                      (x, y, cfg['floor_z']), (x, -y, cfg['floor_z'])])
    g.loft('Passenger cabin floor', rings, m['carpet'])
    start, end = row_stations(cfg)[0] - .36, row_stations(cfg)[-1] + .41
    for side in [-1, 1]:
        for j in [.5, 2.5]:
            y = side * (cfg['aisle_width'] / 2 + .025 + cfg['seat_cell_width'] * j)
            g.cube('Passenger seat track', ((start + end) / 2, y, cfg['floor_z'] + .007),
                   (end - start, .025, .009), m['metal'], .003)
        g.cube('Passenger aisle escape path', (15.5, side * .237, cfg['floor_z'] + .007),
               (20.6, .013, .009), m['light'], .003)
    for side in [-1, 1]:
        g.cube('Passenger overwing escape path', (14.64, side * .98, cfg['floor_z'] + .01),
               (.035, 1.42, .012), m['light'], .003)


def build_service(col, cfg, m):
    g.use(col)
    f = cfg['floor_z']
    for label, x, direction in [('Forward', cfg['front_x'] + .015, 1),
                                ('Aft', cfg['rear_x'] - .015, -1)]:
        radius, bottom, top = exterior.profile(x)
        center = (bottom + top) / 2
        angle = math.asin((f - center) / ((top - bottom) / 2 - .075))
        outline = [inner_point(x, angle + i * (math.pi - 2 * angle) / 64) for i in range(65)]
        g.mesh(f'Passenger {label} bulkhead', outline, [tuple(range(len(outline)))], m['lining'], False)
        g.cube(f'Passenger {label} center door', (x + direction * .022, 0, f + .87),
               (.024, .64, 1.74), m['plastic'], .026)
        g.cube(f'Passenger {label} center door handle', (x + direction * .042, .22, f + .90),
               (.024, .024, .14), m['metal'], .006)
    # Compact service monuments leave the central aisle and exit-row passage open.
    for label, x, y, depth, width in [('Forward', 5.36, .96, .62, .64),
                                      ('Aft', 25.95, .70, 1.20, .65)]:
        face = x + depth / 2 + .015 if label == 'Forward' else x - depth / 2 - .015
        g.cube(f'Passenger {label} galley', (x, y, f + .80), (depth, width, 1.60), m['lining'], .025)
        for z in [f + .36, f + .98, f + 1.36]:
            g.cube(f'Passenger {label} galley door', (face, y, z), (.025, width - .05, .31), m['plastic'], .012)
            g.cube(f'Passenger {label} galley handle', (face + (.024 if label == 'Forward' else -.024), y, z + .06),
                   (.025, .12, .025), m['metal'], .005)
        g.cube(f'Passenger {label} galley countertop', (x, y, f + .81),
               (depth + .025, width + .025, .035), m['metal'], .012)
    g.cube('Passenger forward wardrobe', (5.36, -.98, f + .82), (.62, .64, 1.64), m['lining'], .025)
    # Aft lavatory with separate walls, door, toilet and basin.
    x, y = 25.94, -.68
    for dx in [-.59, .59]:
        g.cube('Passenger lavatory end wall', (x + dx, y, f + .85), (.04, .82, 1.70), m['lining'], .008)
    for dy in [-.40, .40]:
        g.cube('Passenger lavatory side wall', (x, y + dy, f + .85), (1.20, .035, 1.70), m['lining'], .008)
    g.cube('Passenger lavatory door', (x - .62, y, f + .80), (.025, .64, 1.56), m['white'], .016)
    g.cube('Passenger lavatory door handle', (x - .645, y + .22, f + .93), (.028, .025, .14), m['metal'], .007)
    g.text('Passenger lavatory sign', 'LAVATORY', (x - .646, y, f + 1.39), .063, m['dark'], (math.pi / 2, 0, -math.pi / 2))
    g.cube('Passenger lavatory toilet base', (26.12, -.79, f + .22), (.34, .33, .44), m['white'], .08)
    g.cube('Passenger lavatory toilet lid', (26.10, -.79, f + .46), (.43, .36, .045), m['plastic'], .1)
    g.cube('Passenger lavatory washbasin', (25.66, -.90, f + .78), (.32, .25, .12), m['white'], .065)
    for x in [5.0, 24.98]:
        g.cube('Passenger exit sign panel', (x, 0, 4.45), (.035, .49, .14), m['white'], .01)
        for side in [-1, 1]:
            g.text('Passenger illuminated EXIT', 'EXIT', (x + side * .022, 0, 4.415), .085, m['red'],
                   (math.pi / 2, 0, side * math.pi / 2))


def camera(col, name, loc, target, lens=23, ortho=None):
    data = bpy.data.cameras.new(name)
    data.lens = lens
    data.clip_start = .02
    data.clip_end = 150
    if ortho:
        data.type = 'ORTHO'
        data.ortho_scale = ortho
    obj = bpy.data.objects.new(name, data)
    col.objects.link(obj)
    obj.location = loc
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat('-Z', 'Y').to_euler()
    return obj


def scene(name, collections, loc, target, ortho=None):
    result = bpy.data.scenes.new(name)
    for col in collections:
        result.collection.children.link(col)
    rig = bpy.data.collections.new(name + ' | lighting and cameras')
    result.collection.children.link(rig)
    result.camera = camera(rig, name + ' camera', loc, target, ortho=ortho)
    result.unit_settings.system = 'METRIC'
    result.render.engine = 'CYCLES'
    result.cycles.device = bpy.context.scene.cycles.device
    result.cycles.samples = 48
    result.cycles.use_denoising = True
    result.cycles.max_bounces = 6
    result.render.resolution_x = 1600
    result.render.resolution_y = 1000 if not ortho else 650
    result.render.resolution_percentage = 100
    result.render.image_settings.file_format = 'PNG'
    result.view_settings.view_transform = 'AgX'
    world = bpy.data.worlds.new(name + ' world')
    world.use_nodes = True
    world.node_tree.nodes['Background'].inputs[0].default_value = (.68, .77, .9, 1)
    world.node_tree.nodes['Background'].inputs[1].default_value = .3
    result.world = world
    for x in [6.2, 9, 12, 15, 18, 21, 24, 26]:
        data = bpy.data.lights.new(name + ' wash', 'AREA')
        data.energy = 90 if not ortho else 150
        data.shape = 'DISK'
        data.size = 1.3
        obj = bpy.data.objects.new(data.name, data)
        rig.objects.link(obj)
        obj.location = (x, 0, 4.86 if not ortho else 7)
    result.render.filepath = str(ROOT / 'renders' / ('passenger_layout.png' if ortho else 'passenger_cabin.png'))
    return result, rig


def build(cfg):
    m = materials()
    root = g.collection(CABIN_COLLECTION)
    root['layout'] = f"{cfg['rows']} rows x 6; {cfg['seat_pitch']} m nominal pitch; {cfg['aisle_width']} m clear aisle"
    root['reference'] = cfg['reference']
    root['seat_count'] = cfg['rows'] * 6
    root['integrated_in_aircraft'] = True
    root['window_scope'] = 'Interior luminous glazing inserts; existing exterior skin remains closed.'
    parts = {key: g.collection('Passenger | ' + key, root)
             for key in ['Seats', 'Floor and tracks', 'Sidewalls and ceiling', 'Overhead bins and PSU', 'Service areas']}
    build_seats(parts['Seats'], cfg, m)
    build_floor(parts['Floor and tracks'], cfg, m)
    build_shell(parts['Sidewalls and ceiling'], cfg, m)
    build_bins(parts['Overhead bins and PSU'], cfg, m)
    build_service(parts['Service areas'], cfg, m)
    cabin, rig = scene(CABIN_SCENE.replace('138', str(cfg['rows'] * 6)), [root],
                       (24.85, 0, 3.98), (8, 0, 3.79))
    camera(rig, 'Passenger camera | forward looking aft', (5.7, 0, 3.98), (22, 0, 3.79))
    camera(rig, 'Passenger camera | seat detail', (9.45, -.02, 4.12), (7.75, -1.0, 3.28), lens=37)
    layout, _ = scene(LAYOUT_SCENE, [parts[k] for k in ['Seats', 'Floor and tracks', 'Service areas']],
                      (16, 0, 35), (16, 0, 2.68), ortho=24)
    # Put the nose at the left edge of the plan.
    layout.camera.rotation_euler = (0, 0, 0)
    return {'cabin': cabin, 'cabin_layout': layout}

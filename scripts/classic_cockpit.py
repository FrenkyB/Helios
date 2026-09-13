"""737 Classic flight deck, fitted to the saved exterior without changing it.

Panel layout follows the supplied 737-300_cockpit overview and detail boards. This is an editable visual reconstruction, not operational avionics.
"""
import math
from pathlib import Path

import bpy
import bmesh
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

import exterior
import geometry as g

ROOT = Path(__file__).resolve().parents[1]
COLLECTION = 'B737_300_COCKPIT_STUDY'
SCENE = '02 | 737 Classic flight deck'
PREFIX = 'Flight deck | '
FLOOR = 2.55
REAR = 4.84


def materials():
    specs = {
        'panel': ((.16, .205, .24), .12, .52),
        'edge': ((.075, .10, .12), .15, .55),
        'black': ((.009, .013, .018), .03, .48),
        'dial': ((.008, .013, .017), 0, .68),
        'ivory': ((.79, .78, .68), 0, .62),
        'liner': ((.43, .45, .43), .04, .72),
        'metal': ((.43, .48, .51), .8, .28),
        'wool': ((.33, .30, .24), 0, .95),
        'belt': ((.18, .17, .14), 0, .91),
        'carpet': ((.035, .044, .044), 0, .95),
        'sky': ((.03, .22, .34), 0, .58),
        'earth': ((.30, .17, .07), 0, .68),
        'red': ((.37, .014, .010), .04, .47),
        'amber': ((.53, .19, .014), .05, .43),
        'green': ((.045, .24, .09), 0, .55),
    }
    result = {key: g.material(PREFIX + key, *spec) for key, spec in specs.items()}
    result['digits'] = g.material(PREFIX + 'warm numerals', (.83, .60, .30), 0, .5, .25)
    result['daylight'] = g.material(PREFIX + 'interior glazing', (.36, .56, .68), 0, .32, .3)
    mat = result['wool']
    noise = mat.node_tree.nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 220
    bump = mat.node_tree.nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = .45
    bump.inputs['Distance'].default_value = .002
    mat.node_tree.links.new(noise.outputs['Fac'], bump.inputs['Height'])
    mat.node_tree.links.new(bump.outputs['Normal'], mat.node_tree.nodes.get('Principled BSDF').inputs['Normal'])
    return result


def box(name, loc, size, mat, bevel=.008):
    return g.cube(PREFIX + name, loc, size, mat, bevel)


def label(name, text, loc, size, mat):
    return g.text(PREFIX + name, text, loc, size, mat, (math.pi / 2, 0, math.pi / 2))


def surface_group(collection, origin, angle, builder):
    """Build in panel coordinates: X out of face, Y right, Z up."""
    g.use(collection)
    before = set(collection.objects)
    builder()
    bpy.context.view_layer.update()
    transform = Matrix.Translation(Vector(origin)) @ Matrix.Rotation(angle, 4, 'Y')
    for obj in collection.objects:
        if obj not in before:
            obj.matrix_world = transform @ obj.matrix_world


def screw(name, y, z, m, x=.008):
    g.cylinder(PREFIX + name, (x, y, z), (x + .002, y, z), .004, m['metal'], 12)
    g.curve(PREFIX + name + ' slot', [(x + .0025, y - .002, z), (x + .0025, y + .002, z)], m['black'], .0005)


def knob(name, y, z, m, radius=.011, x=.015, color='ivory'):
    g.cylinder(PREFIX + name + ' collar', (x, y, z), (x + .006, y, z), radius * 1.25, m['black'], 20)
    g.cylinder(PREFIX + name, (x + .006, y, z), (x + .025, y, z), radius, m[color], 20)
    g.curve(PREFIX + name + ' index', [(x + .026, y, z), (x + .026, y, z + radius * .8)], m['black'], .001)


def toggle(name, y, z, m, x=.014):
    g.cylinder(PREFIX + name + ' ring', (x, y, z), (x + .004, y, z), .007, m['metal'], 12)
    g.cylinder(PREFIX + name + ' stem', (x + .004, y, z), (x + .020, y, z + .009), .0024, m['metal'], 10)
    g.sphere(PREFIX + name + ' tip', (x + .022, y, z + .01), (.004, .004, .006), m['ivory'], 12, 8)


def seats_and_controls(col, m):
    g.use(col)
    for side in [-1, 1]:
        # Leave knee/torso space behind the fixed yokes; X increases aft.
        tag, x, y = ('Captain' if side < 0 else 'First officer'), 3.55, side * .70
        box(tag + ' seat pedestal', (x, y, FLOOR + .19), (.32, .34, .32), m['edge'], .022)
        for dy in [-.17, .17]:
            box(tag + ' seat rail', (x + .03, y + dy, FLOOR + .017), (.91, .035, .026), m['metal'], .004)
        box(tag + ' cushion', (x - .035, y, FLOOR + .44), (.48, .48, .14), m['wool'], .060)
        back = box(tag + ' seat back', (x + .26, y, FLOOR + .82), (.13, .47, .76), m['wool'], .055)
        back.rotation_euler.y = .09
        frame = box(tag + ' seat back frame', (x + .33, y, FLOOR + .80), (.06, .49, .76), m['edge'], .025)
        frame.rotation_euler.y = .09
        box(tag + ' headrest', (x + .30, y, FLOOR + 1.20), (.16, .34, .23), m['wool'], .055)
        for dy in [-.255, .255]:
            box(tag + ' armrest', (x + .015, y + dy, FLOOR + .665), (.38, .061, .065), m['black'], .024)
            g.cylinder(PREFIX + tag + ' armrest support', (x + .18, y + dy, FLOOR + .40),
                       (x + .18, y + dy, FLOOR + .64), .015, m['metal'], 12)
        for sign in [-1, 1]:
            strap = [(x + .195, y + sign * .145, FLOOR + 1.07),
                     (x + .15, y + sign * .10, FLOOR + .67),
                     (x - .02, y + sign * .025, FLOOR + .519)]
            verts = [(a, b + delta, c) for a, b, c in strap for delta in [-.018, .018]]
            g.mesh(PREFIX + tag + ' shoulder harness', verts, [(0, 1, 3, 2), (2, 3, 5, 4)], m['belt'], False)
        box(tag + ' harness buckle', (x - .02, y, FLOOR + .525), (.045, .06, .018), m['metal'], .005)
        g.cylinder(PREFIX + tag + ' control column', (2.78, y, FLOOR + .08), (2.72, y, 3.09), .040, m['edge'], 24)
        g.cylinder(PREFIX + tag + ' yoke shaft', (2.71, y, 3.085), (2.91, y, 3.12), .028, m['black'], 24)
        points = [(2.91, y - .18, 3.30), (2.925, y - .21, 3.20), (2.925, y - .175, 3.08),
                  (2.925, y - .08, 3.045), (2.925, y + .08, 3.045), (2.925, y + .175, 3.08),
                  (2.925, y + .21, 3.20), (2.91, y + .18, 3.30)]
        g.curve(PREFIX + tag + ' classic control yoke', points, m['black'], .023)
        for grip_side in [-1, 1]:
            box(tag + ' yoke grip', (2.91, y + grip_side*.185, 3.285), (.052, .060, .088), m['black'], .012)
        g.cylinder(PREFIX + tag + ' yoke disconnect', (2.951, y+.046, 3.205), (2.976, y+.046, 3.205), .008, m['amber'], 16)
        box(tag + ' yoke checklist', (2.963, y, 3.155), (.027, .11, .20), m['black'], .02)
        for j, text in enumerate(['TAKEOFF', 'FLAPS ... SET', 'TRIM ... SET', 'BRAKES ... OFF', 'LANDING', 'GEAR ... DOWN', 'FLAPS ... SET']):
            label(tag + ' checklist line', text, (2.981, y, 3.221 - j * .022), .008, m['ivory'])
        for dy in [-.15, .15]:
            pedal = box(tag + ' rudder pedal', (2.47, y + dy, FLOOR + .145), (.075, .19, .18), m['metal'], .012)
            pedal.rotation_euler.y = -.25
            for dz in [-.055, 0, .055]:
                g.curve(PREFIX + tag + ' pedal rib', [(2.516, y + dy - .073, FLOOR + .145 + dz),
                                                    (2.516, y + dy + .073, FLOOR + .145 + dz)], m['black'], .004)


def shell_and_windows(col, m):
    g.use(col)
    fuselage = bpy.data.objects['Fuselage | continuous quad loft']
    vertices = [fuselage.matrix_world @ v.co for v in fuselage.data.vertices]
    bvh = BVHTree.FromPolygons(vertices, [tuple(p.vertices) for p in fuselage.data.polygons])
    panes = [bpy.data.objects[f'Cockpit pane_{side}_{i}'] for side in ['L', 'R'] for i in [1, 2, 3]]
    pane_trees = [BVHTree.FromPolygons([p.matrix_world @ v.co for v in p.data.vertices],
                  [tuple(f.vertices) for f in p.data.polygons]) for p in panes]
    faces = []
    for face in fuselage.data.polygons:
        center = sum((vertices[i] for i in face.vertices), Vector()) / len(face.vertices)
        if not (1.08 < center.x < REAR and center.z > FLOOR) or any(vertices[i].x > REAR for i in face.vertices):
            continue
        faces.append(tuple(face.vertices))
    # Refine only the cockpit patch before cutting the glazing outlines. The
    # original nose grid is too coarse for a clean window-to-trim boundary.
    used = sorted({i for face in faces for i in face})
    remap = {old: new for new, old in enumerate(used)}
    patch = bpy.data.meshes.new(PREFIX + 'Temporary shell patch')
    patch.from_pydata([vertices[i] for i in used], [], [tuple(remap[i] for i in face) for face in faces])
    bm = bmesh.new()
    bm.from_mesh(patch)
    bmesh.ops.subdivide_edges(bm, edges=list(bm.edges), cuts=4, use_grid_fill=True)
    remove = [face for face in bm.faces if any(tree.find_nearest(face.calc_center_median())[3] < .012
                                               for tree in pane_trees)]
    bmesh.ops.delete(bm, geom=remove, context='FACES')
    for vertex in bm.verts:
        vertex.co -= bvh.find_nearest(vertex.co)[1] * .048
    bm.to_mesh(patch)
    bm.free()
    obj = bpy.data.objects.new(PREFIX + 'Cockpit shell liner', patch)
    col.objects.link(obj)
    patch.materials.append(m['liner'])
    for face in patch.polygons:
        face.use_smooth = True
    for source in panes:
        points = []
        for v in source.data.vertices:
            p = source.matrix_world @ v.co
            normal = bvh.find_nearest(p)[1]
            points.append(p - normal * .062)
        obj = g.mesh(PREFIX + 'Inner windshield ' + source.name.removeprefix('Cockpit pane_'), points,
                     [tuple(f.vertices) for f in source.data.polygons], m['daylight'])
        obj['source_exterior_pane'] = source.name
        frame = bpy.data.objects[source.name.replace('pane_', 'frame_')]
        outline = []
        for p in frame.data.splines[0].points:
            point = frame.matrix_world @ Vector(p.co[:3])
            outline.append(point - bvh.find_nearest(point)[1] * .072)
        g.curve(PREFIX + 'Windshield structural frame ' + source.name[-3:], outline, m['edge'], .026, True)
    rings = []
    for i in range(55):
        x = 1.90 + i * (REAR - 1.90) / 54
        width = abs(exterior.sidepoint(x, FLOOR, 1, -.10)[1])
        rings.append([(x, -width, FLOOR - .045), (x, width, FLOOR - .045),
                      (x, width, FLOOR), (x, -width, FLOOR)])
    g.loft(PREFIX + 'Cockpit floor', rings, m['carpet'])
    # Separate aft boundary is ahead of the preserved passenger bulkhead.
    x = REAR - .055
    ry, bottom, top = exterior.profile(x)
    center = (top + bottom) / 2
    start = math.asin((FLOOR - center) / ((top - bottom) / 2 - .09))
    outline = [exterior.surface(x, start + i * (math.pi - 2 * start) / 64, -.09) for i in range(65)]
    g.mesh(PREFIX + 'Rear cockpit boundary', outline, [tuple(range(len(outline)))], m['liner'], False)
    box('Cockpit door', (x - .024, 0, FLOOR + .94), (.035, .65, 1.88), m['panel'], .025)
    g.curve(PREFIX + 'Cockpit door seal', [(x - .046, y, z) for y, z in g.rounded_rect(0, FLOOR + .94, .69, 1.93, .04, 5)], m['black'], .007, True)
    box('Cockpit door handle', (x - .055, -.235, FLOOR + .91), (.035, .028, .16), m['metal'], .007)
    g.cylinder(PREFIX + 'Cockpit door viewer', (x - .048, 0, FLOOR + 1.61), (x - .059, 0, FLOOR + 1.61), .014, m['black'], 20)
    box('Observer jumpseat back', (4.27, -1.38, FLOOR + .93), (.45, .105, .69), m['wool'], .045)
    box('Observer jumpseat folded cushion', (4.27, -1.32, FLOOR + .47), (.45, .15, .35), m['wool'], .04)
    for dx in [-.16, .16]:
        box('Observer jumpseat harness', (4.27 + dx, -1.317, FLOOR + .93), (.033, .013, .55), m['belt'], .004)
    box('Observer jumpseat hinge', (4.27, -1.28, FLOOR + .32), (.48, .065, .065), m['metal'], .012)


def make_scene(root):
    scene = bpy.data.scenes.new(SCENE)
    scene.collection.children.link(root)
    scene.unit_settings.system = 'METRIC'
    scene['scope'] = '737 Classic EFIS flight deck matching the supplied 737-300_cockpit panel reference; not a verified Helios equipment fit.'
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 48
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 8
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 1100
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.view_settings.view_transform = 'AgX'
    scene.world = bpy.data.worlds.new(PREFIX + 'inspection world')
    scene.world.use_nodes = True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value = (.54, .67, .78, 1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value = .3
    rig = bpy.data.collections.new(PREFIX + 'Inspection cameras and lights')
    scene.collection.children.link(rig)
    cameras = {}
    for name, loc, target, lens in [
            ('overview', (4.53, 0, 3.93), (2.40, 0, 3.40), 19),
            ('instruments', (3.86, 0, 4.07), (2.40, 0, 3.18), 24),
            ('overhead', (3.75, 0, 3.30), (3.03, 0, 4.26), 19),
            ('seats_and_door', (2.80, .04, 3.76), (4.05, -.18, 3.40), 18)]:
        data = bpy.data.cameras.new(PREFIX + 'Camera ' + name)
        data.lens, data.clip_start, data.clip_end = lens, .015, 100
        obj = bpy.data.objects.new(data.name, data)
        rig.objects.link(obj)
        obj.location = loc
        obj.rotation_euler = (Vector(target) - obj.location).to_track_quat('-Z', 'Y').to_euler()
        cameras[name] = obj
    scene.camera = cameras['overview']
    for name, loc, target, power, size in [
            ('front daylight', (2.13, 0, 3.95), (3.15, 0, 3.05), 45, 1.10),
            ('rear bounce', (4.40, 0, 4.29), (2.5, 0, 3.25), 65, 1.15),
            ('overhead fill', (3.12, 0, 3.52), (3.04, 0, 4.29), 12, .60),
            ('captain side fill', (3.3, -.98, 4.04), (3.20, 0, 3.0), 15, .65)]:
        data = bpy.data.lights.new(PREFIX + name, 'AREA')
        data.energy, data.shape, data.size = power, 'DISK', size
        obj = bpy.data.objects.new(data.name, data)
        rig.objects.link(obj)
        obj.location = loc
        obj.rotation_euler = (Vector(target) - obj.location).to_track_quat('-Z', 'Y').to_euler()
    scene.render.filepath = str(ROOT / 'renders' / 'cockpit' / 'overview.png')
    return scene


def build():
    import cockpit_reference_panels as panels
    m = materials()
    root = g.collection(COLLECTION)
    panels.reference_metadata(root)
    root['coordinate_system'] = 'X aft from nose, +Y starboard, +Z up; metres'
    root['integrated_in_aircraft'] = True
    parts = {name: g.collection(PREFIX + name, root) for name in
             ['Shell and windshield', 'Main instrument panel', 'Glareshield and MCP',
              'Crew seats and controls', 'Pedestal and throttle', 'Side consoles', 'Overhead and pressurization']}
    shell_and_windows(parts['Shell and windshield'], m)
    panels.main_panel(parts['Main instrument panel'], m)
    panels.glareshield(parts['Glareshield and MCP'], m)
    seats_and_controls(parts['Crew seats and controls'], m)
    panels.pedestal(parts['Pedestal and throttle'], m)
    panels.side_consoles(parts['Side consoles'], m)
    panels.overhead(parts['Overhead and pressurization'], m)
    return make_scene(root)

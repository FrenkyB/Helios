"""Classic EFIS panels traced in pixels from the user's 737-300_cockpit set.

The overview determines the assembly order; the enlarged images supply labels
and screen artwork. UV crops use the original images without resampling. Major
bezels, selectors, switches, keys and levers remain separate editable geometry.
"""
import math
from pathlib import Path

import bpy
import geometry as g
import classic_cockpit as c

ASSETS = Path(__file__).resolve().parents[1] / 'assets' / 'cockpit'
P = c.PREFIX


def image_material(filename, emissive=False):
    name = P + 'Reference ' + filename + (' illuminated' if emissive else '')
    existing = bpy.data.materials.get(name)
    if existing:
        return existing
    image = bpy.data.images.load(str(ASSETS / filename), check_existing=True)
    image.pack()
    mat = g.material(name, (.25, .28, .30), .04, .65)
    texture = mat.node_tree.nodes.new('ShaderNodeTexImage')
    texture.image = image
    texture.interpolation = 'Linear'
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    mat.node_tree.links.new(texture.outputs['Color'], bsdf.inputs['Base Color'])
    if emissive:
        mat.node_tree.links.new(texture.outputs['Color'], bsdf.inputs['Emission Color'])
        bsdf.inputs['Emission Strength'].default_value = .30
    return mat


class Panel:
    """Source pixel -> local face (X depth, Y right, Z up)."""
    def __init__(self, filename, region, width, m, height=None):
        self.filename, self.region, self.width, self.m = filename, region, width, m
        left, top, right, bottom = region
        self.sx = width / (right - left)
        self.sz = (height / (bottom - top)) if height else self.sx
        self.cx, self.cy = (left + right) / 2, (top + bottom) / 2
        self.material = image_material(filename)
        self.image_size = tuple(bpy.data.images.get(filename).size)

    def point(self, px, py, depth=0):
        return depth, (px - self.cx) * self.sx, (self.cy - py) * self.sz

    def uv(self, obj):
        layer = obj.data.uv_layers.active or obj.data.uv_layers.new(name='Reference_pixels')
        layer.name = 'Reference_pixels'
        width, height = self.image_size
        for loop in obj.data.loops:
            co = obj.data.vertices[loop.vertex_index].co
            px, py = co.y / self.sx + self.cx, self.cy - co.z / self.sz
            layer.data[loop.index].uv = (px / width, 1 - py / height)
        obj['reference_image'] = self.filename

    def plate(self, name, rect=None, polygon=None, depth=.012, thickness=.025, illuminated=False):
        if polygon is None:
            left, top, right, bottom = rect or self.region
            polygon = [(left, top), (left, bottom), (right, bottom), (right, top)]
        front = [self.point(x, y, depth) for x, y in polygon]
        back = [self.point(x, y, depth - thickness) for x, y in polygon]
        n = len(polygon)
        faces = [tuple(range(n)), tuple(range(2*n - 1, n - 1, -1))]
        faces += [(i, (i+1) % n, (i+1) % n+n, i+n) for i in range(n)]
        mat = image_material(self.filename, True) if illuminated else self.material
        obj = g.mesh(P + name, front + back, faces, mat, False)
        obj.data.materials.append(self.m['edge'])
        for face in obj.data.polygons:
            face.material_index = 0 if face.index == 0 else 1
        self.uv(obj)
        obj['reference_region_px'] = list(rect or self.region)
        return obj

    def gauge(self, name, px, py, radius, depth=.029):
        _, y, z = self.point(px, py)
        g.cylinder(P + name + ' bezel', (.013, y, z), (depth, y, z), radius*self.sx,
                   self.m['black'], 48)
        points = [self.point(px + radius*.88*math.cos(i*math.tau/64),
                            py - radius*.88*math.sin(i*math.tau/64), depth+.001) for i in range(64)]
        obj = g.mesh(P + name + ' face', points, [tuple(range(64))], self.material, False)
        self.uv(obj)
        obj['instrument_kind'] = 'classic_analog'
        return obj

    def selector(self, name, px, py, radius=6, depth=.018, color='ivory'):
        _, y, z = self.point(px, py)
        c.knob(name, y, z, self.m, radius*self.sx, x=depth, color=color)
        bpy.data.objects[P + name]['reference_pixel'] = (px, py)

    def toggle(self, name, px, py):
        _, y, z = self.point(px, py)
        g.cylinder(P + name + ' washer', (.014, y, z), (.018, y, z), .005, self.m['metal'], 12)
        g.cylinder(P + name + ' stem', (.018, y, z), (.038, y, z+.008), .0025, self.m['metal'], 12)
        c.box(name + ' grip', (.040, y, z+.009), (.007, .007, .012), self.m['ivory'], .002)


def main_panel(col, m):
    def build():
        p = Panel('cockpit_1.jpg', (14, 85, 1150, 460), 2.25, m)
        outline = [(14, 163), (167, 121), (405, 94), (760, 94), (994, 121), (1150, 161),
                   (1150, 460), (755, 460), (755, 337), (406, 337), (406, 460), (14, 460)]
        p.plate('Main instrument panel', polygon=outline, thickness=.055)
        for tag, upper, lower in [
                ('CAPT', (168, 124, 284, 229), (167, 235, 286, 369)),
                ('FO', (873, 124, 991, 229), (875, 235, 992, 369))]:
            for role, rect in [('EADI', upper), ('EHSI', lower)]:
                obj = p.plate(tag + ' ' + role, rect, depth=.031, illuminated=True)
                obj['display_role'] = role
                obj['avionics_family'] = '737 Classic EFIS'
        for name, x, y, r in [
                ('CAPT airspeed', 123, 192, 36), ('CAPT altimeter', 325, 194, 29),
                ('CAPT vertical speed', 326, 261, 28), ('CAPT RMI', 128, 283, 29), ('CAPT clock', 56, 277, 26),
                ('FO airspeed', 832, 192, 35), ('FO altimeter', 1030, 192, 29),
                ('FO vertical speed', 1031, 262, 28), ('FO RMI', 837, 284, 28), ('FO clock', 1102, 262, 26),
                ('Standby airspeed', 466, 138, 29), ('Standby attitude', 465, 203, 25),
                ('Standby altitude', 456, 261, 19), ('Standby small left', 442, 302, 16),
                ('Standby small right', 477, 304, 16), ('Flap position', 688, 154, 18),
                ('Brake pressure', 379, 251, 20), ('Fuel quantity left', 774, 257, 18),
                ('Fuel quantity center', 775, 298, 18), ('Fuel quantity right', 775, 341, 18)]:
            p.gauge(name, x, y, r)
        for name, rect in [('Primary engine indicators', (514, 157, 595, 317)),
                           ('Secondary engine indicators', (607, 151, 666, 318))]:
            obj = p.plate(name, rect, depth=.033, illuminated=True)
            obj['display_role'] = 'classic_engine_indicators'
        # The lever is offset right of the two narrow engine instrument stacks.
        _, y, z = p.point(738, 255)
        g.cylinder(P + 'Landing gear lever', (.025, y, z), (.100, y, z-.018), .009, m['metal'], 16)
        g.cylinder(P + 'Landing gear wheel handle', (.100, y-.022, z-.018), (.100, y+.022, z-.018), .022, m['black'], 24)
        for i, (x, y, r) in enumerate([(64, 419, 17), (237, 408, 10), (277, 408, 10),
                                      (324, 408, 10), (925, 411, 10), (966, 411, 10), (1100, 422, 17)]):
            p.selector('MIP lower selector ' + str(i), x, y, r)
    c.surface_group(col, (2.39, 0, 3.10), -.14, build)


def glareshield(col, m):
    g.use(col)
    # Swept, padded wings with the narrower MCP centered above the panel.
    outline = [(-1.12, -.025), (-1.04, .045), (-.60, .092), (-.38, .095),
               (.38, .095), (.60, .092), (1.04, .045), (1.12, -.025)]
    rings = [[(x, y, 3.48+z) for y, z in outline] for x in [2.25, 2.58]]
    obj = g.loft(P + 'Glareshield padded lip', rings, m['black'])
    g.bevel(obj, .012)
    def build():
        p = Panel('cockpit_1.jpg', (404, 14, 761, 69), .74, m)
        p.plate('MCP housing', thickness=.065)
        for name, x, y, r in [('Left course', 438, 42, 5), ('IAS MACH', 506, 42, 7),
                               ('Heading', 553, 42, 5), ('Altitude', 602, 42, 6), ('Right course', 723, 43, 5)]:
            p.selector('MCP ' + name, x, y, r)
        for name, rect in [('MCP left course display', (423, 18, 451, 29)),
                           ('MCP speed display', (486, 17, 522, 30)), ('MCP heading display', (538, 18, 568, 29)),
                           ('MCP altitude display', (581, 17, 620, 29)), ('MCP vertical speed display', (632, 17, 670, 29)),
                           ('MCP right course display', (710, 17, 740, 29))]:
            p.plate(name, rect, depth=.017, thickness=.004, illuminated=True)
        for i, (x, y) in enumerate([(475, 56), (504, 58), (554, 59), (604, 58), (640, 59), (687, 38), (700, 38)]):
            p.plate('MCP pushbutton ' + str(i), (x-5, y-4, x+5, y+4), depth=.025, thickness=.013)
        _, y, z = p.point(659, 45)
        c.box('MCP vertical speed thumbwheel', (.029, y, z), (.025, .020, .050), m['black'], .007)
        # Warning blocks use their own UV crops at the same physical scale.
        for name, region, lateral in [('CAPT', (321, 23, 401, 57), -.455), ('FO', (763, 23, 845, 57), .455)]:
            q = Panel('cockpit_1.jpg', region, .16, m)
            before = set(g.COL.objects)
            q.plate(name + ' warning annunciators', depth=.025)
            for o in g.COL.objects:
                if o not in before:
                    o.location.y = lateral
    c.surface_group(col, (2.60, 0, 3.632), -.10, build)


def cdu_group(col, m):
    def build():
        p = Panel('cockpit_1.jpg', (405, 337, 755, 536), .694, m)
        p.plate('Lower center FMC panel', thickness=.05)
        for tag, left in [('CAPT', 405), ('FO', 640)]:
            p.plate(tag + ' CDU bezel', (left+5, 339, left+114, 535), depth=.023)
            p.plate(tag + ' CDU screen', (left+17, 348, left+100, 410), depth=.028, illuminated=True)
            for row in range(9):
                for key in range(6):
                    x, y = left + 15 + key * 15, 421 + row * 8.9
                    p.plate(tag + f' CDU key {row}_{key}', (x-5, y-3.2, x+5, y+3.2), depth=.033, thickness=.012)
            for side in [-1, 1]:
                for j in range(6):
                    x = left + (10 if side < 0 else 106)
                    y = 356 + j*9
                    p.plate(tag + f' CDU line select {side}_{j}', (x-3, y-2, x+3, y+2), depth=.032)
    c.surface_group(col, (2.51, 0, 2.81), -.40, build)


def pedestal(col, m):
    g.use(col)
    c.box('Center pedestal base', (3.35, 0, 2.80), (1.60, .58, .48), m['panel'], .018)
    c.box('Throttle quadrant', (2.99, 0, 3.055), (.56, .355, .13), m['panel'], .018)
    def throttle_face():
        p = Panel('cockpit_2.jpg', (493, 244, 645, 506), .32, m, height=.55)
        p.plate('Throttle quadrant markings', depth=.007)
    c.surface_group(col, (3.00, 0, 3.118), -math.pi/2, throttle_face)
    for side in [-1, 1]:
        y = side*.062
        g.cylinder(P + 'Thrust lever ' + str(side), (3.035, y, 3.13), (2.96, y, 3.31), .010, m['metal'], 16)
        c.box('Thrust grip ' + str(side), (2.96, y, 3.31), (.062, .074, .039), m['ivory'], .010)
        c.label('Thrust lever number', '1' if side < 0 else '2', (2.993, y, 3.305), .018, m['black'])
        g.cylinder(P + 'Reverse thrust lever ' + str(side), (2.96, y, 3.27), (3.033, y, 3.36), .005, m['metal'], 12)
        c.box('Reverse grip ' + str(side), (3.033, y, 3.36), (.030, .051, .020), m['black'], .005)
        g.cylinder(P + 'Stabilizer trim wheel ' + str(side), (3.04, side*.191, 3.075),
                   (3.04, side*.225, 3.075), .158, m['black'], 64)
        # Alternating white rim sectors, not the previous exposed spoke wheel.
        for quadrant in range(4):
            points = [(3.04 + .147*math.sin(a), side*.230, 3.075 + .147*math.cos(a))
                      for a in [quadrant*math.pi/2 + j*.35/12 for j in range(13)]]
            g.curve(P + 'Trim wheel white rim sector', points, m['ivory'], .010)
        g.cylinder(P + 'Trim wheel folding crank', (3.12, side*.23, 2.98), (3.12, side*.29, 2.98), .009, m['black'], 16)
    for y, name, x, color in [(-.163, 'Speed brake', 2.93, 'black'), (.163, 'Flap lever', 3.15, 'ivory')]:
        g.cylinder(P + name, (3.10, y, 3.13), (x, y, 3.30), .007, m['metal'], 16)
        c.box(name + ' handle', (x, y, 3.30), (.057, .043, .026), m[color], .008)
    def radio_faces():
        p = Panel('cockpit_4.jpg', (416, 423, 746, 777), .59, m)
        p.plate('Aft pedestal radio rack', depth=.012, thickness=.065)
        # Traced horizontal modules preserve the uneven breaks and central blank.
        for name, rect in [('VHF left', (421, 426, 525, 483)), ('VHF center', (528, 426, 635, 483)),
                           ('VHF right', (638, 426, 741, 483)), ('Navigation radio left', (421, 488, 526, 551)),
                           ('Navigation radio center', (529, 488, 634, 551)), ('Navigation radio right', (637, 488, 741, 551)),
                           ('Blank center insert', (523, 554, 642, 621)), ('Audio left', (421, 622, 522, 699)),
                           ('Audio right', (645, 622, 741, 699)), ('Transponder', (422, 703, 741, 735)),
                           ('Rudder and aileron trim', (422, 738, 741, 773))]:
            p.plate(name + ' face', rect, depth=.017, thickness=.007)
        for i, (x, y, r) in enumerate([(435, 458, 6), (509, 458, 6), (543, 458, 6), (618, 458, 6),
                                      (650, 458, 6), (726, 458, 6), (437, 516, 5), (507, 515, 5),
                                      (544, 516, 5), (619, 516, 5), (650, 516, 5), (726, 516, 5),
                                      (441, 579, 10), (718, 579, 10), (439, 713, 5), (720, 714, 5),
                                      (448, 759, 8), (609, 753, 15), (723, 760, 8)]):
            p.selector('Pedestal rotary ' + str(i), x, y, r)
        for side, start in [('left', 432), ('right', 653)]:
            for row in range(2):
                for i in range(7):
                    p.selector(f'Audio {side} volume {row}_{i}', start+i*10.4, 655+row*13, 2.6)
        for i, (x, y) in enumerate([(544, 440), (565, 440), (587, 440), (488, 681), (672, 681), (564, 754)]):
            p.toggle('Pedestal toggle ' + str(i), x, y)
    c.surface_group(col, (3.82, 0, 3.055), -math.pi/2, radio_faces)
    def fire_face():
        p = Panel('cockpit_4.jpg', (474, 369, 693, 423), .38, m)
        p.plate('Fire control module', polygon=[(475, 371), (684, 371), (691, 387), (691, 422), (475, 422)], depth=.012, thickness=.05)
        for name, rect in [('1', (515, 384, 535, 422)), ('APU', (565, 384, 585, 422)), ('2', (622, 384, 642, 422))]:
            p.plate('Fire handle ' + name, rect, depth=.056, thickness=.05)
    c.surface_group(col, (3.425, 0, 3.055), -math.pi/2, fire_face)
    cdu_group(col, m)


def overhead(col, m):
    def forward():
        p = Panel('upper_panel.jpg', (58, 267, 548, 777), .94, m)
        outline = [(58, 267), (548, 267), (548, 743), (509, 762), (453, 777),
                   (161, 777), (98, 762), (58, 743)]
        p.plate('Overhead structural tray', polygon=outline, thickness=.065)
        # Drawn divisions are intentionally asymmetric, as in the supplied board.
        groups = [
            ('Flight controls', (63, 271, 170, 539)), ('Electrical meters', (174, 271, 326, 404)),
            ('Generator bus', (175, 408, 326, 502)), ('Fuel pumps', (174, 506, 251, 708)),
            ('Wipers and heat', (253, 506, 325, 708)), ('Equipment cooling', (330, 272, 416, 383)),
            ('Temperature controls', (418, 272, 544, 444)), ('Anti ice', (330, 387, 416, 485)),
            ('Hydraulic pumps', (330, 489, 416, 551)), ('Air conditioning packs', (330, 555, 416, 708)),
            ('Cabin pressure', (419, 448, 544, 538)), ('Pressurization selectors', (419, 542, 544, 708)),
            ('Fuel crossfeed and pumps', (63, 543, 170, 708)), ('Landing and exterior lights', (67, 713, 235, 745)),
            ('Engine start', (239, 713, 419, 745)), ('Position and runway lights', (423, 713, 539, 745))]
        for name, rect in groups:
            obj = p.plate('Overhead ' + name + ' plate', rect, depth=.016, thickness=.011)
            obj['overhead_group'] = name
        for name, x, y, r in [('AC meter', 198, 295, 17), ('DC meter', 250, 295, 17),
                               ('Frequency meter', 198, 336, 17), ('Load meter', 250, 336, 17),
                               ('Fuel temperature', 220, 520, 13), ('Cabin temperature', 489, 350, 14),
                               ('Supply duct temperature', 469, 410, 14), ('Cabin altitude', 488, 484, 17),
                               ('Duct pressure', 375, 575, 17), ('Cabin vertical speed', 375, 630, 19),
                               ('Pressure differential', 375, 683, 17), ('Fuel crossfeed', 109, 566, 16)]:
            p.gauge('Overhead ' + name, x, y, r, depth=.032)
        selectors = [(195, 372, 8), (251, 372, 8), (306, 367, 8), (461, 354, 6), (521, 354, 6),
                     (109, 590, 9), (217, 704, 7), (475, 571, 7), (508, 570, 7), (461, 674, 7),
                     (479, 741, 7), (271, 741, 8), (366, 741, 8)]
        for i, (x, y, r) in enumerate(selectors):
            p.selector('Overhead selector ' + str(i), x, y, r)
        switches = [(84, 322), (139, 322), (84, 375), (139, 375), (84, 484), (138, 484),
                    (187, 451), (214, 451), (264, 451), (301, 451), (187, 478), (300, 478),
                    (339, 310), (364, 310), (391, 310), (399, 342), (340, 423), (366, 423),
                    (394, 423), (340, 456), (395, 456), (340, 514), (363, 514), (397, 514),
                    (340, 543), (395, 543), (339, 611), (405, 611), (342, 696), (404, 696),
                    (197, 579), (239, 579), (198, 632), (238, 632), (78, 661), (102, 661),
                    (129, 661), (154, 661), (90, 693), (142, 693), (440, 653), (513, 655)]
        for i, (x, y) in enumerate(switches):
            p.toggle('Overhead switch ' + str(i), x, y)
        for i, rect in enumerate([(188, 466, 201, 496), (277, 466, 290, 496), (204, 415, 217, 444)]):
            p.plate('Overhead guarded switch ' + str(i), rect, depth=.042, thickness=.026)
        for name, rect in [('FLT ALT digits', (464, 593, 493, 606)), ('LAND ALT digits', (464, 624, 493, 637))]:
            p.plate(name, rect, depth=.021, thickness=.004, illuminated=True)
        p.selector('Pressurization mode selector', 500, 658, 7)
        for i in range(8):
            p.toggle('Landing light switch ' + str(i), 91+i*17, 734)
    c.surface_group(col, (2.97, 0, 4.27), 1.25, forward)
    def aft():
        p = Panel('upper_panel.jpg', (58, 8, 548, 264), .94, m)
        p.plate('Aft overhead panel', depth=.012, thickness=.050)
        for name, rect in [('IRS navigation', (172, 54, 247, 215)), ('Oxygen', (269, 99, 332, 217)),
                           ('Audio and service', (335, 12, 442, 111)), ('Flight recorder and warning', (447, 85, 543, 215))]:
            p.plate('Aft overhead ' + name, rect, depth=.018, thickness=.008)
        for i in range(7):
            for row in range(2):
                p.selector('Aft overhead audio ' + str(row) + '_' + str(i), 353+i*10.5, 55+row*15, 2.7)
        for i, (x, y) in enumerate([(187, 160), (218, 159), (304, 141), (268, 237), (346, 91), (515, 172)]):
            p.selector('Aft overhead rotary ' + str(i), x, y, 5)
        for row in range(4):
            for key in range(3):
                x, y = 204+key*10, 101+row*12
                p.plate(f'IRS keypad {row}_{key}', (x-4, y-4, x+4, y+4), depth=.027, thickness=.01)
        for i, (x, y, r) in enumerate([(93, 101, 4), (124, 142, 4), (486, 151, 4), (268, 199, 4)]):
            p.toggle('Aft overhead switch ' + str(i), x, y)
    c.surface_group(col, (3.76, 0, 4.56), math.pi/2, aft)


def side_consoles(col, m):
    g.use(col)
    for side in [-1, 1]:
        c.box('Side console ' + str(side), (3.14, side*1.16, 2.94), (1.08, .29, .36), m['panel'], .02)
        c.box('Document pocket ' + str(side), (3.77, side*1.34, 3.06), (.35, .07, .26), m['edge'], .015)
        def build():
            p = Panel('cockpit_4.jpg', (1041, 362, 1229, 786), .24, m)
            outline = [(1047, 364), (1060, 364), (1159, 474), (1168, 483), (1227, 483),
                       (1227, 634), (1221, 650), (1210, 666), (1208, 714), (1208, 766),
                       (1204, 778), (1196, 782), (1108, 782), (1102, 778), (1098, 746),
                       (1097, 714), (1086, 698), (1067, 682), (1049, 666), (1043, 650), (1043, 378)]
            p.plate('Side console control plate ' + str(side), polygon=outline, depth=.012)
            for i, (x, y) in enumerate([(1069, 407), (1100, 430), (1090, 490), (1090, 553)]):
                p.selector(f'Side console {side} knob {i}', x, y, 7)
            p.plate('Side console guarded control ' + str(side), (1080, 491, 1103, 535), depth=.035)
            p.gauge('Side console cup recess ' + str(side), 1152, 725, 24, depth=.015)
        c.surface_group(col, (3.19, side*1.16, 3.125), -math.pi/2, build)
        if side < 0:
            g.use(col)
            g.curve(P + 'Captain nosewheel tiller', [(2.79, -1.20, 3.22), (2.88, -1.19, 3.30),
                         (3.02, -1.19, 3.29), (3.11, -1.20, 3.21)], m['black'], .018)


def reference_metadata(root):
    root['version'] = 'classic_efis_reference_v2'
    root['reference'] = '737-300_cockpit/celotna_slika.jpg plus cockpit_1, cockpit_2, cockpit_4, upper_panel detail images.'
    root['avionics'] = '737 Classic EFIS: paired EADI/EHSI, two narrow engine indicator stacks and separate analog instruments.'
    root['construction'] = 'Editable 3D panel housings and controls; packed source-image UV regions for labels and display faces.'

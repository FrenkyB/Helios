"""737-300 Classic exterior, parameterized from Boeing's general arrangement.

The lofts are visual reconstructions, not Boeing manufacturing geometry.
X increases aft from nose, +Y is starboard, +Z up; ground is Z=0.
"""
import math
from math import sin, cos, pi, sqrt
import bpy
import geometry as g

P = [
    (0.00,.006,2.54,2.55),(.08,.18,2.35,2.75),(.25,.40,2.15,2.98),
    (.60,.68,1.91,3.29),(1.10,.96,1.68,3.60),(1.65,1.20,1.51,3.90),
    (2.20,1.39,1.37,4.24),(2.85,1.57,1.27,4.62),(3.55,1.70,1.21,4.86),
    (4.40,1.80,1.17,5.04),(5.60,1.86,1.15,5.13),(7.30,1.88,1.15,5.16),
    (12.0,1.88,1.15,5.16),(18.8,1.88,1.15,5.16),(22.0,1.88,1.17,5.16),
    (24.0,1.84,1.34,5.15),(26.0,1.69,1.64,5.13),(28.0,1.38,2.10,5.04),
    (29.5,1.02,2.52,4.90),(30.7,.66,2.94,4.67),(31.7,.28,3.38,4.32),
    (32.18,.055,3.85,4.07)]

def profile(x):
    return [g.interp([(p[0],p[k]) for p in P],x) for k in range(1,4)]

def surface(x, theta, offset=0):
    ry,bot,top=profile(x)
    cz=(top+bot)/2
    rz=(top-bot)/2
    return (x,(ry+offset)*cos(theta),cz+(rz+offset)*sin(theta))

def sidepoint(x,z,side,offset=.009):
    ry,bot,top=profile(x)
    cz=(top+bot)/2
    rz=(top-bot)/2
    return (x,side*(ry*sqrt(max(.00001,1-((z-cz)/rz)**2))+offset),z)

def side_glazing(name,outline,side,mat,offset=.019):
    """Concentric surface-domain rings avoid ngons cutting through curved skin."""
    cx=sum(p[0] for p in outline)/len(outline)
    cz=sum(p[1] for p in outline)/len(outline)
    n=len(outline);count=7
    verts=[sidepoint(cx,cz,side,offset)]
    for ring in range(1,count+1):
        t=ring/count
        verts.extend(sidepoint(cx+t*(x-cx),cz+t*(z-cz),side,offset) for x,z in outline)
    faces=[(0,1+j,1+(j+1)%n) for j in range(n)]
    for ring in range(count-1):
        a=1+ring*n;b=a+n
        faces.extend((a+j,a+(j+1)%n,b+(j+1)%n,b+j) for j in range(n))
    return g.mesh(name,verts,faces,mat)

def build(root,cfg):
    mats={
        'white':g.material('Paint | warm white',(.82,.845,.86),.13,.29),
        'wing':g.material('Wing | light Boeing gray',(.51,.56,.61),.2,.36),
        'panel':g.material('Coroguard | center wing',(.32,.365,.40),.28,.47),
        'seam':g.material('Panel seams | soft graphite',(.115,.14,.16),.25,.5),
        'glass':g.material('Glazing | smoked blue',(.012,.034,.052),.45,.16),
        'metal':g.material('Metal | brushed aluminum',(.57,.64,.69),.85,.26),
        'chrome':g.material('Metal | oleo chrome',(.72,.77,.81),.97,.14),
        'dark':g.material('Engine | graphite',(.033,.045,.054),.58,.34),
        'rubber':g.material('Tires | charcoal rubber',(.013,.017,.022),0,.72),
        'well':g.material('Wheel wells | interior',(.20,.23,.19),.1,.7),
        'red':g.material('Navigation | port red',(.65,.008,.015),.1,.2,2),
        'green':g.material('Navigation | starboard green',(.01,.40,.07),.1,.2,2),
        'lamp':g.material('Landing lamps',(.85,.92,1),.3,.14,2),
    }
    col=g.collection('01_Fuselage',root);g.use(col)
    xs=sorted(set([p[0] for p in P]+[i*32.18/240 for i in range(241)]))
    fus=g.loft('Fuselage | continuous quad loft',[[surface(x,2*pi*j/128) for j in range(128)] for x in xs],mats['white'])
    fus['construction']='Closed quad-ring loft. Surface-mounted window inserts; no cabin apertures.'
    fus['length_m']=32.18
    # Cylindrical UV seed with a bottom seam.
    uv=fus.data.uv_layers.active
    for face in fus.data.polygons:
        for li in face.loop_indices:
            vi=fus.data.loops[li].vertex_index
            ring,j=divmod(vi,128)
            uv.data[li].uv=(xs[ring]/32.18,j/128)
    # Gently raised, blended wing/body fairing, largely buried inside fuselage.
    fair=[]
    for x,ry,rz,z in [(10.5,.02,.02,1.8),(11.3,1.35,.32,1.9),(12.0,1.88,.48,1.90),
        (15.0,2.12,.57,1.83),(18.5,1.98,.52,1.82),(20.0,1.48,.39,1.80),(21.0,.02,.02,1.80)]:
        fair.append([(x,ry*cos(a*2*pi/64),z+rz*sin(a*2*pi/64)) for a in range(64)])
    g.loft('Wing-body fairing',fair,mats['wing'])
    # APU exhaust, with visible recessed throat.
    g.cylinder('APU exhaust', (31.95,0,3.96),(32.20,0,3.96),.105,mats['metal'],r2=.075)
    g.cylinder('APU dark throat',(32.202,0,3.96),(32.208,0,3.96),.055,mats['dark'])

    g.use(g.collection('02_Windows_Doors_Panels',root))
    for side in [-1,1]:
        tag='L' if side<0 else 'R'
        # Boeing side drawing has one overwing escape opening per side.
        centers=[5.95+i*.508 for i in range(44)]
        centers=[x for x in centers if abs(x-14.65)>.39 and x<26.95]
        for i,x in enumerate(centers):
            outline=g.rounded_rect(x,3.65,.275,.405,.085,5)
            side_glazing(f'Window_{tag}_{i+1:02}',outline,side,mats['glass'])
            g.curve(f'Window seal_{tag}_{i+1:02}',[sidepoint(a,b,side,.021) for a,b in outline],mats['metal'],.009,True)
        for label,x,z,w,h in [('Forward door',4.63,3.52,.85,1.83),('Aft door',27.55,3.76,.82,1.82),('Overwing exit',14.65,3.63,.51,.96)]:
            outline=g.rounded_rect(x,z,w,h,.11,8)
            g.curve(f'{label}_{tag}',[sidepoint(a,b,side,.014) for a,b in outline],mats['seam'],.008,True)
            dz=z+.31 if label!='Overwing exit' else z+.17
            side_glazing(f'{label} porthole_{tag}',g.rounded_rect(x,dz,.17,.21,.065,5),side,mats['glass'])
            g.curve(f'{label} handle_{tag}',[sidepoint(x-.12,z-.16,side,.021),sidepoint(x+.12,z-.16,side,.021)],mats['metal'],.018)
            for dx in [-.30,.30]:
                g.curve(f'{label} hinge_{tag}_{dx}',[sidepoint(x+dx,z-.62,side,.018),sidepoint(x+dx,z-.47,side,.018)],mats['metal'],.014)
            if label!='Overwing exit':
                y=sidepoint(x,z+.87,side,.027)[1]
                # Text faces outwards on both sides, following local side orientation.
                rot=(pi/2,0,0) if side<0 else (pi/2,0,pi)
                g.text(f'Exit stencil_{label}_{tag}','EXIT',(x,y,z+.73),.06,mats['seam'],rot)
        if side==1:
            for label,x,z,w,h in [('Forward cargo',8.5,1.82,1.22,.89),('Aft cargo',22.25,1.90,1.22,.84)]:
                g.curve(label,[sidepoint(a,b,side,.015) for a,b in g.rounded_rect(x,z,w,h,.07,8)],mats['seam'],.008,True)
                g.curve(label+' handle',[sidepoint(x-.13,z+.22,side,.028),sidepoint(x+.13,z+.22,side,.028)],mats['metal'],.018)
        # Six principal cockpit panes, plus Classic eyebrow windows.
        polygons=[[(1.95,1.53),(2.07,1.03),(2.72,.94),(2.69,1.53)],
                  [(2.12,1.00),(3.00,.45),(3.30,.73),(2.78,.92)],
                  [(3.06,.43),(3.58,.34),(3.84,.65),(3.36,.72)]]
        eyebrows=[[(2.85,1.24),(2.88,1.48),(3.23,1.43),(3.17,1.17)],
                  [(3.12,.98),(3.24,1.17),(3.55,1.02),(3.45,.85)]]
        for i,poly in enumerate(polygons+eyebrows):
            points=[]
            for k in range(len(poly)):
                a,b=poly[k],poly[(k+1)%len(poly)]
                for t in [j/16 for j in range(16)]:
                    x=a[0]+t*(b[0]-a[0]);theta=a[1]+t*(b[1]-a[1])
                    p=surface(x,theta,.027);points.append((p[0],side*abs(p[1]),p[2]))
            # Dense surface-domain quads stay above the convex nose loft.
            verts=[];n=20
            for j in range(n+1):
                v=j/n
                for k in range(n+1):
                    u=k/n
                    weights=[(1-u)*(1-v),u*(1-v),u*v,(1-u)*v]
                    x=sum(w*p[0] for w,p in zip(weights,poly))
                    theta=sum(w*p[1] for w,p in zip(weights,poly))
                    p=surface(x,theta,.024);verts.append((p[0],side*abs(p[1]),p[2]))
            faces=[(j*(n+1)+k,j*(n+1)+k+1,(j+1)*(n+1)+k+1,(j+1)*(n+1)+k) for j in range(n) for k in range(n)]
            g.mesh(f'Cockpit pane_{tag}_{i+1}',verts,faces,mats['glass'])
            g.curve(f'Cockpit frame_{tag}_{i+1}',points,mats['seam'],.010,True)
        for j,(x,theta) in enumerate([(2.12,1.19),(2.65,.74)]):
            pts=[surface(x,theta,.042),surface(x+.21,theta+.15,.042),surface(x+.42,theta+.18,.042)]
            g.curve(f'Wiper_{tag}_{j}',[(p[0],side*abs(p[1]),p[2]) for p in pts],mats['dark'],.012)
        # Pitot probes and static ports.
        for i,x in enumerate([2.40,3.08]):
            a=sidepoint(x,2.65,side,.02)
            b=(x-.12,a[1]+side*.22,2.65)
            g.cylinder(f'Pitot base_{tag}_{i}',a,b,.022,mats['metal'])
            g.cylinder(f'Pitot tube_{tag}_{i}',b,(x-.40,b[1],b[2]),.012,mats['metal'])
        for x in [3.7,4.1]:
            p=sidepoint(x,2.85,side,.017)
            g.sphere(f'Static port_{tag}_{x}',p,(.024,.009,.024),mats['seam'],16,8)
    # Restrained skin joints; no exaggerated rivet grid.
    for i,x in enumerate([1.03,4.3,7.4,10.5,13.6,17.3,20.5,23.6,26.6,29.4]):
        g.curve(f'Skin circumferential joint_{i:02}',[surface(x,2*pi*j/160,.006) for j in range(160)],mats['seam'],.0025,True)
    for theta in [-.78,pi+.78]:
        g.curve(f'Lower longitudinal seam_{theta}',[surface(4.5+j*25/160,theta,.006) for j in range(161)],mats['seam'],.0023)
    build_wings(root,mats,cfg)
    build_tail(root,mats,cfg)
    build_engines(root,mats,cfg)
    build_gear(root,mats,cfg)
    g.use(g.collection('07_Antennas_Lights',root))
    for i,(x,h,l) in enumerate([(8.5,.35,.50),(21.4,.30,.46),(25.0,.21,.40)]):
        z=profile(x)[2]
        v=[(x,-.025,z),(x+l,-.025,z),(x+l-.06,-.012,z+h),(x+.19,-.012,z+h*.93)]
        g.loft(f'Dorsal VHF antenna_{i}',[v,[(a,-b,c) for a,b,c in v]],mats['white'])
    for i,x in enumerate([9.1,20.4]):
        z=profile(x)[1]
        v=[(x,-.02,z),(x+.40,-.02,z),(x+.35,-.012,z-.25),(x+.17,-.012,z-.22)]
        g.loft(f'Ventral antenna_{i}',[v,[(a,-b,c) for a,b,c in v]],mats['white'])
    for x,z in [(13.7,5.19),(15.1,1.13)]:
        g.sphere('Anti-collision beacon',(x,0,z),(.105,.105,.075),mats['red'])
    return mats

WING=[(1.42,11.60,6.80,1.93,.135),(5.50,14.18,4.20,2.18,.115),(14.44,19.37,1.57,3.06,.095)]
TAIL=[(.5,26.90,5.03,3.94,.09),(6.35,31.05,2.35,4.98,.075)]

def section(stations,y):
    for i in range(len(stations)-1):
        a,b=stations[i:i+2]
        if a[0]<=y<=b[0]:
            t=(y-a[0])/(b[0]-a[0])
            return [a[k]+t*(b[k]-a[k]) for k in range(1,5)]
    return list(stations[0][1:] if y<stations[0][0] else stations[-1][1:])

def foil(stations,y,u,sign=1):
    le,ch,z,th=section(stations,y)
    thick=5*th*ch*(.2969*sqrt(max(u,0))-.1260*u-.3516*u*u+.2843*u**3-.1036*u**4)
    camber=.011*ch*sin(pi*u)
    return (le+ch*u,y,z+camber+sign*max(.004,thick))

def wing_part(name,side,ys,u0,u1,stations,mat):
    rings=[]
    for y in ys:
        us=[u0+(u1-u0)*(1-cos(pi*i/28))/2 for i in range(29)]
        ring=[]
        for sign, seq in [(1,us),(-1,list(reversed(us)))]:
            for u in seq:
                x,yp,z=foil(stations,y,u,sign)
                ring.append((x,side*yp,z))
        rings.append(ring)
    return g.loft(name,rings,mat)

def wing_patch(name,side,y0,y1,u0,u1,stations,mat,offset=.012):
    verts=[]
    for j in range(9):
        y=y0+(y1-y0)*j/8
        for i in range(13):
            u=u0+(u1-u0)*i/12
            x,yp,z=foil(stations,y,u)
            verts.append((x,side*yp,z+offset))
    faces=[(j*13+i,j*13+i+1,(j+1)*13+i+1,(j+1)*13+i) for j in range(8) for i in range(12)]
    return g.mesh(name,verts,faces,mat)

def build_wings(root,m,cfg):
    g.use(g.collection('03_Wings_ControlSurfaces',root))
    for side in [-1,1]:
        tag='L' if side<0 else 'R'
        ys=[1.42+i*(14.44-1.42)/64 for i in range(65)]+[5.5]
        ys=sorted(set(ys))
        wing_part('Wing main box_'+tag,side,ys,.145,.725,WING,m['wing'])
        for i,(ya,yb) in enumerate([(1.42,3.4),(3.42,5.49),(5.51,8.0),(8.02,10.7),(10.72,14.44)]):
            wing_part(f'Leading edge slat_{tag}_{i}',side,[ya+(yb-ya)*j/14 for j in range(15)],0,.142,WING,m['metal'])
        for i,(ya,yb) in enumerate([(1.42,5.49),(5.51,8.49),(8.51,10.70),(10.72,14.44)]):
            label='Aileron' if i==3 else 'Trailing flap'
            wing_part(f'{label}_{tag}_{i}',side,[ya+(yb-ya)*j/20 for j in range(21)],.730,1,WING,m['wing'])
        wing_patch('Coroguard walkway_'+tag,side,2.05,13.95,.24,.64,WING,m['panel'])
        for i,(ya,yb) in enumerate([(2.25,3.4),(3.45,4.6),(5.8,6.9),(6.95,8.0),(8.05,9.1)]):
            wing_patch(f'Spoiler panel_{tag}_{i}',side,ya,yb,.585,.718,WING,m['wing'],.021)
            pts=[]
            for y,u in [(ya,.585),(yb,.585),(yb,.718),(ya,.718),(ya,.585)]:
                x,yp,z=foil(WING,y,u);pts.append((x,side*yp,z+.024))
            g.curve(f'Spoiler hinge gap_{tag}_{i}',pts,m['seam'],.004)
        for i,y in enumerate([3.7,6.5,10.1]):
            le,ch,z,th=section(WING,y)
            x=le+ch*.84
            rings=[]
            for dx,r in [(-1.25,.025),(-.65,.17),(0,.21),(.75,.16),(1.50,.025)]:
                rings.append([(x+dx,side*y+r*cos(2*pi*k/32),z-.38+r*1.1*sin(2*pi*k/32)) for k in range(32)])
            g.loft(f'Flap track fairing_{tag}_{i}',rings,m['wing'])
        for y in [5.5,8.5,11.0,13.1]:
            pts=[]
            for j in range(30):
                x,yp,z=foil(WING,y,.16+.55*j/29);pts.append((x,side*yp,z+.014))
            g.curve(f'Wing chord joint_{tag}_{y}',pts,m['seam'],.003)
        for y in [11.8,12.7,13.6,14.2]:
            x,yp,z=foil(WING,y,.985)
            g.cylinder(f'Static wick_{tag}_{y}',(x,side*yp,z),(x+.28,side*yp,z),.004,m['dark'],12)
        g.sphere('Navigation lamp_'+tag,(19.58,side*14.41,3.08),(.10,.025,.045),m['red' if side<0 else 'green'])
        g.sphere('Wingtip strobe_'+tag,(20.50,side*14.42,3.07),(.10,.023,.040),m['lamp'])
        g.sphere('Landing light_'+tag,(12.3,side*2.70,2.04),(.11,.14,.12),m['lamp'])

def build_tail(root,m,cfg):
    g.use(g.collection('04_Empennage',root))
    for side in [-1,1]:
        tag='L' if side<0 else 'R'
        ys=[.5+(6.35-.5)*j/40 for j in range(41)]
        wing_part('Horizontal stabilizer_'+tag,side,ys,0,.70,TAIL,m['wing'])
        wing_part('Elevator_'+tag,side,ys,.705,1,TAIL,m['wing'])
        for y in [4.7,5.5,6.1]:
            x,yp,z=foil(TAIL,y,1)
            g.cylinder(f'Tail wick_{tag}_{y}',(x,side*yp,z),(min(33.39,x+.22),side*yp,z),.004,m['dark'],12)
    # Fin chord stations include the long Classic dorsal fillet.
    stations=[(4.72,22.6,31.5,.37),(5.05,24.0,31.6,.34),(6.50,27.10,31.95,.25),
              (10.87,30.70,32.54,.095),(11.13,31.05,32.60,.055)]
    def vpart(name,u0,u1,mat):
        rings=[]
        for z,le,te,t in stations:
            us=[u0+(u1-u0)*(1-cos(pi*i/24))/2 for i in range(25)]
            ring=[]
            for side,seq in [(1,us),(-1,list(reversed(us)))]:
                for u in seq:
                    thick=t*sin(pi*max(.0001,min(.9999,u)))**.7+.004
                    ring.append((le+(te-le)*u,side*thick,z))
            rings.append(ring)
        return g.loft(name,rings,mat)
    vpart('Vertical fin with dorsal fillet',0,.73,m['white'])
    vpart('Rudder',.735,1,m['wing'])
    for side in [-1,1]:
        g.curve(f'Rudder trim tab_{side}',[(32.23,side*.042,7.8),(32.42,side*.038,9.1),(32.16,side*.092,9.1),(31.89,side*.10,7.8)],m['seam'],.004,True)
    g.sphere('Tail position light',(32.60,0,10.8),(.038,.035,.055),m['lamp'])

def build_engines(root,m,cfg):
    g.use(g.collection('05_Engines_CFM56_3',root))
    for side in [-1,1]:
        tag='L' if side<0 else 'R'; y=side*4.83; z=1.60
        def ring(x,r,flatten=True):
            points=[]
            for j in range(96):
                a=2*pi*j/96
                yy=r*cos(a)
                zz=r*sin(a)
                if flatten:
                    # Soft rectangular lower quadrant, the CFM56-3 installation signature.
                    zz=max(-r*.865,zz)
                    yy*=1.025
                points.append((x,y+yy,z+zz))
            return points
        # Outer skin turns through the rounded inlet lip into an actual recessed duct.
        spec=[(14.48,.83),(14.20,1.00),(13.80,1.17),(12.90,1.24),(11.50,1.22),
              (11.10,1.20),(11.00,1.16),(11.02,1.09),(11.13,1.035),(11.50,.95),(11.94,.875)]
        nac=g.loft('CFM56-3 nacelle_'+tag,[ring(x,r) for x,r in spec],m['white'],caps=False)
        nac.data.materials.append(m['metal']);nac.data.materials.append(m['dark'])
        for p in nac.data.polygons:
            band=p.index//96
            p.material_index=1 if 4<=band<=7 else (2 if band>=8 else 0)
        # Rear bypass nozzle, dark compressor backing, central exhaust and plug.
        g.loft('Bypass nozzle_'+tag,[ring(14.4,.835),ring(14.95,.72),ring(14.98,.64),ring(14.42,.73)],m['metal'],caps=False)
        g.cylinder('Engine core_'+tag,(13.7,y,z),(15.0,y,z),.54,m['dark'],64,r2=.44)
        g.cylinder('Exhaust cone_'+tag,(15.0,y,z),(15.65,y,z),.43,m['metal'],64,r2=.12)
        g.cylinder('Turbine dark exit_'+tag,(15.65,y,z),(15.68,y,z),.12,m['dark'],48)
        g.cylinder('Fan dark backing_'+tag,(12.04,y,z),(12.08,y,z),.88,m['dark'],96)
        for i in range(38):
            a=i*2*pi/38
            verts=[]
            for r,twist,x in [(.22,0,11.86),(.45,.10,11.91),(.70,.19,11.98),(.855,.22,12.01)]:
                for off in [-.026,.044]:
                    ang=a+twist+off
                    verts.append((x,y+r*cos(ang),z+r*sin(ang)))
            blade=g.mesh(f'Fan blade_{tag}_{i:02}',verts,[(0,1,3,2),(2,3,5,4),(4,5,7,6)],m['metal'])
            mod=blade.modifiers.new('Blade thickness','SOLIDIFY');mod.thickness=.009
        g.cylinder('Fan spinner_'+tag,(11.35,y,z),(12.05,y,z),.015,m['metal'],64,r2=.245)
        spiral=[]
        for j in range(90):
            t=j/89;r=.017+.18*t;a=t*3*pi
            spiral.append((11.35+(r/.245)*.70-.006,y+r*cos(a),z+r*sin(a)))
        g.curve('Spinner spiral_'+tag,spiral,m['white'],.009)
        # Pylon grows aft/up to the wing underside, with a narrow leading blade.
        v=[(11.8,y-.10,2.63),(13.8,y-.15,3.00),(15.05,y-.20,2.72),(15.5,y-.12,2.04),(13.7,y-.20,2.38)]
        g.loft('Engine pylon_'+tag,[v,[(a,2*y-b,c) for a,b,c in v]],m['wing'])
        for i,x in enumerate([11.46,13.12,13.75]):
            r=g.interp([(11.46,1.22),(13.12,1.23),(13.75,1.18)],x)
            g.curve(f'Cowl circumferential seam_{tag}_{i}',ring(x,r+.004),m['seam'],.005,True)
        for a in [.15,pi-.15]:
            pts=[]
            for j in range(40):
                x=11.5+j*2.1/39;r=1.22
                pts.append((x,y+1.025*r*cos(a),z+r*sin(a)))
            g.curve(f'Cowl longitudinal seam_{tag}_{a}',pts,m['seam'],.004)
        for x in [11.75,12.9,13.5]:
            g.cube(f'Cowl latch_{tag}_{x}',(x,y+side*1.25,1.5),(.10,.012,.035),m['metal'],.005)

def tire(name,x,y,z,r,width,m):
    rings=[]
    # Revolved tire cross section around lateral axle, closed through inner bead.
    profile=[(-width*.5,r*.58),(-width*.53,r*.83),(-width*.40,r*.97),(-width*.27,r),
             (width*.27,r),(width*.40,r*.97),(width*.53,r*.83),(width*.5,r*.58)]
    n=64
    for dy,rr in profile:
        rings.append([(x+rr*cos(j*2*pi/n),y+dy,z+rr*sin(j*2*pi/n)) for j in range(n)])
    rings.append(rings[0])
    obj=g.loft(name,rings,m['rubber'],False)
    for side in [-1,1]:
        yy=y+side*width*.49
        g.cylinder(name+' hub', (x,yy-side*.07,z),(x,yy,z),r*.54,m['metal'],48)
        g.cylinder(name+' axle cap',(x,yy,z),(x,yy+side*.025,z),r*.24,m['wing'],32)
        for i in range(8):
            a=2*pi*i/8
            g.cylinder(name+f' hub bolt_{side}_{i}',(x+r*.36*cos(a),yy,z+r*.36*sin(a)),
                (x+r*.36*cos(a),yy+side*.008,z+r*.36*sin(a)),r*.035,m['dark'],8)
    for dy in [-width*.18,0,width*.18]:
        g.curve(name+f' tread_{dy}',[(x+(r+.001)*cos(j*2*pi/96),y+dy,z+(r+.001)*sin(j*2*pi/96)) for j in range(96)],m['seam'],.006,True)
    return obj

def build_gear(root,m,cfg):
    g.use(g.collection('06_LandingGear',root))
    for side in [-1,1]:
        tag='L' if side<0 else 'R';x=16.46;y=side*2.615
        for d in [-.31,.31]:
            tire(f'Main tire_{tag}_{d}',x,y+d,.565,.565,.43,m)
        g.cylinder('Main axle_'+tag,(x,y-.60,.565),(x,y+.60,.565),.105,m['metal'])
        g.cylinder('Main oleo chrome_'+tag,(x,y,.57),(16.35,y,1.37),.093,m['chrome'])
        g.cylinder('Main oleo sleeve_'+tag,(16.35,y,1.18),(16.09,y,2.17),.14,m['wing'])
        g.cylinder('Main drag brace_'+tag,(15.12,y,1.91),(16.40,y,1.00),.063,m['metal'])
        g.cylinder('Main side stay_'+tag,(16.16,side*1.52,1.48),(16.35,y,1.21),.068,m['metal'])
        g.curve('Main hydraulic hose_'+tag,[(16.15,y+.15,2.07),(16.30,y+.18,1.32),(16.50,y+.20,.82),(16.52,y+.31,.64)],m['rubber'],.018)
        g.curve('Main torque scissors_'+tag,[(16.42,y,1.20),(16.67,y,.98),(16.48,y,.77)],m['metal'],.042)
        door=g.cube('Main gear leg door_'+tag,(16.16,y+side*.22,1.60),(.67,.055,1.16),m['wing'],.025)
        door.rotation_euler[1]=-.16
        g.sphere('Main wheel well recess_'+tag,(16.95,side*1.09,1.13),(.77,.64,.035),m['dark'])
    x=4.01
    for y in [-.20,.20]:tire(f'Nose tire_{y}',x,y,.34,.34,.21,m)
    g.cylinder('Nose axle',(x,-.36,.34),(x,.36,.34),.065,m['metal'])
    g.cylinder('Nose oleo',(x,0,.42),(3.90,0,1.04),.065,m['chrome'])
    g.cylinder('Nose upper strut',(3.90,0,.88),(3.81,0,1.62),.105,m['wing'])
    g.cylinder('Nose drag brace',(4.60,0,1.34),(4.00,0,.78),.043,m['metal'])
    g.curve('Nose torque scissors',[(3.96,-.10,1.02),(4.17,-.10,.78),(4.01,-.10,.56)],m['metal'],.024)
    for side in [-1,1]:
        g.cube('Nose gear door_'+str(side),(3.72,side*.39,1.00),(1.25,.04,.40),m['white'],.012)
        g.cylinder('Nose fork_'+str(side),(4.0,side*.085,.70),(4.01,side*.085,.34),.044,m['metal'])
    g.cube('Nose well shadow',(3.72,0,1.24),(1.28,.73,.035),m['dark'],.08)

# ECS overview — Phase 1

The existing final file, `models/Boeing_737-300_Helios_Livery.blend`, contains
the dedicated scene **08 | ECS_OVERVIEW**. The existing `run_all.py` generates
it as its final stage, after the standalone CFM56 engine. No manual second
script or separate project is required.

This scene prepares a whole-aircraft systems presentation: one reused Boeing
737-300 exterior, two installed instances of the existing CFM56 engine,
transparent shell and wireframe display, and dedicated cameras and lights.
The aircraft, airport, cabin, flight deck, pressurization panel and standalone
engine retain their separate scenes and source assets.

## Open and inspect

Choose **08 | ECS_OVERVIEW** in Blender's scene selector, or use
**N > ECS Overview > Inspect overview**. The sidebar selects
**CTRL_ECS_OVERVIEW** and opens the wide camera. F12 renders the selected
overview camera.

| Sidebar button | Camera | Purpose |
| --- | --- | --- |
| Wide | `CAM_OVERVIEW_WIDE` | Full aircraft and both engines |
| 3Q | `CAM_OVERVIEW_3Q` | Cinematic three-quarter framing |
| Side | `CAM_OVERVIEW_SIDE` | Technical side view |

An additional **CAM_OVERVIEW_ENGINE_STUDY** camera frames the left installed
engine and pylon for closer inspection. All four cameras are static and can
be animated in later phases. The three required cameras frame the full
aircraft; the side view naturally overlaps the two engines in projection.

The inspection button uses a 0.02–500 m viewport clipping range and hides
floor and relationship overlays. Use Material Preview or Rendered shading
to inspect the transparent-shell materials; Solid shading does not reproduce
the final transparent render.

If script auto-execution is disabled and the sidebar is missing, open
embedded **ECS_OVERVIEW_CONTROL.py** in the Text Editor and click **Run Script**.
Re-running the sidebar script safely replaces its own registered classes.
The optional sidebar adds convenient buttons; the cameras and native custom
properties remain available without it.

## Presentation controls

**CTRL_ECS_OVERVIEW** holds the aircraft presentation state:

| Property | Effect |
| --- | --- |
| `SHOW_SHELL` | Show the overview's transparent aircraft shell |
| `SHOW_WIREFRAME` | Show the overview's wireframe presentation |
| `WIREFRAME_THICKNESS` | Wire width, 1–25 mm; default 5 mm |
| `WIREFRAME_COLOR` | RGB color picker for the overview wire material |

Enable **Wireframe**, then adjust **Wireframe thickness** and **Wireframe color**
in the existing sidebar. Thickness drives all six display wireframe modifiers;
color drives their private material's base color, emission color and viewport
swatch. These controls affect the wire layer. The transparent shell's windows
and panel outlines keep their own presentation materials.

The controls use native Blender drivers, with no update handler or custom
driver function. They work with script auto-execution disabled. Save the file
to retain edits; updating only the overview also retains its saved wire width
and color. A full generated project starts with the documented defaults.

The installed engine objects are **ENGINE_LEFT_OVERVIEW** and
**ENGINE_RIGHT_OVERVIEW**. Both instance one overview-owned engine template.
Its controller, **ECS ENG | CTRL_ENGINE**, provides the sidebar's engine
controls:

| Property | Effect |
| --- | --- |
| `CUTAWAY_MODE` | Reversibly open the engine's presentation shell |
| `SHOW_NACELLE` | Show the outer engine shell |
| `SHOW_INTERNALS` | Show the fan and mechanical core |
| `N1_SPEED` | Constant RPM for the low-pressure spool |
| `N2_SPEED` | Constant RPM for the high-pressure spool |

These settings are shared by the two installed instances. N1 and N2 can run
at different constant speeds; changing either affects both installed engines.
Set both speeds to zero for a still engine. Constant-speed timeline playback
requires no RPM bake. Phase 1 does not provide an RPM-ramp editing or baking
workflow; use constant RPM values in this overview.

The template controller is independent of **CTRL_ENGINE** in
**07 | CFM56_ENGINE**. Overview controls do not change the standalone engine's
presentation or animation state.

## Asset reuse and preservation

The aircraft comes from **B737_300_EXTERIOR**. Its overview objects reference
the existing mesh data and apply materials through overview-only object
material slots. Sparse wireframe presentation uses dedicated display objects.
The original exterior geometry and materials remain intact. Cabin furniture,
cockpit interior geometry and livery text/decals are omitted from this scene
to keep the future interior presentation space clear.

The source aircraft's older engine geometry is omitted from the overview;
its two pylons are reused as presentation copies. The existing HEL-5 CFM56
asset supplies both installed engines. Its geometry is copied into a fully
detached overview template, preserving shared blade meshes through cached
mesh copies. Private material copies protect the standalone asset and keep
its subsequent rebuilds independent. Both installed collection instances use
that same template; the engine has not been remodeled.

The overview template includes existing mechanical and bleed hardware from
the source asset. Standalone airflow overlays, labels, cameras and lights are
excluded. The bleed hardware receives the mirrored installed presentation
described below; the original engine core and standalone asset stay intact.

### Installed bleed outlets

The complete visible bleed system has the same shape on both engines, mirrored
so both face the fuselage. Each installed engine has its own overview-only
bleed root under **ENGINES_OVERVIEW**. The right root uses the original local
orientation; the left root reflects local Y. Both use the same existing bleed
hardware geometry and the same short final outlet shape. Valve motion follows
the shared overview engine control through the reflected parent.

The copied bleed hardware in the shared engine template is hidden. Visible
installation copies reuse its detached mesh, curve and material data. The
standalone originals remain untouched. New final routes replace the copied
**BLEED_OUTLET_STUB** and **BLEED_OUTLET_FLANGE**. Each route joins the valve
exit, rises on the inboard side below the wing, then enters the engine pylon.
The continuous internal section runs aft through the pylon into the wing's
pneumatic duct volume. Its terminal flange is inside the wing. The pipe and
flange remain below the local upper wing skin; there is no upward external
outlet above the wing. The installed bleed presentation follows **Show internals**.

**ECS BLEED | LEFT OUTLET** and **ECS BLEED | RIGHT OUTLET** are non-rendered
connection guides inside the wing whose local +Z axis points downstream.
**ECS BLEED | LEFT PYLON ENTRY** and **ECS BLEED | RIGHT PYLON ENTRY** mark
the transition into the pylon. Each bleed root is parented to its installed
engine. The transparent presentation can reveal the concealed internal run;
the visible external portion ends where it enters the pylon. This bounded
lead-in does not add a precooler or a complete aircraft airflow network.
This is an installed presentation correction, not certified pipe routing.

### Engine mounting

Coordinates are metres: +X runs from nose toward tail, +Y is starboard and
+Z is up. The installed engine roots retain the source aircraft's positions:

- Left: **(11.0, -4.83, 1.60)**.
- Right: **(11.0, 4.83, 1.60)**.
- Both use zero rotation and unit scale; their intakes face -X.

The HEL-5 engine is smaller than the older stylized nacelle. To connect it
visually while retaining its intended scale, each overview pylon uses a
private mesh copy. Only the lower leading vertices (indices 0 and 5) move
to Z=2.40, and the lower attachment vertices (indices 4 and 9) move to Z=1.97.
The remaining vertices and all X/Y coordinates stay unchanged.

An audit of 1,001 rays against the actual source nacelle triangles measured
continuous pylon overlap of **0.0122–0.0924 m** along the adapted lower edge.
The original aircraft pylons remain unchanged. This is a visual installation
for the overview, not an engineering reconstruction of certified mounts.

## Scope and future work

The overview provides a clean base for future documentary camera movement
from outside the aircraft toward an engine and through the fuselage.
Any non-rendered guide empties or camera-planning helpers identify approximate
future areas only; they are not system components or an animated camera route.

Phase 1 does not create precoolers, packs, a mix manifold, cabin duct routing,
outflow or relief valves, or a connected airflow network. It does not add an
airport animation or modify the pressurization-panel module.

## Build and repeatability

Run the existing **run_all.py** workflow. The ECS overview stage reuses the
aircraft and engine already available in the final project, generates its
owned overview content, and saves the same final `.blend` file.

Rebuilding the overview replaces only its owned resources. It preserves
unrelated scenes and source assets and retains the exact scene, instance,
controller and camera names; repeated runs do not accumulate `.001` copies.
Save manual customizations separately before regenerating generated content.

The overview builder writes a temporary candidate, checks source preservation
and repeated-build inventory, reopens the candidate and exercises both engine
instances and shell controls before publishing the final file. It backs up the
previous final file under `reports/backups/ecs_overview_<timestamp>/`.
The saved report is `reports/ecs_overview_verification.json`.

For a preview, choose the overview scene and one of its cameras, then press
**F12**. The sidebar's **Engine cutaway** option exposes the engine internals.
Normal generation requires only `run_all.py`; rendering previews is optional.

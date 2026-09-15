# HEL-5 — standalone CFM56-3 engine

The existing `run_all.py` builds the engine after the pressurization panel and
saves it into `models/Boeing_737-300_Helios_Livery.blend`. Scene:
**07 | CFM56_ENGINE**. Root collection: **CFM56_3_ENGINE**.
The engine is independent of the airport, aircraft and panel.

## Inspection and controls

Choose scene 07, or **N > CFM56 > Inspect engine**. F12 renders the selected
engine camera. Cameras include technical side, three-quarter, fan and bleed detail.
If the sidebar is absent, run embedded `CFM56_ENGINE_CONTROL.py` from the Text
Editor. The sidebar follows the panel's optional embedded UI pattern. Native
drivers and Object > Custom Properties work even with script auto-execution disabled.

Select **CTRL_ENGINE**. All dimensions are metres; +X points aft, Y=Z=0 is
the precise engine centreline. ROT_N1 and ROT_N2 are independent siblings.

| Property | Effect |
| --- | --- |
| N1_SPEED | LP spool RPM: fan, booster, LP shaft and four LPT rotors |
| N2_SPEED | HP spool RPM: nine HPC rotors, HP shaft and one HPT rotor |
| BLEED_VALVE_OPEN | 0 closed to 1 open; butterfly and external indicator rotate 90 degrees |
| BLEED_SOURCE | 0 selects stage 5 primary, 1 selects stage 9 high pressure airflow |
| CUTAWAY_MODE | Reversibly hides near-side shell and casing quadrants |
| SHOW_NACELLE | Outer shell visibility |
| SHOW_INTERNALS | Mechanical core and fan visibility |
| SHOW_AIRFLOW | Separate emissive paths and travelling arrows |
| SHOW_LABELS | Optional technical labels |

Default speeds are 12 and 30 RPM for readable slow motion. Set both to zero for
engine off. Constant RPM uses native frame drivers. Rotation is clockwise looking
forward from the exhaust. Use slow speeds for close-ups; high RPM can alias at
ordinary frame rates.

### Starting and stopping shots

1. Set the engine scene frame rate and shot range.
2. Keyframe N2_SPEED first, then N1_SPEED, using Object > Custom Properties or
   the sidebar. Keyframe BLEED_VALVE_OPEN and the presentation toggles as needed.
3. Click **Bake RPM animation** after editing RPM keys. This integrates evaluated
   speed curves at four samples per frame and stores native phase-correction
   curves. Re-bake after changing RPM curves, shot range or frame rate.
4. Save. Playback, scrubbing and rendering the baked shot require no handlers,
   external dependencies or script auto-execution. N1_PHASE / N2_PHASE are generated
   corrections; do not edit them manually. Constant-speed shots need no bake.

This avoids the acceleration discontinuities produced by multiplying the current
animated RPM by the frame number. Integration uses numerical trapezoids; extremely
short speed changes may require a larger `samples` argument to `bake_rpm`.
Use the baked shot range when rendering. Re-bake a longer range before extending it.

## Architecture and scope

Construction order is centreline/stations, envelope and shafts, fan and stages,
casings, bleed system, controls, flow, materials and animation verification.
The fan has 38 linked cambered blade instances and midspan snubbers. Other blade
rows share one mesh per row. There are 3 booster, 9 HPC, 1 HPT and 4 LPT rotor
rows, with separate stationary vane rows. The combustor is an annular static
assembly with liners, injectors and cooling-hole details.

The 1.524 m fan and flattened Classic nacelle establish the intended visual
proportions. The approximately 3.4 m illustrated envelope, section stations,
airfoil profiles, vane counts, ancillary hardware and duct routing are artistic
approximations. The supplied infographic is visual guidance, not a dimensioned
engineering drawing. This is an animation and documentary asset, not maintenance
CAD, a thermodynamic simulation or a validated model of pneumatic regulation.

The supplied illustration's N1/N2 brackets and dimensions are not copied as
technical truth. Mechanical grouping follows the two-spool architecture above.
The engine uses a single annular combustor and separate bypass exhaust around
the core. The stage-9 line is selectable high-pressure bleed; no downstream
precooler, packs, cabin or aircraft connection is included.

`BLEED_OUTLET_TO_AIRCRAFT` is an Empty at **(2.70, -0.64, -0.72)**.
Its local +Z axis points aft (+X). The outlet stub ends there; the nominal visual
connection diameter is 0.094 m. The butterfly is visible through the removable
valve housing and has a visible external position indicator. Flow overlays sit
slightly outside the opaque bleed pipes for inspection and stop when the valve
closes. Both source pipes remain physical geometry regardless of selected flow.

## Sources

- User reference: `turbofan_engine.png` (visual language and bleed layout).
- [Boeing CFM56-3 AMM 72-00-00, engine specifications, hosted by Ariana](https://www.flyariana.com/content/articleasset?id=5b541807-dc09-480d-987e-49b073b23096):
  two spools, compressor/turbine stage arrangement, annular combustor and rotation direction.
- [CFM International: Project TECH56](https://www.cfmaeroengines.com/press-articles/cfm-continues-to-mature-project-tech56-technology):
  CFM56 nine-stage high-pressure compressor.

## Build and verification

Normal use remains opening `run_all.py` in Blender and clicking Run Script.
For automated validation the same orchestrator also accepts Blender background
execution: `blender --background --python-exit-code 1 --python run_all.py`.
All stages run in the same order. Existing model files are backed up first.

`build_cfm56_engine.py` follows the pressurization module's candidate-file pattern:
snapshot unrelated content, build engine, compare preservation, rebuild and check
idempotence, save a candidate, reopen with native driver checks, then save the same
final output. The generator refuses unowned name collisions or shared engine
objects. It removes only tagged engine resources; existing scenes are retained.

Reports: `reports/cfm56_engine_verification.json`; log: `logs/cfm56_engine.log`.
Engine previews are under `renders/cfm56/`. The full workflow still regenerates
upstream aircraft/airport content as before; manual edits are preserved in the
existing timestamped backups. The engine stage itself preserves unrelated data.

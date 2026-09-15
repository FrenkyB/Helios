# ECS overview — Phase 2

Run `run_all.py` in Blender's Text Editor. Its final stage extends the existing
`08 | ECS_OVERVIEW` scene and saves the same
`models/Boeing_737-300_Helios_Livery.blend` project.

Both branches now follow the existing installed bleed connection through the
pylon and wing, an engine-side finned precooler, and a lower wing/body
air-conditioning pack. Each pack has two finned exchanger sections, an air-cycle
machine, a water separator, metal casings, couplings and a mounting tray.
The two conditioned-air ducts stop at independent, named output anchors.

## Viewing and animation

In **ECS Overview → Pneumatic system | Phase 2**, use:

- **Left branch / Right branch:** display either or both Phase 2 branches.
- **Show ducts / Show precoolers / Show packs:** independent physical visibility.
- **Show airflow:** display the moving flow layer. Private Phase 2 duct and casing
  materials become partly transparent for inspection; turn it off to see opaque
  metallic equipment. Existing aircraft and engine materials retain their settings.
- **Flow speed (m/s):** shared apparent speed along every path. Default is 1 m/s;
  0 stops the markers. Press Space to play the timeline.
- **Left / Right / Packs:** additional inspection cameras. All existing overview
  camera buttons and aircraft/engine controls remain available.

For a clear close-up through the airframe, turn **Transparent shell** off and set
**Wireframe thickness** to 2 mm with the existing aircraft presentation controls.

Orange-red arrows travel from the installed engine bleed pipe to the precooler;
amber arrows continue through the supply and pack; cyan arrows leave each pack.
Small open arrow sleeves show motion on the existing opaque engine-side pipe.
Native Follow Path constraints and simple drivers work with script auto-execution
disabled. The sidebar is registered by the normal launcher. When reopening with
auto-execution disabled, the embedded `ECS_OVERVIEW_CONTROL.py` can register the
optional sidebar; the saved animation and custom properties already work.

Flow is a documentary animation, not a pressure/temperature simulation. The
architecture records the existing `ECS ENG | CTRL_ENGINE["BLEED_VALVE_OPEN"]`
source for future valve logic, with no duplicate valve-state control.

## Coordinates and installation

Units are metres: +X aft, +Y starboard, +Z up. Each branch reads its actual existing
Phase 1 handoff and tangent before constructing the continuation. Left and right
assemblies have properly handed routing and positive object scales.

| Connection | Left world XYZ | Right world XYZ | Local +Z direction |
| --- | --- | --- | --- |
| Existing installed bleed handoff | (14.80, -4.83, 2.23) | (14.80, 4.83, 2.23) | +X |
| `PACK_LEFT_OUTPUT` / `PACK_RIGHT_OUTPUT` | (12.12, -0.65, 2.18) | (12.12, 0.65, 2.18) | -X |

Precoolers are fitted to the wing volume next to the pylon handoff. Packs sit in
the lower center wing/body region, below the model's 2.68 m cabin floor and forward
of the main landing gear. Mounting rails, brackets and airframe attachment pads
give installation context. No master aircraft mesh is edited.

Placement is a documentary reconstruction fitted to this model's actual wing,
fuselage, fairing, cabin and landing-gear geometry, rather than manufacturing CAD.
The [Boeing 737 Classic airport planning document, D6-58325-6 Rev D](https://www.boeing.com/content/dam/boeing/v2/airports/acaps/737CL_REVD.pdf)
provides the aircraft envelope and ground-service context. Internal component
shapes and mounting coordinates are visual approximations fitted to the saved
model, not dimensions taken from that airport planning document.

## Ownership and future extension

The existing `ECS_OVERVIEW` collection contains the additive `ECS_PHASE2` layer:

```text
ECS_PHASE2
    PNEUMATIC_DUCTS
    PRECOOLERS
    PACKS
    PHASE2_AIRFLOW
    PHASE2_HELPERS
```

`CTRL_ECS_PHASE2` owns the new controls. Only IDs marked `ecs_phase2_asset` may be
removed during a Phase 2 rebuild. Unrelated resources, Phase 1 geometry, cameras,
lights, materials, wireframe settings, and N1/N2/cutaway controls are protected.
Targeted Phase 2 rebuilds retain its saved visibility and speed settings.
The full launcher keeps the existing project-generation sequence and then runs
both ECS stages automatically; no additional manual generation step is needed.

`PACK_LEFT_OUTPUT` and `PACK_RIGHT_OUTPUT` are static empties with downstream local
+Z axes. The short cyan ducts terminate there. Phase 2 creates no mix or crossover
manifold, cabin/cockpit distribution, recirculation, outflow/relief valves, or cabin
pressure-control logic.

Saved-file validation is recorded in `reports/ecs_phase2_verification.json`.
The build checks preservation, owned-resource rebuilds, both physical routes,
equipment, flow direction/speed, independent controls, and save/reopen behavior
before publishing the final project.

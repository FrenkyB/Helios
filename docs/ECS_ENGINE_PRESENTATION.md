# Installed engine presentation

Run the existing `run_all.py` in Blender's Text Editor. Its final stage upgrades
the installed engines in `08 | ECS_OVERVIEW` and saves the same
`models/Boeing_737-300_Helios_Livery.blend` project.

## Controls

Open **N > ECS Overview > Installed engine presentation**. Each engine has three
mode buttons and six shell switches. Convenience buttons apply a mode to both.

| Mode | Visible enclosing geometry |
| --- | --- |
| Closed (0) | Complete nacelle and technical cases; internals remain behind the opaque shell. |
| Cutaway (1) | Outboard and top sectors removed, including corresponding front/aft sectors. Inboard and bottom sectors retain the engine outline. |
| Fully open (2) | Nacelle, enclosing technical cases, casing bolts and outer combustor shell hidden; rotating and static internals exposed. |

The six switches hide additional sections allowed by the preset. **Inner, Outer,
Top, Bottom** control the middle nacelle and corresponding technical cases.
**Intake/front** controls the intake ring; **Aft/core** controls the core cowling
and exhaust casing. Fully open hides these enclosing sections regardless of the
switches; their saved values remain available when returning to another mode.
For a complete closed exterior, enable all six switches and Show nacelle.

Inner means facing the fuselage: +Y on the left engine, -Y on the right engine.
Outer means facing away from the fuselage. The cutaway therefore mirrors across
the aircraft. Use Closed with selected switches off to choose a custom opening
for a particular camera angle.

Examples:

- Left Fully open / Right Closed: expose the left engine for a technical shot.
- Both Cutaway: retain both outlines while showing their internal architecture.
- Left Closed / Right Fully open: inspect the right engine from either side.
- Both Fully open: show both engine cores in a wide systems view.

Existing **Show nacelle**, **Show internals**, **N1 speed** and **N2 speed** remain
shared master controls. Nacelle and internals switches gate the new presentation;
N1/N2 rotation works in every mode. Shell sections stay static.

The retained **Global cutaway** control imposes at least Cutaway on both engines.
Clicking a new mode button first transfers that visible state to the independent
modes and clears the global override, then applies the requested mode. The other
engine keeps its visible state. Direct custom-property animation may also combine
the global override and independent modes deliberately.

## Saved state and animation

`CTRL_ECS_ENGINE_PRESENTATION` stores `LEFT_ENGINE_MODE`, `RIGHT_ENGINE_MODE`
(integers 0-2), and `LEFT_SHOW_*` / `RIGHT_SHOW_*` booleans for all six sections.
These native custom properties can be keyframed. Simple visibility drivers work
with automatic Python execution disabled; no frame or load handlers are needed.

The launcher registers the existing sidebar. On a later reopen with script
auto-execution disabled, run the embedded `ECS_OVERVIEW_CONTROL.py` once to show
the optional sidebar. Saved custom properties, visibility and animation already
work without it. Targeted rebuilds retain presentation settings.

## Organization and preservation

The original `ECS_ENGINE_TEMPLATE`, its shared master controller, geometry and
materials remain intact. The two existing installed collection instances point
to `ECS_ENGINE_LEFT_PRESENTATION` and `ECS_ENGINE_RIGHT_PRESENTATION`, each with
SHELL, INTERNALS and HELPERS groups. Internal geometry and materials are reused;
only the presentation object hierarchy and modular shell fragments are private.
Fragment mesh data is shared between the two installed engines. A hidden owned
source reference keeps the unchanged original template saved in the project.

The modular shells follow the original surface coordinates and UVs, adding closed
boundaries at section splits. Only IDs marked `ecs_engine_presentation_asset`
are replaced during this upgrade. All standalone engine content, original scenes,
Phase 1/2 equipment, bleed installation, controllers, cameras, lights, wireframe
and transparent-aircraft settings are protected by before/after verification.

The build checks two targeted executions, source-surface coverage, shell masks,
all nine left/right mode combinations, animation, UI registration and save/reopen
behavior before replacing the final file. The existing final file is backed up
under `reports/backups/` before publication.

# 737-300 cockpit panel reference

These original JPG files were supplied by the user in
`Dokumentacija/B737-300_COCKPIT_REFERENCE_PACK/B737-300_COCKPIT_REFERENCE_PACK/737-300_cockpit/`.
The overview includes the source artwork's FlightPanels attribution; the files
are retained as supplied. No replacement artwork or online references are used.

- `celotna_slika.jpg`: overall assembly and relative arrangement reference.
- `cockpit_1.jpg`: main panel, Classic EADI/EHSI, engine indications, MCP and CDU.
- `cockpit_2.jpg`: throttle quadrant detail.
- `cockpit_4.jpg`: fire handles, aft radio pedestal and side-console outlines.
- `upper_panel.jpg`: forward and aft overhead arrangement.

`scripts/cockpit_reference_panels.py` expresses traced rectangles, outlines and
control centers in source-image pixel coordinates. Panels have real thickness;
major bezels, keys, rotaries, toggles, yokes and levers are editable objects.
Printed labels, instrument scales and static display contents use UV crops from
the original images, which are packed into the delivered Blender file.

The four detail JPG files are required to regenerate this cockpit. The overview
is a reference only. Opening the saved `.blend` needs no external image files.
This is the Classic EFIS arrangement shown by the supplied board, not an exact
Helios equipment certification or functional avionics simulation.

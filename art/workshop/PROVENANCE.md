# Provenance

The SVG source geometry in this package was authored programmatically for the tlfrobot conversation, using the included `tools/build_assets.py`. It is not a trace of the earlier PNG concepts and does not reuse vector paths from Karel, robotzero, third-party icon sets or the textbook. The previously generated robot sheets served as discussion context only.

The resulting design is a simpler top-down workshop rover named Timo. No existing named cartoon character is used as its identity. Generic concepts such as a camera probe, gripper, clock and play symbol are used for their interface meaning.

No fonts, embedded rasters, remote artwork or JavaScript inside SVG masters are included. PNG files under `desktop/` are derived renders from the newly authored vector masters, with their provenance recorded in `desktop/manifest.json`.

The optional JavaScript preview renderer is separate source code and is not embedded in SVG masters. This note describes how the files were made; it does not assert legal exclusivity over generic robot or interface ideas.

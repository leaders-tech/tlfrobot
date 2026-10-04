# Timo / Workshop — real SVG artwork for tlfrobot

This package corrects the earlier PNG-only delivery. **All 37 `.svg` files contain actual vector geometry.** None embeds a PNG, JPEG, base64 image or other raster. The character is a new, simpler vector interpretation for a top-down grid, not a lossless vectorisation of the previous glossy PNG sheets.

## Contents

- **22 required masters**, at the exact paths A01–A22 in the R1 art brief.
- **3 reserve masters**: gate, push button and lamp. These are graphics only, not new game rules.
- **12 derived individual control SVGs**, extracted from the same drawings as `ui/controls.svg`.
- `manifest.json`: asset inventory, named parts, palette roles, anchors and coordinate conventions.
- `gallery.html`: self-contained offline SVG gallery and 20 reference animation demonstrations. Open it in a browser. The gallery includes SVG-file downloads and a source-code view for every asset.
- `animation/player.js`: dependency-free SVG DOM preview renderer with direct frame sampling, play/pause/resume/cancel and request-controlled waiting.
- `animation/clips.json`: template inventory and phase metadata. The preview evaluator is implemented in `player.js`; this JSON is documentation/data, not an independently executable expression language.
- `desktop/`: **150 transparent PNG exports generated from the SVG masters**, at 64, 128 and 256 physical pixels per cell. These are optional native-desktop derivatives. The robot additionally has 13 full-canvas part layers at each density.
- `tools/`: complete source generator, export and validation scripts.

The Python robot package, Pyodide bridge, game model, checker and pygame renderer are **not** implemented in this artwork package. The preview player is not a second authoritative simulation. No claim is made that every renderer requirement from the full software specification has been accepted.

## Character and art direction

**Timo** is a small caretaker of a modular workshop. It carries crystalline components, marks tiles and inspects its surroundings. Components are cargo, not fuel. Paint is floor marking. There is no health, damage or death mechanic.

A circular chassis with four diagonal drive pods supports both movement policies. In relative mode an amber pointer defines forward. In absolute mode hide `heading`; retain a neutral upright presentation, and indicate a move with a transient directional arrow. A compass query or side scan must not rotate the robot as a side effect.

The drawing uses original geometric paths with a restrained blue, cream, amber and slate palette. It deliberately avoids perspective-dependent lighting, blur, metallic gloss and direction-specific sprite sheets. The face can remain upright while the chassis/heading rotate. The scanner and tools are independent.

## Using the SVG masters

A plain `<img src="robot/robot.svg">` is sufficient for a static icon. For animation, insert inline SVG or load it into a DOM instance, then transform the **named groups**, not random path numbers. `TlfRobotArt.mount` in the player demonstrates ID namespacing, including local `href` references.

Every original file is independently valid SVG and has a declared `viewBox`. Most icons use 64 × 64. Robot and cell layers use 128 × 128. The horizontal wall is 128 × 24 and its joint 24 × 24. The controls contact sheet is 256 × 192; each of its 12 symbols has its own 32 × 32 viewBox.

The masters are **static by default**. Animations are transformations and visibility/reveal changes applied from JavaScript, rather than independent looping timelines embedded in SVG files. This preserves host ownership of pause, cancellation and Python continuation.

### Robot parts

`robot/robot.svg` provides the following required logical groups:

`shadow`, `drive`, `body`, `heading`, `sensor`, `gripper-base`, `gripper-left`, `gripper-right`, `roller`, `eraser`, `cargo-hatch`, `eyes`, `eyelids`.

There are also addressable drive pods and individual eye groups. The exact parts are recorded in the manifest. Tools and eyelids have `opacity="0"` initially, not deleted geometry. Set the appropriate group to opacity 1 when deploying a tool. Several tools are not meant to be visible simultaneously.

**Do not reset all nested transforms to the identity**: drive pods have their own fixed rotations in the master. Apply animation in an outer wrapper or restore each part's original transform before sampling a new frame.

### Geometry

The robot pivot is `(64,64)` in local 128-unit cell space. SVG x grows right and y grows down; canonical north is negative y and positive angles are clockwise. World-to-SVG conversion belongs to the application.

| Anchor | Local coordinates |
|---|---|
| Pivot | `(64,64)` |
| Cargo | `(64,92)` |
| Sensor origin | `(64,26)` |
| Tool mount | `(91,83)` |
| Grip contact | `(109,107)` |
| Paint contact | `(107,106)` |
| Erase contact | `(109,106)` |
| Suggested current-cell object centre | `(111,109)` |
| Suggested count badge rectangle | `(99,115,27,12)` |

The object and badge locations are initial layout suggestions, not logical cell coordinates. The application must adapt dense/large number labels without concealing walls. The gallery uses live text for counts and values. No font files are included.

World placement, heading rotation and local tools should use separate wrappers. The independent sensor rotates around `(64,64)` to query an adjacent edge; it is not a long-range radar. Crystal transfer goes between the current-cell object and cargo, not from a neighbouring tile. A paint reveal clips only the current cell's paint layer; goals and crystals remain separate.

### Theme roles and states

Shapes have concrete fill/stroke values for portability and `data-fill-role` / `data-stroke-role` annotations for recolouring. The manifest contains the palette. Do not replace the literal SVG colours with unsupported CSS assumptions in desktop exports.

False is a slate round badge; error is a warm triangular warning. Completed is a neutral stop-like square; accepted is an amber seal. Colours are supplementary to shape. Start, finish and target are independent outline annotations, never paint or exit triggers.

The bag uses `bag-base`, `bag-lid`, `bag-contents` and `bag-indicator`. Its amount, including ∞, is application-owned text. Compass labels and True/False/None are also live text. `clock-hand` rotates around `(32,34)`; `compass-pointer` around `(32,32)`.

### Controls

`ui/controls.svg` contains these symbols: `play`, `pause`, `stop`, `step`, `reset`, `history-back`, `history-forward`, `speed`, `zoom-in`, `zoom-out`, `fit`, `settings`. The sheet also renders a text-free contact sheet so that opening it does not show a blank document. For `<img>` or simpler integrations, use the matching individual files in `ui/icons/`.

### Reserve assets

`gate.svg` has `gate-frame` and `gate-panel`. A host implementing the open-state preview should clip the sliding panel to the slot while translating it; gate physics and interaction are not included. `switch-cap` moves down by 4 local units when pressed. `lamp-on` and `lamp-off` are visibility-switched alternatives, and differ in shape/detail as well as colour.

## Preview animation API

The self-contained gallery already embeds every required resource. The separate `animation/player.js` declares `window.TlfRobotArt`. Its `Stage` is a **fixed demonstration scene**, not a drop-in production world renderer.

- `new TlfRobotArt.Stage(container, assets)` mounts the scene; `assets` maps the manifest paths to SVG source strings.
- `stage.render(key, progress, options)` samples one of the 20 demonstrations directly. Progress is clamped to `[0,1]`. Returned counts are only preview accounting.
- `stage.play(key, options)` returns `{finished, pause, resume, cancel, completeInput}`. `finished` is a Promise. Cancel restores the start frame and rejects with `AbortError`; handle that rejection.
- `stage.destroy()` cancels and removes the demonstration scene.

`options` include `direction`, `heading`, `policy`, `turn`, `transfer`, `count`, `bag`, `painted`, `subject`, `result`, `input`, `lifecycle`, `reduced` and `speed`. See the full gallery controls and `clips.json` for their use. For a **successful transfer preview**, the renderer guarantees a nonempty source; use C11 to demonstrate an empty source. Do not infer command legality from this convenience behaviour.

A key/click waiting clip does not resolve merely because its icon is drawn: call `completeInput(value)` from an accepted host event. Timed waiting uses `input: "time"` and `waitSeconds`. The production application must supply its own authoritative runtime clock, request IDs and completion/commit semantics.

The gallery provides direct seeking and five snapshots, but does not simulate all future world edits or multiple actors. In particular, C17 is a visual crossfade illustration, not a fully general map-snapshot loader; C18 is a viewport example. Reduced-motion mode avoids the spatial interpolation but retains state/value feedback.

## Desktop exports

Exports preserve the complete original canvas; `trim_offset` is always `[0,0]`. See `desktop/manifest.json` for the scale and original source of each file. Hidden robot tools are forced visible **only in their separate layer exports**, so an application can composite them explicitly. Static whole-robot exports retain the normal hidden-tool state.

These are PNG layers, not frame animations and not a tested pygame adapter. For rotations, always transform a fresh source layer rather than repeatedly rotating an already rotated bitmap.

## Rebuild and validate

From the package directory:

```sh
python tools/build_assets.py
python tools/build_gallery.py
python tools/validate_assets.py
```

For desktop exports, install CairoSVG in the build environment and run:

```sh
python -m pip install cairosvg
python tools/export_desktop.py
```

A browser test additionally uses Python Playwright and an installed Chromium. `tools/test_browser.py` accepts `--chromium` when a system executable should be used. It reports exactly what was tested; it does not claim Firefox/Safari or native renderer compatibility from a Chromium test.

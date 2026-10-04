# TLF Robot — Original Art and Animation Brief

**Release:** R1 · **Revision:** 0.2 · **Date:** 4 October 2026  
**Scope:** one original character, two movement policies, crystals, paint, sensing, input and clear error feedback.

This is the separate production brief for the graphics team. The full development requirements remain authoritative for runtime and map semantics. **The SVG illustrations, clip data and desktop exports described below will be created and delivered separately. This documentation bundle does not contain finished robot artwork or animation files.**

## 1. Design goal

Create a small, friendly, competent maintenance robot working in a modular workshop. It moves crystalline components, marks tiles with paint and navigates partitions. The story gives purpose to existing actions without inventing fuel, health, gravity or combat. The working visual theme ID is `workshop`; the character's final name and palette are still design decisions, not borrowed branding.

The character must be original. Do not trace, recolour, collage or reuse the old Karel, robotzero or textbook assets. Reuse the idea of an expressive probe or short movement, not the old silhouette, face, palette or path geometry. Keep provenance for sketches, masters and exports. Visual approval is required before production packaging.

Use a predominantly top-down view. A slightly decorative surface treatment is acceptable, but fixed isometric projections, directional lighting and baked-in text make rotation unnecessarily difficult. Aim for readable shapes at 32–128 pixel cell sizes. The robot should be recognisable and its current cell obvious, not an elaborate cartoon that conceals the algorithm.

## 2. One character, not two

The same robot serves both policies. In relative mode a conspicuous heading pointer defines forward. The body and pointer can rotate on a quarter-turn command. In absolute mode the pointer is absent and the body must not imply a hidden forward direction; a short temporary arrow communicates each movement direction.

Do not draw four direction-specific bodies. Do not invent two species or different toolkits. A circular/rounded chassis, omnidirectional drive, cargo hatch and independent tool/probe parts are preferable. A very directional front bumper or face that stays visibly pointed north is unsuitable for the absolute presentation.

The renderer has separate world translation, heading rotation and local tool groups. Text and HUD labels remain upright. The absolute policy is a presentation configuration of one master, not another character design.

## 3. Complete source SVG inventory

There are **22 required SVG source files**. This includes one robot master with named parts and one controls sheet with twelve symbols. It does not mean twenty-two full-character illustrations.

| ID / file | Purpose | Required drawing and reuse |
|---|---|---|
| **A01** `robot/robot.svg` | Robot master | One original top-down robot with a neutral body, separately addressable heading pointer, drive ring, sensor, gripper, roller, eraser, cargo hatch, eyes and eyelids. All tools are parts of this one master, not different characters. Transform named groups; omit heading pointer in absolute mode; no four-direction files. |
| **A02** `world/crystal.svg` | Crystal | One original, unmistakably crystalline collectible; legible at small size, with no number embedded. The same symbol serves a pile, a carried crystal, a toolbar and inventory. |
| **A03** `world/paint.svg` | Paint patch | A full-cell coating with restrained texture; separate from targets and the floor. Reveal or remove through a rectangular clip; recolour through theme tokens. |
| **A04** `world/wall.svg` | Wall segment | A straight horizontal one-cell barrier centred on an edge, with a repeatable middle and explicit end anchors. Rotate for vertical walls; repeat the middle, do not distort decorative ends. |
| **A05** `world/wall-joint.svg` | Wall joint | A small neutral connector hiding seams at corners, T-junctions and crossings. One rotationally symmetric symbol; actual wall topology remains engine data. |
| **A06** `world/marker-start.svg` | Start marker | Thin origin marker that remains visible under paint and a robot. Static annotation, never a sensor or checkpoint trigger. |
| **A07** `world/marker-finish.svg` | Finish marker | Distinct docking outline, not a paint-coloured tile or automatic exit. May coexist with start and target; reaching it does not terminate execution. |
| **A08** `world/marker-target.svg` | Target marker | Corner brackets or a dashed outline marking cells mentioned in the task. Never interpreted as paint; target quantities use live text. |
| **A09** `hud/bag.svg` | Bag indicator | A cargo-container icon with separately addressable lid and contents indicator. Empty, nonempty and infinite variants use the same geometry and live text. |
| **A10** `hud/compass.svg` | Compass indicator | Four cardinal ticks and a movable requested-direction indicator. No embedded letters. Renderer adds localised labels and rotates only the pointer. |
| **A11** `hints/direction-arrow.svg` | Direction arrow | A short straight arrow drawn in one canonical direction. Rotate for four directions; show in absolute movement without creating heading. |
| **A12** `hints/sensor-pulse.svg` | Sensor pulse | A small probe/ray segment with origin and target anchors; not a long-range radar scan. Rotate and scale its length to the adjacent edge or current-cell object. |
| **A13** `hints/focus-ring.svg` | Focus ring | An open outline that can surround a cell, object, inventory icon or selected location. Translate, scale and fade; colour is supplementary, not the only signal. |
| **A14** `status/boolean-true.svg` | True symbol | A clear positive boolean symbol without baked-in text. Always pair with the actual Python text True; not a task-success trophy. |
| **A15** `status/boolean-false.svg` | False symbol | A clear negative boolean symbol, visually distinct from a fatal error. Always pair with False; an ordinary false sensor is not an accident. |
| **A16** `status/error.svg` | Error symbol | A calm warning indicator, distinguishable by shape from the boolean symbols. Shared across error categories; category and explanation are live text. |
| **A17** `status/completed.svg` | Program completed symbol | A neutral completion indicator. Must not imply that a task was solved. |
| **A18** `status/success.svg` | Verified success symbol | A modest original seal used only after a checker accepts the result. A brief reveal is enough; no obligatory confetti. |
| **A19** `input/keyboard.svg` | Keyboard input symbol | A key-cap outline or small keyboard cue, with an empty label area. Actual key names are live localised text. |
| **A20** `input/pointer.svg` | Pointer input symbol | A mouse/touch-compatible click cue. Translate to the selected cell; support keyboard activation of the same control. |
| **A21** `input/clock.svg` | Timed wait symbol | Clock outline with separately addressable hand. Progress comes from the runtime wait, never an independent looping timer. |
| **A22** `ui/controls.svg` | Control icon sheet | Symbols: play, pause, stop, step, reset, history-back, history-forward, speed, zoom-in, zoom-out, fit, settings. One sheet with 12 named symbols; labels and keyboard shortcuts are HTML/native UI text. |

### Optional low-cost reserve

These three extra masters can be designed at the same time but are not functional R1 world elements. A closed/open gate is a sliding panel; a push button is a cap moving over a base; a signal lamp changes its lens state. Do not implement associated rules on the basis of artwork alone.

| ID / file | Purpose | Limits |
|---|---|---|
| **X01** `reserve/gate.svg` | Sliding gate | Frame and sliding panel in separate groups; shown open/closed by translation. Rotate one horizontal master; no gate physics is promised in R1. |
| **X02** `reserve/switch.svg` | Push button | Base and cap in separate groups; pressed state by short translation. Mouse, touch and keyboard can later share the same semantic activation. |
| **X03** `reserve/lamp.svg` | Signal lamp | Outline and inner lens; off/on states differ in shape/detail as well as colour. Opacity/state replacement; no illumination shader. |

### Things that do not need additional pictures

The developer generates the grid, blank floor, world-sized backgrounds, coordinate labels, numbers, True/False/None text, quantity badge backgrounds, direction/turn arcs, selection rectangles, paint-reveal clips and camera transforms. One crystal with a numeric badge is sufficient for every finite quantity. The bag displays a live ∞ label when appropriate. These are not invitations to bake numbers or words into SVG paths.

## 4. Robot anatomy and geometry

Use `viewBox="0 0 128 128"`. Rotation pivot: `(64,64)`. Canonical relative heading: north, toward negative local y. Keep the neutral body approximately within radius 42 around the pivot, with space around it for wall edges, current-cell objects and badges. Fine decoration must not make the heading pointer or tools unreadable.

Required logical part names: `body`, `drive`, `heading`, `sensor`, `gripper-base`, `gripper-left`, `gripper-right`, `roller`, `eraser`, `cargo-hatch`, `eyes`, `eyelids`, `shadow`. They can be SVG groups or exported symbols. A fixed alternate pose selected by visibility is permitted for a shape that cannot be moved rigidly; do not introduce a full deformation rig for a tiny visual difference.

The artist supplies exact numeric anchors for pivot, cargo, probe origin, tool mount, grip contact, paint contact and erase contact. The developer supplies current-cell object and adjacent-edge target anchors in world space. The manifest also declares a safe badge region. After these anchors are agreed, runtime code must not infer them by measuring random SVG paths.

Tools act on the current cell. A side sensor reaches the immediately adjacent edge. The gripper must not appear to take a crystal from the cell ahead. Paint stays within the current tile, and the robot does not shift logically just because its roller extends. The shadow must work with rotations and with absolute translation, rather than implying a moving light source.

## 5. Source file rules

Use simple paths/shapes, groups, fill/stroke, opacity and transforms. Transparent background and declared viewBox are required. All geometry must be bounded and every named part must survive the export process.

No embedded raster image, SVG script, event handler, external asset, external font, `foreignObject`, imported stylesheet or filter-dependent essential effect. Avoid costly blur/glow. Prefer layered solid shapes for depth. Do not deliver a PNG hidden inside an SVG wrapper. The build checks file contents, not only extension.

Every human-language string is live text generated by the application. Do not convert numbers, keyboard labels, compass letters or Python values to outlines. Use theme-role names for paint, frame, body, outline, accent and status colours; the approved palette is a separate design decision. A state must remain distinguishable without its colour.

Multiple running examples can share a page, so logical part names will be namespaced on mounting. No asset may rely on a global DOM ID outside its own manifest. Relative local references must remain correct after namespacing.

## 6. Animation format and ownership

The runtime representation is **SVG parts + parameterised clip data**. The developer provides a small evaluator; the artist provides reviewed tracks and phases. Every clip can be paused, resumed, accelerated, cancelled or sampled at any progress. A free-running animated SVG, GIF, Lottie file or video is not the master format.

Basic operations: translate, rotate about a pivot, scale, change opacity, toggle visibility, reveal/wipe a rectangle and move along a short anchor-based polyline. Use the shared linear/ease-in/ease-out/ease-in-out curves. For numerals and status text, emit a named display cue, not an embedded text animation. Do not require arbitrary SVG path morphing, spring physics, shaders or a script in an art file.

A static sprite that translates can be a good movement animation. A probe that rotates and extends can be a good sensing animation. A small reveal is sufficient for a paint sweep. Spend effort on the clarity of source, target and outcome, not on animation complexity.

The template declares assets, parameters, normalised tracks, duration policy, display cues, transient nodes, reduced-motion behaviour and cleanup. The manifest binds logical node names and anchors. Animation code must never decide how many crystals exist or whether an edge is blocked.

## 7. Complete template inventory

There are **20 reusable runtime templates**. Outcomes such as True/False, finite/infinite bag or north/south are variants of these templates, not independent hand-drawn movies.

| ID / template | Trigger and parameters | Visual contract / duration at 1× |
|---|---|---|
| **C01** `move.step` | move / north / south / east / west. Parameters: direction, movement policy, start/end anchors. | Translate actor root between adjacent cell centres; optional drive-ring motion; absolute mode shows a short direction arrow. No change of heading during a step. Duration: 350 ms. |
| **C02** `turn` | turn_left / turn_right / turn_around. Parameters: signed angle, initial heading. | Rotate heading group by signed -90, +90 or +180 degrees; draw a short procedural arc. Never substitute +270 for -90; quarter turns use 220 ms, half turns 360 ms. Duration: 220 / 360 ms. |
| **C03** `crystal.transfer` | take / put. Parameters: take/put, before counts, finite/infinite bag. | Deploy gripper, move one crystal between current-cell object anchor and cargo anchor, settle, retract. No teleport from a neighbouring cell; visual accounting includes one in-transit crystal. Duration: 420 ms. |
| **C04** `paint.apply` | paint. Parameters: fresh/repeated, theme. | Deploy roller and reveal the current-cell paint layer with a rectangular sweep; already-painted cells get a shorter visible pass. Repeated paint does not darken or accumulate layers. Duration: 450 / 180 ms. |
| **C05** `paint.erase` | erase. Parameters: painted/clean. | Deploy eraser and wipe only the paint layer; clean cells get a short acknowledgement. Crystals, targets, walls and visit history are untouched. Duration: 350 / 180 ms. |
| **C06** `sense.edge` | all eight *_clear sensors. Parameters: world direction, clear/blocked, observed edge. | Point the independent probe at the requested adjacent edge and show the sampled True or False. A blocked probe is not a collision; do not turn the body or scan beyond one edge. Duration: 180 ms. |
| **C07** `sense.cell` | on_crystal / painted / crystal_count. Parameters: crystal/paint/count, result, target anchor. | Focus the relevant current-cell layer or its empty location; display the exact sampled value. Absence is visible; no synthetic object is added to the world. Duration: 180 ms. |
| **C08** `sense.bag` | bag_empty / bag_count. Parameters: boolean/count, empty/nonempty/infinite. | Focus the cargo indicator and reveal its sampled value. An empty bag yields True for bag_empty; an infinite bag_count yields None, not Infinity. Duration: 180 ms. |
| **C09** `sense.heading` | four facing_* sensors. Parameters: requested direction, actual heading, result. | Compare compass query with actor heading and show the sampled boolean. Do not rotate the logical actor while checking. Duration: 180 ms. |
| **C10** `error.wall` | illegal step. Parameters: attempted direction, edge. | Nudge toward the attempted edge without crossing it; return to the original centre; highlight the obstacle. No state mutation or successful movement flash. Duration: 280 ms. |
| **C11** `error.object` | NO_CRYSTAL / EMPTY_BAG. Parameters: cell/bag. | A short unsuccessful reach toward the empty cell or inventory, then return to idle. No crystal may appear even transiently as a successful transfer. Duration: 240 ms. |
| **C12** `error.status` | unavailable command / limits / Python / transport / invalid map. Parameters: error category, source range, details. | Show an error indicator and the correct source/field diagnostic. No fake movement; invalid maps can be reported without drawing a world. Duration: 160 ms. |
| **C13** `input.waiting` | wait_key / wait_click / wait. Parameters: key/click/time. | Show the corresponding input cue; for a timed wait reflect runtime progress. The cue does not settle the request; only input, timer completion or cancellation does. Duration: controlled by the pending request. |
| **C14** `input.received` | accepted key or cell click. Parameters: key/click and sampled value. | Flash the consumed key or focus the selected cell before returning the value. Do not consume one physical input twice; do not highlight a new cursor position instead of the sampled cell. Duration: 120 ms. |
| **C15** `lifecycle` | ready / completed / cancelled. Parameters: ready/completed/cancelled. | A modest state change and matching status cue. Completed is neutral; Stop does not celebrate success. Duration: 160 ms. |
| **C16** `verdict` | checker pass / checker failure. Parameters: accepted/rejected, differences. | Reveal success seal or focus concrete mismatching cells/edges. Only trusted/publicly configured checking triggers a success indication. Duration: 360 ms. |
| **C17** `view.reset` | reset or load another map. Parameters: old/new snapshot. | Replace with the authoritative initial snapshot through a brief crossfade. Not reverse execution and not a sequence of robot commands. Duration: 120 ms. |
| **C18** `view.camera` | follow / pan / zoom / fit. Parameters: viewport, target transform. | Interpolate the view transform with actor/world geometry unchanged. Camera animation does not affect sensor results or create world boundaries. Duration: 180 ms. |
| **C19** `focus.feedback` | source/value focus, counters, editor confirmation. Parameters: target, label, old/new value. | Brief outline or opacity change on an existing target; numeric text updates at the owning clip cue. This is a helper track, not another command or an independent completion barrier. Duration: 120 ms. |
| **C20** `idle.blink` | optional idle expression. Parameters: eye state. | Close and reopen eyelids with a tiny scale/visibility change. Ambient only, off when paused/hidden/reduced-motion; never delays Python. Duration: 120 ms. |

## 8. Essential clip direction

### Movement and turning

For a step, ease between adjacent cell centres over roughly 350 ms at normal speed. A tiny drive-ring movement is enough; there is no requirement for a walk cycle. The final centre must be exact. Do not rotate heading during movement. In absolute mode a temporary arrow indicates the direction and disappears afterwards.

For turns, rotate about the agreed centre: left −90°, right +90°, around +180° in SVG-clockwise convention. Quarter turns take roughly 220 ms and a half-turn 360 ms. The left turn must not spin right for 270°. A procedural arc can explain the direction; no extra turn illustration is needed.

### Crystal transfer

Proposed phases: reach 0–25%, pickup/transfer 25–70%, deposit 70–85%, retract 85–100%. Source and destination anchors are inside the current cell and at the robot's cargo hatch. A separate HUD pulse can acknowledge the inventory change; do not send the crystal on a long trip across the screen.

At pickup show one transient carried crystal. The visible pile decreases by one, then the destination increases at deposit. During transfer the visible accounting includes the carried object. With a finite bag, never briefly show two successfully transferred crystals. With an infinite bag, keep its ∞ indicator fixed while the cell changes by one. The model's actual commit happens on successful request completion; intermediate numbers are only a consistent visual preview.

Test the last crystal disappearing, a pile remaining, the first crystal arriving, a large count and a crystal on a painted target. On cancellation before commit, the preview restores the original state and removes its carried object. Reversing the decorative motion must not execute reverse model operations.

### Paint and eraser

Fresh paint: tool deploys, sweeps across a rectangular reveal, then retracts. Full coverage is a boolean state, not a freehand accumulation of strokes. Repaint is a short additional tool movement on an already painted tile, without changing opacity or shade. Use approximately 450 ms fresh and 180 ms repeated.

Erase uses the eraser, not a recycled crystal animation. Reveal the floor by removing only the paint layer. A clean cell gets a shorter acknowledgement. Targets, walls and crystals remain intact. Use approximately 350 ms for removal and 180 ms for an empty pass.

### Sensing

An edge check briefly directs the independent probe toward exactly one adjacent edge. A useful phase layout is point 0–30%, show subject/value 30–80%, retract 80–100%, totalling about 180 ms. Do not swivel the whole logical robot just to look left. Do not show a ray crossing multiple cells.

Current-cell checks focus the crystal/paint layer or its empty location. Bag checks focus the bag. Compass checks compare query direction and heading without turning it. The actual Python result is displayed, including zero and None. True means the predicate is true, not that something good happened: an empty bag must show True for `bag_empty()`.

A False sensor is a normal branch decision. An illegal move is an error. The art must distinguish those situations. Negation in student Python does not require a second visual measurement.

### Errors

A wall collision is a small nudge toward the obstacle, never passage through it. Then restore the exact original centre and show the error cue. Missing crystal and empty bag use a short unsuccessful reach with no phantom successful object. An unavailable command, syntax error, limit or bridge failure requires a readable status, not a made-up movement or explosion.

No destruction, death, alarm flash or long failure animation is required. The result should help a child locate the mistake, not punish them visually. The UI owns detailed explanation and source highlighting.

### Input, pause and lifecycle

Waiting for a key or click displays the relevant cue until a real input or cancellation settles it. Do not make the cue's own animation finish the Python wait. A timed wait follows runtime progress. A consumed key/click gets a short acknowledgement at its sampled target, not at the mouse's later location.

Pause means frozen frame, not a new infinite loop. Idle blink is ambient and never delays Python. Program completion is neutral; the success seal appears only when a checker approves the task. Reset restores a snapshot, not a reverse route.

## 9. Web and desktop exports

For the web provide source SVGs and validated clip data. The renderer mounts parts in DOM and uses WAAPI/a shared timeline. For local Python provide RGBA PNG layers or atlases generated from the same masters, plus pivots, anchors and the same tracks. A desktop runtime cannot be assumed to execute SVG browser animations.

Preserve trim offsets and scale metadata in raster exports. Suggested base raster sizes are 64, 128 and 256 physical pixels per cell; they are exports, not three artistic designs. The source geometry should also be inspected at 32, 48 and 96 CSS-pixel cells. Repeated rotations should always start from a clean source layer to avoid cumulative blur.

A clip may use a short pre-rendered local tool pose sequence only where rigid transforms are insufficient; it must still be driven by the common progress and cancellation contract. Do not render an entire world into a frame sequence.

## 10. Preview gallery and acceptance

Provide a standalone HTML gallery with controls for every template, its outcomes, four directions, initial headings, count and bag variants, paint/target overlaps, playback speed, progress seeking and reduced motion. It must work without an application server after the documented asset load/export step, or be delivered as a self-contained HTML preview with embedded vector art. It must not require remote old-repository files.

Each example displays the template ID, associated Python call, parameters and before/after state. Include side-by-side exact snapshots at 0%, 25%, 50%, 75% and 100%. A test harness checks direct seeking against sequential playback and ensures cancellation removes all temporary nodes. The gallery's demo state is not a second authoritative game engine.

Review these contrasts explicitly: relative heading versus absolute direction neutrality; crystal versus paint versus target; ordinary False versus fatal failure; completed versus accepted; empty versus infinite bag; a current-cell action versus an adjacent-edge query.

All required variants must remain understandable in reduced motion and at small scale. No font files, borrowed characters, embedded rasters or opaque video-only masters are acceptable in the SVG delivery. The art work package is complete only when its files validate against the manifest and both web and desktop adapters can use the agreed geometry.

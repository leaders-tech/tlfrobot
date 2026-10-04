# TLF Robot — Release 1 Development Requirements

**Document revision:** R1 / 0.2 · **Date:** 4 October 2026  
**Status:** implementation specification, not a description of an available package.  
**Audience:** Python/runtime developers, browser developers, test-platform maintainers and the separate graphics/animation team.

## 0. Reading this specification

This document consolidates the earlier functional draft and live-execution addendum. Where they disagree, this document governs the proposed first release. “MUST” is an acceptance requirement; “SHOULD” permits a documented, tested alternative. Installation commands and package APIs below describe the required delivered product. They are not a claim that `tlfrobot` has already been published to PyPI.

The user-facing entry point is always:

```python
from tlfrobot import *
```

Release 1 has **one robot in each running world and one original character design**. It retains two map-selected movement policies: relative movement with heading, or absolute cardinal movement without heading. These are not two characters or two separate libraries. Multiple simultaneous robots, robot switching, network multiplayer and concurrent student controllers are out of scope.

The default graphical mode is **live execution**: a Python action returns only after its action-specific animation finishes. A sensor returns its sampled value after displaying that measurement. Input waits return after a real or scripted input is delivered. The UI remains responsive while Python waits. Recording is a consequence of execution, not a substitute for it.

### 0.1. Decisions made for this release

| Area | Required decision |
|---|---|
| Language | Real Python; synchronous, ordinary functions; no source-to-async rewriting. |
| Authoring format | TOML 1.0, normally `map.toml`; JSON is the wire/normalised representation. YAML is not an additional R1 parser. |
| Why not change to YAML now? | The earlier draft already used TOML; it supports comments and ASCII multiline maps and has a standard-library parser in Python 3.11+. The user's `map.yaml` suggestion was not a format constraint. [S07] |
| Browser | CodeMirror 6; Pyodide in a module Worker; TypeScript; SVG DOM; Web Animations API and a small shared timeline controller. |
| Desktop | CPython and optional `pygame-ce`; no local web server or browser required. |
| Judge | CPython with no graphics imports; stdin map; compact NDJSON output; checker re-executes actions on its own trusted model. |
| State transition | Prepare an atomic transaction, show its preview, commit on successful completion, then resume Python. Cancellation before commit does not apply the transaction. |
| Interaction | `wait_key()`, `wait_click()` and `wait(seconds)` in R1. Physical map editing during execution and autonomous doors are deferred. |
| Art | 22 required SVG source files, including one robot master and one 12-symbol controls sheet; 20 reusable animation templates. Three additional prop masters are an optional art reserve only. |

### 0.2. Separate original-art delivery

**The original SVG illustrations, authored animation tracks and derived desktop image assets listed in this document will be produced and supplied as a separate graphics/animation work package after this specification. They are not included in the present documentation bundle.**

The implementation team owns the renderer, timeline evaluator, input bridge, state model and integration. The art team owns the original character, visual language, master SVGs, authored clip data and reviewed exports. Both teams jointly verify the manifest and clip contracts. Development may use clearly identified internal geometric test shapes, but the public release must not ship borrowed Karel/robotzero art or claim temporary test shapes are the completed design.

The historical implementations are behavioural references: short readable commands, visible sensing, and suspension until a visual action or user answer completes. They are not asset donors. The supplied `robotzero` review and source archive informed the requirement; this document does not claim the old implementation supports the new protocols or features.

## 1. Product scope and architecture

### 1.1. Mandatory end-to-end workflows

The same student source file must work in these three workflows without editing robot calls:

**Browser:** host loads a map → bootstrap makes the map available on stdin → runner reads it once → student code from CodeMirror is compiled separately → commands animate SVG DOM → UI inputs wake the waiting program.

**Desktop:** install `tlfrobot[desktop]` → create a student file and adjacent `map.toml` → run the package launcher from the terminal or a PyCharm module configuration → a native window displays the live world.

**ejudge:** install the base package in the actual runner and checker environments → ejudge starts a trusted bootstrap and the submitted student file → map arrives on stdin → compact JSON lines leave stdout → a checker in the package validates transitions and the task's goal.

The package must also validate a map, replay a saved trace, run a scripted interaction without graphics and expose reusable checking functions for task authors.

### 1.2. Responsibilities

| Component | Owns | Must not own |
|---|---|---|
| `core` | World state, walls, capabilities, legal actions, sensor sampling, transaction preparation/commit | SVG, pixels, audio, DOM, OS window loops |
| `maps` | Parse, validate, normalise and serialise world/goal/input documents | Executing code contained in a map |
| `runtime` | Session lifecycle, student globals, call ordering, transport waits, cancellation, limits | A second implementation of movement rules |
| Host environment | Input queues, timeline progress, UI controls and transport acknowledgements | Deciding that a wall is passable by inspecting the drawing |
| Renderer | Read-only scene projection and temporary action previews | Authoritative robot coordinates or inventory |
| Trace writer | Bounded, ordered semantic records | Per-frame images or unrestricted debug printing |
| `checking` | Strict trace parsing, independent replay, goal evaluation, diagnostics | Trusting a student's claimed final state or success flag |

There is one Python implementation of the physical rules. The browser must not maintain a second JavaScript movement engine that can disagree with CPython. TypeScript may calculate screen transforms, hit tests and animation paths, but not robot legality.

In R1 the sole physical model may live in the student's execution Worker/process because all physical mutations come through one serial command stream. UI input capture and animation run outside it. A blocked Python Worker must not be expected to execute a Python input callback. Physical editor changes require Stop/Reset first. This is deliberately narrower than a fully autonomous multi-controller world. A later multi-robot release will move the authoritative coordinator outside blocked student controllers; R1 does not pretend that this is already implemented.

Use internal actor and controller identifiers from the start, fixed to `robot` and `student` in R1. Do not expose an unneeded object API, `active_robot` setter or multiple-character selector.

## 2. Python syntax and complete public API

### 2.1. Language rules

The import exports a fixed list of **32 functions**. A map controls permissions, not which Python names happen to exist. A disallowed function raises a clear library error. CodeMirror completion is filtered by the same capability metadata, but hiding an item in completion is not enforcement.

All movement, tool and sensing primitives take no arguments. Only `wait` takes an argument. `move(4)`, `paint("red")`, diagonal movement and automatic collection are not part of R1. Students use `for`, `while` and their own functions to express repetition and abstraction.

Actions return actual `None`; boolean sensors return actual `bool`; counts return ordinary Python values. No Promise, coroutine, proxy with a magical `__bool__`, or lazy value may escape into student code.

Normal Python semantics apply to `def`, recursion, variables, function parameters, `return`, `break`, `continue`, exceptions, `not`, `and`, `or` and short-circuit evaluation. A sensor skipped by short-circuiting is not called, animated or logged. Do not silently rewrite `move` to `move()` or `while front_clear:` to `while front_clear():`; a diagnostic may explain the likely mistake without changing the source.

There is no mandatory `main()`, `async`, `await`, `done()`, GUI event loop or renderer import in a student file. Compile source at module level in a fresh namespace. Do not wrap the student's statements in an invisible function, and do not concatenate a hidden header into the displayed source.

### 2.2. Public functions

| Signature | Returns | Requires | Meaning / clip |
|---|---|---|---|
| `move()` | `None` | relative | Move forward by one cell; preserve heading. C01 |
| `turn_left()` | `None` | relative | Rotate in place by -90 SVG-clockwise degrees; preserve position. C02 |
| `turn_right()` | `None` | relative | Rotate in place by 90 SVG-clockwise degrees; preserve position. C02 |
| `turn_around()` | `None` | relative | Rotate in place by 180 SVG-clockwise degrees; preserve position. C02 |
| `front_clear()` | `bool` | relative | Check the adjacent front edge relative to the sampled heading. C06 |
| `left_clear()` | `bool` | relative | Check the adjacent left edge relative to the sampled heading. C06 |
| `right_clear()` | `bool` | relative | Check the adjacent right edge relative to the sampled heading. C06 |
| `back_clear()` | `bool` | relative | Check the adjacent back edge relative to the sampled heading. C06 |
| `north()` | `None` | absolute | Move one cell by (0,+1); there is no heading. C01 |
| `south()` | `None` | absolute | Move one cell by (0,-1); there is no heading. C01 |
| `east()` | `None` | absolute | Move one cell by (+1,0); there is no heading. C01 |
| `west()` | `None` | absolute | Move one cell by (-1,0); there is no heading. C01 |
| `north_clear()` | `bool` | absolute | Check the adjacent edge to the north. C06 |
| `south_clear()` | `bool` | absolute | Check the adjacent edge to the south. C06 |
| `east_clear()` | `bool` | absolute | Check the adjacent edge to the east. C06 |
| `west_clear()` | `bool` | absolute | Check the adjacent edge to the west. C06 |
| `take()` | `None` | crystals | Transfer one current-cell crystal to the bag. C03 |
| `put()` | `None` | crystals | Transfer one bag crystal to the current cell. C03 |
| `on_crystal()` | `bool` | crystals | Whether the current cell contains at least one crystal. C07 |
| `bag_empty()` | `bool` | crystals | Whether a finite bag has count zero; false for an infinite bag. C08 |
| `paint()` | `None` | paint | Set the current-cell paint bit; repaint is an observable no-op. C04 |
| `painted()` | `bool` | paint | Read only the current-cell paint bit. C07 |
| `erase()` | `None` | paint, eraser | Clear only the paint bit; erasing clean ground is an observable no-op. C05 |
| `facing_north()` | `bool` | relative, compass | Whether the sampled heading is north. C09 |
| `facing_south()` | `bool` | relative, compass | Whether the sampled heading is south. C09 |
| `facing_east()` | `bool` | relative, compass | Whether the sampled heading is east. C09 |
| `facing_west()` | `bool` | relative, compass | Whether the sampled heading is west. C09 |
| `crystal_count()` | `int` | crystals, counts | Exact nonnegative count on the current cell. C07 |
| `bag_count()` | `int \| None` | crystals, counts | Exact finite bag count; None for an infinite bag. C08 |
| `wait_key()` | `str` | keyboard | Consume the oldest queued normalised key, or wait for one. C13+C14 |
| `wait_click()` | `tuple[int, int]` | pointer | Consume the oldest queued primary-cell click, or wait for one. C13+C14 |
| `wait(seconds: int \| float)` | `None` | Available in either movement policy | Advance explicit logical waiting time and suspend; seconds must be finite and nonnegative. C13 |

The `requires` column uses capability names described in §3. Multiple requirements are conjunctive. A map's optional `allowed_commands` list can restrict them further.

### 2.3. Detailed state semantics

Relative heading is one of `north`, `east`, `south`, `west`. `turn_left()` maps north to west, `turn_right()` maps north to east, and `turn_around()` changes heading by two quarter turns. The half-turn visual path is clockwise. Position is unchanged by every turn or sensor.

An absolute robot has **no heading**. Its canonical JSON heading is `null`. It can translate in every cardinal direction without turning. Show the same character without its heading pointer and with a temporary movement arrow. Do not leave it apparently facing the direction of its last step.

A wall separates two adjacent cells. Crystals, paint and presentation markers never block movement. There is no gravity, energy consumption, momentum, collision body size or diagonal corner cutting.

`take()` transfers exactly one crystal from the current cell. `put()` transfers exactly one crystal to the current cell. A finite bag has no game-specific capacity limit, but representation and resource limits still apply. In a finite-bag world, the sum of crystals on the board and in the bag is conserved by these operations.

An infinite bag is an explicitly configured source and sink. Taking removes one crystal from the cell and leaves the bag infinite; putting adds one and leaves the bag infinite. Cells can contain only finite counts. `bag_empty()` is false for an infinite bag. `bag_count()` returns `None`, displayed as the Python value `None`, while the bag's status badge may show ∞. Do not use JSON Infinity, a negative sentinel or a special numeric class.

Paint is one boolean layer. Repainting is valid and idempotent, but still consumes a call and is animated. Erasing a clean cell is similarly valid. Erasing affects no crystals, targets or visit history. The eraser is a separately enabled capability. R1 has one logical paint colour and unlimited paint; the theme chooses its display colour.

### 2.4. Errors and terminal failure

A command is checked before a transaction is prepared. A failed call cannot partially move the robot, change its bag or paint a cell. World-command errors mark the session as failed. A student may catch the Python exception, but catching it does not restore the session: subsequent robot calls fail and the final status remains unsuccessful. Ordinary caught exceptions in a student's own calculations do not by themselves fail the world.

| Code | Meaning |
|---|---|
| `WORLD_NOT_LOADED` | A robot call occurred outside a configured runner session. |
| `COMMAND_UNAVAILABLE` | Movement policy, tool, sensor, input permission or command allowlist forbids the call. |
| `WALL_COLLISION` | A step would cross a wall or a bounded world's outer boundary. |
| `NO_CRYSTAL` | `take()` was called on an empty cell. |
| `EMPTY_BAG` | `put()` was called with an empty finite bag. |
| `SESSION_FAILED` | An attempted call after an earlier terminal world failure. |
| `INVALID_ARGUMENT` | A library argument has an invalid type/value, including negative/nonfinite `wait` duration. |
| `INPUT_EXHAUSTED` | The configured script has no next event for a requested input. |
| `INPUT_MISMATCH` | The next scripted event has the wrong type for this wait. |
| `INPUT_OVERFLOW` | An input queue exceeded its explicit bounded capacity. |
| `MAP_INVALID` | Invalid authoring document; student execution has not started. |
| `CALL_LIMIT`, `TRACE_LIMIT`, `OUTPUT_LIMIT`, `STATE_LIMIT`, `NUMBER_RANGE`, `COMPUTE_LIMIT`, `WAIT_LIMIT` | The indicated execution or representation budget was exceeded. |
| `PYTHON_EXCEPTION` | An uncaught student exception; preserve its original type and source position. |
| `RUNTIME_FAILURE` | A transport, renderer or infrastructure failure, not a robot mistake. |

Provide named Python exceptions under `tlfrobot.errors`, with a common `RobotError`, stable `code`, user-safe `message` and structured `details`. They are not added to import-star. Normal Python arity errors raised before entering the dispatcher remain normal `TypeError`; do not forge a successful call record for them. `SystemExit(0)` is normal source termination only when the session has not already failed. Other `SystemExit` values are unsuccessful. A user Stop produces `cancelled`, not a successful result and not a wall collision.

## 3. Map language and coordinate conventions

### 3.1. Format and default discovery

Use UTF-8 **TOML 1.0** with `format = "tlfrobot-world/1"`. Recommended filename: `map.toml`; `.world.toml` is also acceptable when selected explicitly. R1 does not silently interpret YAML as TOML. Keeping one authoring parser avoids format-specific differences across browser, desktop and judge. Use Python `tomllib` and a schema validator shared by every runtime. The parser must limit input size before parsing. [S07]

Map lookup by the launcher is deterministic:

1. Explicit `--map` argument or `run_file(..., map_source=...)`.
2. `TLFROBOT_MAP`, if no explicit source was supplied.
3. `map.toml` next to the selected student source file.

A supplied `-` means stdin. Explicit relative paths and relative environment paths are resolved against the launcher's working directory; automatic discovery is relative to the student file, not an arbitrary IDE working directory. Do not scan parent directories, choose the newest map or fall back from a missing explicit file to another map. Show the resolved path in graphical run metadata. Importing `tlfrobot` performs no map I/O and opens no window.

`--world` may remain a deprecated CLI alias for `--map` to accommodate the earlier draft, but not a second source with independent precedence. Specifying both is an error.

### 3.2. Sections

| Section/key | Contract |
|---|---|
| `format` | Required literal `tlfrobot-world/1`. |
| `id` | Required nonempty identifier, maximum 128 characters. |
| `title` | Optional plain text, never interpreted as HTML. |
| `rules.movement` | Required `relative` or `absolute`. |
| `rules.tools` | Optional list drawn from `crystals`, `paint`, `eraser`; default empty. Eraser requires paint. |
| `rules.sensors` | Optional list drawn from `compass`, `counts`; default empty. Compass requires relative; counts requires crystals. |
| `rules.inputs` | Optional list drawn from `keyboard`, `pointer`; default empty. |
| `rules.allowed_commands` | Optional additional allowlist of public names. Omitted means all capability-permitted calls; empty means no robot-library calls. |
| `board` | Bounded geometry or an unbounded plane, and edge walls. |
| `robot` | Required initial position; heading and bag according to capabilities. |
| `cells` | Optional initial crystal and paint layers. |
| `presentation` | Trusted theme identifier, viewport, coordinate display and task markers. |
| `goal` | Optional public practice goal. Production checkers can use a separate private goal document. |
| `limits` | Optional tighter task limits, never larger permissions than the host allows. |

Unknown fields and enum values are errors, not ignored typos. Reject duplicate capability names, duplicate coordinates within a layer and duplicate map keys. Do not accept strings containing Python, template code, SVG markup, URLs, includes or executable goal expressions. Arbitrary custom properties are not an R1 escape hatch.

### 3.2.1. Limits and validation fields

The optional `limits` table accepts only `max_calls`, `max_trace_bytes`, `max_output_bytes`, `max_state_cells`, `max_wait_us` and `max_compute_ms`, each a nonnegative integer. A supplied map value is combined with the host value using the stricter minimum. Omitted values use host policy. `max_calls=0` permits a normally terminating source that makes no library calls; zero is not interpreted as unlimited. The pre-parse `max_map_bytes`, maximum input queue size and JSON decoder bounds are host settings, not values that the unparsed map can increase. A default `max_wait_us` of 3,600,000,000 bounds explicit waits to one logical hour; a host may choose a tighter classroom policy. Compute time and abandoned-session wall time are separate host budgets.

State-cell accounting counts the union of nonzero-crystal and painted-cell coordinates, not the sum of the two layer lengths. Wall-interval count and bounded-map dimensions have independent host validation ceilings. Exceeding a viewport limit changes only what is drawn; exceeding a model limit must be reported, not implemented by adding walls.

### 3.3. Coordinates and numeric representation

Cells use integer `(x, y)` coordinates, with **x increasing east/right and y increasing north/up**. The usual bounded origin is `[0, 0]`, the lower-left cell. A cell occupies the square `[x, x+1] × [y, y+1]`; its visual centre is `(x+0.5, y+0.5)`.

All finite coordinates, counts, revisions, IDs and semantic microseconds crossing the JSON boundary must remain within JavaScript's exact integer range, ±(2**53−1). Counts, times and sequence IDs are nonnegative. Booleans are not accepted as integers. No wrapping, rounding, hidden coordinate clipping or artificial wall is allowed at a numeric limit; raise `NUMBER_RANGE` instead.

Internally use sparse storage: a mapping for positive crystal counts and a set for painted cells. Absent entries mean zero and unpainted. The robot's current cell may contain both layers and any presentation markers. Maintain visits separately in replay/checking, not as an automatic visible paint layer.

### 3.4. Bounded boards and walls

Default `board.topology` is `bounded`; `origin` defaults to `[0, 0]`. Supply `size = [width, height]` with positive integers. The whole outer boundary is closed. It is not possible to leave a bounded map by omitting one outer wall in its source.

An inner wall is an edge interval:

```toml
[board]
size = [6, 5]
walls = [
    { axis = "h", at = 2, span = [1, 4] },
    { axis = "v", at = 4, span = [0, 3] }
]
```

`h` fixes y and varies x; `v` fixes x and varies y. `span=[a,b]` covers unit edges indexed by `a <= k < b`. Therefore the horizontal example closes the north edges of `(1,1)`, `(2,1)` and `(3,1)`. Its endpoints are grid vertices, not occupied cells. Require `a < b`. Merge overlapping or adjacent walls; a duplicate never opens a passage. Reject intervals outside a bounded board. Explicit duplicates of its outer boundary are harmless after normalisation.

### 3.5. ASCII alternative

For a small board, `board.ascii` replaces both `size` and `walls`; it cannot be combined with them. It is not a second overlaid geometry source.

```toml
format = "tlfrobot-world/1"
id = "small-workshop"

[rules]
movement = "relative"
tools = ["crystals", "paint"]

[board]
ascii = '''
+---+---+---+---+
| .   .   .   . |
+   +---+   +   +
| .   . | .   . |
+   +   +   +   +
| .   .   .   . |
+---+---+---+---+
'''

[robot]
at = [0, 0]
heading = "east"
bag = 0

[cells]
crystals = [{ at = [1, 0], count = 2 }]
painted = [[2, 1]]
```

A W×H board uses `4W+1` characters per line and `2H+1` lines. The first visual row is north. Junction positions contain `+`, horizontal intervals contain exactly `---` or three spaces, vertical positions contain `|` or a space, and each cell interior is exactly ` . `. The dot is only a cell placeholder in the map notation, not a crystal. Robot, paint and quantities remain structured data so arbitrary layer combinations do not need a growing alphabet of ASCII symbols.

Tabs are forbidden. Normalise CRLF; remove at most the optional outer empty lines and a uniform source indentation, not meaningful interior spaces. The contour must be closed. Diagnostics must report the source line/column and, where possible, the affected grid edge. The graphical editor must render the parsed geometry, not a visually similar separate interpretation.

### 3.6. Unbounded plane

`board.topology = "plane"` means all integer cells, including negative coordinates. Forbid `size`, `origin` and `ascii`. Wall intervals can use `"-inf"` at the lower end and `"+inf"` at the upper end. These are wall endpoint tokens, not floating-point values.

```toml
[board]
topology = "plane"
walls = [
    { axis = "h", at = 1, span = ["-inf", "+inf"], gaps = [[7, 8]] }
]

[presentation]
viewport = [-4, -2, 12, 6]
```

This section example denotes an infinite horizontal barrier with the one-cell passage above `(7,0)`. `gaps` are finite half-open edge intervals within their own span. Subtract each wall's gaps before taking the union of walls; another wall may still close the same gap. Keep rays and lines as intervals, never materialise infinitely many edges. The viewport is `(xmin, ymin, width, height)` and is never a physical boundary.

The complete runnable plane example in the bundle uses a finite isolated wall and ordinary recursive Python. Unbounded storage is still subject to finite call/state/coordinate limits.

### 3.7. Initial state and presentation

`robot.at` is required. In relative mode `robot.heading` is required; in absolute mode it is forbidden in authoring TOML and normalises to JSON `null`.

With crystals enabled, `robot.bag` is required and is either a nonnegative integer or `"infinite"`. Without crystals it is forbidden and normalises to `null`. Initial `cells.crystals` is a list of `{at=[x,y], count=n}` with positive n. Zero entries are omitted. `cells.painted` is a list of coordinate pairs. A layer belonging to a disabled tool is rejected, not silently retained as inaccessible gameplay data.

`presentation.theme` is a built-in theme identifier, with `workshop` as the proposed first theme. `show_coordinates` is boolean. `markers` contain `{at, kind}`, with `kind` equal to `start`, `finish` or `target`. Multiple kinds may share a cell. Exact duplicate markers may be rejected as authoring mistakes. Markers do not affect sensing, movement or completion. A target remains distinguishable when covered by paint or crystals.

Map titles, errors and quantities are rendered as text nodes, never interpolated HTML. No asset URL is accepted from a student map. Persisted changes are explicit: save a copy of the current state or edit the initial map after stopping. Do not silently overwrite the original source file or drop TOML comments. A “save normalised copy” operation may replace formatting when clearly labelled. [S07]

## 4. Goals and reusable checking

### 4.1. Separate execution status from a task verdict

`completed` means the student source terminated normally and no session error occurred. It does not mean `accepted`. Without a goal, show neutral completion only. Do not automatically finish when the robot touches a marker; a program may pass through its destination and later return.

Public practice maps may embed `goal`. A private goal is a separate file:

```toml
format = "tlfrobot-goal/1"

[goal]
robot_at = [1, 0]
bag = 1

[goal.crystals]
mode = "exact"
cells = []

[goal.paint]
mode = "exact"
cells = [[1, 0]]
```

A separate checker goal is authoritative and replaces an embedded public goal; do not merge them with ambiguous precedence. A missing production goal is a task configuration error, not automatic acceptance. Hidden goals and hidden test worlds are never sent to a browser under the assumption that hidden object properties are secret.

### 4.2. Standard goal predicates

| Predicate | Semantics |
|---|---|
| `robot_at` | Exact final cell. Omission means position is not constrained. |
| `robot_heading` | Exact final heading, only in relative mode. Omission means heading is not checked. |
| `bag` | Exact finite bag quantity or `"infinite"`; only with crystals enabled. |
| `crystals.mode = "exact"` | Entire final nonzero layer equals the supplied positive-count list. Unlisted cells must contain zero. |
| `crystals.mode = "specified"` | Only listed cells are checked for exact counts; zero is allowed here. |
| `crystals.mode = "unchanged"` | Entire crystal layer equals the initial layer; no `cells` field. |
| `paint.mode = "exact"` | Exact final painted-cell set. |
| `paint.mode = "contains"` | All listed cells are painted; other cells are unconstrained. |
| `paint.mode = "unchanged"` | Entire paint layer equals the initial layer; no `cells` field. |
| `visits.mode = "contains"` | Every listed cell was visited at least once. |
| `visits.mode = "exact"` | The set of visited cells equals the listed set. |
| `visits.mode = "all_reachable"` | Every cell in the finite reachable component of the initial position was visited. |

Visit tracking includes the initial cell and every successfully completed movement destination. A turn, sensor, failed movement or cancelled movement does not create another visit. An optional `visits.forbid_revisits = true` forbids entering any cell already entered, including returning to the initial cell. Otherwise revisits are allowed.

For `all_reachable`, enumerate with a configured validation bound. Bounded boards are straightforward; a plane can still enclose a finite component. If finiteness cannot be established within the authoring/checker bound, report a task configuration error. Never silently truncate a search and call the truncated set “all reachable”. A custom trusted Python checker remains the right extension for unusual geometry or trace constraints.

Checking “all visited cells are next to a wall” is not checking “the whole perimeter was visited”. Add explicit regression tests in which the robot does nothing, walks a proper subset or revisits only its start. A generic valid route is not compared to one privileged reference route.

### 4.3. Checking package contract

The delivered package must provide:

| API | Required behaviour |
|---|---|
| `tlfrobot.maps.load_world(path_or_file)` | Read and strictly validate a TOML world. Never start a student session. |
| `tlfrobot.maps.loads_world(text)` | Equivalent loading from UTF-8 text. |
| `tlfrobot.checking.parse_trace(stream, *, limits)` | Incremental bounded NDJSON reader with structured format errors. |
| `tlfrobot.checking.replay(world, records, *, inputs=None, limits=None)` | Re-execute allowed operations from the trusted initial state; validate reported values, sequence and final state. Return final state, counts and visit information. |
| `tlfrobot.checking.evaluate_goal(world, replay_result, goal)` | Return structured acceptance and mismatches. Does not execute strings from the goal. |
| `tlfrobot.checking.check_files(map_path, trace_path, *, goal_path=None, inputs_path=None)` | High-level reusable check returning a `CheckResult`. |
| `tlfrobot.checking.ejudge.main(argv=None)` | Thin CLI adapter using ejudge's argument order and exit codes. |

`CheckResult` must carry a verdict category (`accepted`, `wrong_answer`, `presentation_error`, `checker_error`), a stable diagnostic code, a concise message, and bounded details including offending call and/or cell when available. The browser may use the same Python checker for public goals. A checker never imports pygame or requires a display.

Trusted custom Python goal functions are allowed in a task maintainer's own checker code, not by putting a callable name, import path or Python expression in a map. Checks should reuse `replay` instead of reimplementing all movements.

## 5. Live actions, sensing and cancellation

### 5.1. Request lifecycle

Each internal request has `run_id`, `controller_id`, `actor_id`, `request_id`, operation, arguments and optional source location. There is at most one unresolved request per R1 student controller. IDs belong to transport/session management; random run IDs do not make deterministic judge traces nondeterministic.

For an action:

1. Check session status, permissions and resource budgets.
2. Prepare an immutable transaction from the current revision. It contains before/after data and the action-specific visual focus, but changes no authoritative state yet.
3. Send the action preview to the host. The host renders the associated finite clip and remains able to receive Pause, Stop and allowed input.
4. On successful action completion, commit that transaction once against the expected revision, publish the resulting semantic record and committed snapshot/delta, and release the preview.
5. Return `None` to the waiting Python call.

For a sensor, sample the value at step 2. Animate and later return **that same value**, including the revision at which it was sampled. Do not sample again at animation completion. Sensors and idempotent operations still count as calls and are visible.

The committed state is always at discrete grid coordinates. Interpolated pixels and an in-transit decorative crystal are presentation data. An inspector during a pending action should show the last committed state and the pending command, not claim a fractional grid coordinate is the model.

### 5.2. Exactly-once settlement

A request settles exactly once as completed, failed or cancelled. Acknowledge by request identity, not by “whatever animation ended last”. Late callbacks from an earlier run are ignored. A renderer failure is not successful completion. An idle blink or unrelated camera animation is not part of the request's completion barrier.

Stop sets cancellation out of band, wakes any blocked bridge and prevents the next call. If cancellation wins before commit, discard the pending transaction and restore the last committed visual state without reverse robot commands. If commit already won, keep the committed action and cancel before the next one. The race must have one well-defined arbiter and an automated regression test.

A prepared world error is terminal even when its explanatory animation is skipped or cancelled. It has no state effect. Renderer cancellation must not turn a known failed command into success. A lost renderer/transport must settle as an infrastructure failure or cancellation, never leave an immortal waiting Python call.

### 5.3. Controls

Play/Resume, Pause, Step, Stop, Reset, speed, zoom, pan, fit and history navigation are environment controls, not import-star functions. Pause freezes the current clip immediately. Step finishes a partly displayed call or executes exactly the next call; it then pauses before another call. This is API stepping, not a full Python debugger. A source loop that never calls the library may require the interrupt/watchdog rather than producing a Step event.

Going backwards displays recorded history; it does not rewind the Python stack. To resume the live stack, return to the live edge. Reset or editing past source starts a new session. Changing code in CodeMirror while running edits the next-run buffer, not the currently executing source snapshot.

Default speed is 1×. Offer 0.25×, 0.5×, 1×, 2× and 4×. An explicitly selected instant-action mode still preserves command order and consumes inputs normally. It is not a record-first mode. A browser without a supported live bridge must show a compatibility explanation; it may offer a clearly labelled replay-only mode for static programs, but must not silently run interactive tasks that way.

## 6. User interaction and time

### 6.1. Input scope

R1 includes keyboard and primary-cell pointer input. A click can select a tile; it does not directly teleport the robot, add a wall, paint or give it a crystal. Physical map editing is available only after stopping. This keeps one-robot interactions useful without introducing concurrency rules, gates, timed collisions or multiple physical state owners in the first release.

`wait_key()` consumes the oldest queued keyboard event and returns a normalised string. Arrow keys are `up`, `down`, `left`, `right`; Space is `space`; Escape is `escape`; Enter is `enter`; Backspace is `backspace`. Printable single-character values use the produced Unicode character with ASCII letters lowercased. Ignore modifier-only presses, composition events, and platform/IDE shortcuts. Ignore OS auto-repeat in the baseline profile; every accepted physical keydown is one event.

The world must have focus before receiving keyboard input. Typing code, selecting completion or using browser shortcuts must not control the robot. Escape in a focused game is an input key, not implicitly the global Stop command. The Stop button and a documented nonconflicting host shortcut work independently. On-screen direction/paint controls may emit the same key events for touch access.

`wait_click()` returns an ordinary `(x, y)` tuple captured at the time of a primary pointer activation. In JSON this is `[x,y]`. Convert screen coordinates through the inverse camera transform and the world y-axis convention. Floor to the cell; reject clicks outside bounded geometry. Clicking a thin wall uses a documented hit-testing rule: wall-edit handles are inactive in run mode, and primary input chooses the containing cell after coordinate conversion. Camera dragging is not a click. A move larger than the configured click threshold becomes a pan, not a delayed selection. A keyboard-accessible cell cursor must offer the same activation.

Input queues are distinct for key and click events, FIFO within type, cleared at Run/Reset, and bounded to 128 events per type by default. Events received while a robot animates are queued, not discarded. The UI may display the number waiting. Overflow must be surfaced and fail/stop the input session rather than silently executing an unbounded backlog. Stop does not enter either queue. While explicitly paused, accept navigation/Stop but do not enqueue new game inputs; already queued events remain queued.

No student callback is invoked asynchronously inside a pending action. The student chooses when to wait and what to do with the returned value. R1 does not export generic DOM objects, browser events, JS proxies, device keycodes, drag paths or mouse-polling functions.

### 6.2. Explicit timed waits

`wait(seconds)` accepts an `int` or finite `float`, excluding `bool`, and requires `seconds >= 0`. Convert to integer microseconds using nearest-microsecond rounding with ties upward, then validate range and wait budgets. `wait(0)` is a valid observable yield point. Values that overflow or are nonfinite fail before waiting.

Keep explicit logical waiting time separate from elapsed animation time and human thinking time. In R1 actions/sensor illustrations do not advance a simulated physics clock, and there are no autonomous timed world objects. `wait` advances `time_us` by its requested duration. A normal live renderer paces that interval; headless execution advances it immediately. Pause freezes its progress. Speed changes may scale its presentation rate while preserving the logged semantic duration. Reduced motion removes moving clock hands but does not remove a deliberate wait; instant-action mode does not silently turn a requested timed wait into no delay. A separate explicit fast/headless run may bypass wall-clock delays.

Human input waiting does not add guessed animation-based times to `time_us`. R1 grading checks consumed input order and explicit waits, not unrecorded wall-clock reaction speed. Autonomous timed events and timing-sensitive race tasks require a later, explicitly versioned scheduling contract.

### 6.3. Scripted input for repeatable tests

Use a separate input document, not an overloaded stdin stream:

```toml
format = "tlfrobot-input/1"
events = [
    { kind = "key", value = "right" },
    { kind = "key", value = "up" },
    { kind = "key", value = "space" },
    { kind = "key", value = "escape" }
]
```

For scripts, consume events in their listed order. The next requested input type must match the next listed event: fail with `INPUT_MISMATCH` rather than quietly skipping it. Exhaustion produces `INPUT_EXHAUSTED`; a headless worker must not hang forever. An input script is trusted test data. It is provided independently to both runner and checker; an output trace cannot invent its own trusted script.

A private goal document may contain an additional `input_script` table with the same `events` list and `require_all_consumed` boolean (default true for a supplied script). The exported standalone `inputs.toml` remains the form used by CLI `--inputs`. For an ejudge interactive test, deliver the script to the runner as a separate task resource/approved bootstrap configuration, not by putting private goals into student stdin. This deployment profile must be demonstrated before claiming interactive ejudge support. Static robot tasks require no script and are the mandatory initial ejudge deployment.

Ordinary `input()` is not a second undocumented input API. The student-facing stdin is at EOF after map setup in the judge/browser baseline; use the explicit waits for game interaction. `print()` is supported. Do not monkeypatch `time.sleep` or built-in input into robot actions.

## 7. Browser runtime and CodeMirror integration

### 7.1. Editor

Use CodeMirror 6 with Python language support, indentation, bracket handling, undo/redo, search, source diagnostics and capability-aware completion. Completion metadata is generated from the same API catalogue as the Python exports and documentation. CodeMirror supports custom completion sources; do not maintain an unrelated hardcoded list. [S01]

Each completion shows the exact signature, return type and a short explanation. The world mode/capability list is visible next to the editor. Missing parentheses may be highlighted as likely mistakes without modifying code. Source-range decorations must not become an alternative source buffer.

Run freezes the exact source string and filename for the session. Errors and API-call highlights refer to this frozen version; if the visible buffer changes, display that it is a new version. Use 1-based lines and 0-based Unicode code-point columns in the Python-facing protocol; convert explicitly to CodeMirror's UTF-16 offsets. Test non-ASCII text and characters outside the BMP. If only a reliable line is available, highlight the line and do not invent a column.

A first release must have a useful execution log and call-line highlighting. It is not required to inspect every local variable, trace every Python line or implement an IDE-grade breakpoint debugger.

### 7.2. Host bootstrap and stdin

The host owns map selection. A course header can refer to a map path or resource ID, but the runner receives **map bytes**, not a Python expression that opens an arbitrary URL. Resolve/fetch the map before execution; enforce the host's same-origin/resource policy. Render a loading or validation error before starting the student when map delivery fails.

Pass the complete UTF-8 map through a finite stdin provider and read it once in the trusted bootstrap. Source code is supplied on a separate channel. Pyodide exposes standard stream hooks, including byte-array stdin and explicit EOF. [S02]

The following illustrates the required boundary, not a complete browser application:

```javascript
const bytes = new TextEncoder().encode(mapText);
let provided = false;

pyodide.setStdin({
  stdin() {
    if (provided) return null;
    provided = true;
    return bytes;
  },
  isatty: false,
});
```

The bootstrap then calls the package runtime with `map_source="-"`, separate student source and an already attached browser transport. It must not hand stdin simultaneously to both the map parser and student `input()`. Preserve map bytes as immutable run metadata. A header is separate infrastructure: execute it under its own synthetic filename, then compile student source under `solution.py`; do not shift every student line by a hidden line count.

### 7.3. Python execution and package installation

Run Pyodide in an ES-module Worker. Workers cannot directly manipulate the page DOM, so renderer calls pass through the bridge. Current Pyodide documentation requires module-type workers; use a pinned tested Pyodide distribution, not floating `/stable/` runtime assets. [S03]

Build the base library as a platform-independent Python wheel. Preload or install the exact release wheel through the supported Pyodide package path, such as `micropip` for pure-Python wheels, before student execution. [S06] Do not request pygame or system GUI wheels in Pyodide. The web build, wheel, map schema, API catalogue, trace version and art manifest must advertise compatible versions and reject an incompatible pairing.

Do not download dependencies on every Run click. Cache preloaded immutable runtime assets and document the cold-start and warm-start paths. Test cleanup after repeated runs, including Python/JS proxies and disposed callbacks. A pooled Worker is acceptable only if student state cannot contaminate another run; otherwise reset or recreate it.

### 7.4. Synchronous request/response bridge

Baseline: `SharedArrayBuffer` with an atomic response mailbox, used only from the execution Worker. The host thread never blocks. A browser with no suitable bridge cannot offer the required live contract. [S04]

A request is posted with its identity and payload. The Worker waits for the matching response state. The host completes the animation or obtains input, writes the response payload and byte length into shared storage, publishes the terminal response state atomically, then notifies. The Worker rechecks identity/state after every wake and decodes the payload only after publication. Notifications can be early or spurious; the condition check, not receipt of a notification alone, determines completion.

The response carries actual data (`None`, bool, count, key, coordinate pair, error or cancellation), not merely a “done” flag. A synchronously blocked Worker cannot rely on its own `onmessage` handler to receive that data and unblock itself. R1 has one outstanding request, so a bounded single-response mailbox is enough. State its maximum payload, overflow handling and buffer ownership explicitly; 64 KiB is a reasonable initial response capacity for these small return values, not a map-transfer size limit.

Cancellation is an independent flag/interrupt path. Use timed sleeps in the Worker, not busy polling, to check cancellation and runtime interrupts. Clear/protect mailbox reuse by request identity. Start/Stop/Reset must settle or invalidate all pending work. Never reuse a single unqualified global resolver across sessions.

Cross-origin isolation and a secure context must be checked before running. A normal dedicated deployment uses COOP/COEP and compatible resource responses; embedding in another page/iframe and the permissions policy must be tested explicitly. A Worker protects responsiveness, not account secrets: execute untrusted code on a dedicated origin/context without application tokens, private goals or privileged host interfaces. Restrict messages to the known protocol.

`pyodide.ffi.run_sync()`/JSPI may be a separately tested bridge alternative. The checked official documentation still marks it experimental and specifies allowed stack-entry modes. Merely calling `runPythonAsync()` does not make every synchronous Python call wait for an arbitrary UI Promise. [S05]

### 7.5. Rendering and interruptions

Update SVG/DOM in the page, driven by the transaction preview and committed events. Use native SVG groups, transforms, opacity and simple clipping. Web Animations API is sufficient for these finite effects and exposes completion, but cancellation rejects the current finished promise; handle it as cancellation, not as success or an unhandled rejection. [S08, S09]

All tracks of one clip share one progress value. A custom `requestAnimationFrame` controller may seek paused WAAPI effects, or coordinate equivalent native transforms, but two systems must not independently write the same node's transform. Separate world translation, heading and tool-local motion with nested groups.

Pause freezes progress. A hidden tab pauses its live visual execution rather than allowing Python to run invisibly ahead. An explicit instant/headless mode is a separate user choice. Prefer culling and chunked static wall/grid layers over creating a DOM element for every invisible tile of an infinite world. Reuse symbols and current-cell overlays. Benchmark normal 50×50 maps on a declared reference device; do not claim universal 60 fps without measuring it.

A program such as `while True: pass` must not freeze the UI indefinitely. Track compute-active time separately from bridge waiting time, set up the Pyodide interrupt mechanism and keep a host watchdog that can terminate the Worker. Interrupt polling only inside `move()` is insufficient. [S10] A SIGKILL-equivalent Worker termination may leave only a valid trace prefix; never fabricate a successful final record.

## 8. Local CPython and PyCharm

### 8.1. Installation and launch contract

The delivered base distribution is `tlfrobot`; graphical dependencies belong to the `desktop` extra. The target commands are:

```sh
python -m pip install "tlfrobot[desktop]"
python -m tlfrobot run examples/relative/solution.py
python -m tlfrobot run examples/relative/solution.py --map examples/relative/map.toml
python -m tlfrobot validate examples/relative/map.toml
python -m tlfrobot replay examples/relative/result.jsonl
```

In PyCharm create a Python run configuration with **module name `tlfrobot`** and parameters `run solution.py`. The configured interpreter is the environment where the package was installed. Place `map.toml` beside `solution.py` or add `--map` in that configuration. No additional student code is required.

Bare `python solution.py` is deliberately **not** a second auto-launch mechanism in R1. A robot call outside a configured session gives `WORLD_NOT_LOADED` with the exact module-launch instruction. Do not implement import-time process spawning, invisible re-execution of the source, or a long GUI loop in `atexit` just to imitate the IDE's default Run-file button. A future IDE integration can configure the launcher automatically without changing robot semantics.

The earlier draft required an explicit `--world`; R1 adds adjacent `map.toml` discovery and the clearer `--map` name. This is a host convenience change, not a new command of the robot.

### 8.2. GUI process arrangement

Use pygame-ce for the native scene and input. The launcher owns the GUI event loop and runs arbitrary student code outside that loop, preferably in a child interpreter launched through the package's own internal module. It must not depend on a student `if __name__ == "__main__"` guard. Do not re-run the user module on process spawn. An IPC transport implements the same request/completion contract as the browser.

The window remains responsive during computation, waiting, pausing and errors. After normal completion it remains open until the user closes it; the parent launcher, not an exit hook, owns this lifetime. Closing the window cancels a still-running child. Stop terminates noncooperative computation after a grace period. Clean up children, pipes and display resources across repeated runs.

The headless runtime must not spawn a GUI process, import pygame, initialise audio or depend on `DISPLAY`. Standard `print()` goes to the local console and optional trace output without corrupting the action channel. Desktop commands may optionally save a trace to an explicit file; no JSON protocol should unexpectedly replace the ordinary console unless headless mode was selected.

### 8.3. Reusing the art

pygame-ce can rasterise some SVG but does not provide the browser's SVG animation model. Its documented SVG support is limited and image loading produces a Surface. [S11] Ship pre-rendered RGBA PNG layers/atlases derived from the same approved master SVGs and evaluate the same transform/opacity/visibility tracks.

Do not rasterise a master SVG, load an image from disk or rebuild every tile on every frame. Cache source layers and useful scaled surfaces. Rotate the original high-quality layer rather than repeatedly rotating an already transformed result. Camera scale changes invalidate only affected caches. Define and test the opposite sign conventions of SVG-clockwise and pygame rotation.

Simple rectangular paint clipping, alpha changes and rigid transforms are required on both renderers. Arbitrary path morphing, browser filters, CSS layout inside SVG, Lottie, video and a second desktop art direction are not required. Pre-rendered frame sequences are a fallback for a particular effect only when demonstrably necessary; they do not become the authoritative semantics of an action.

Target Python 3.11–3.14 for the base package, with the actual release CI matrix documenting tested versions. Target Windows, macOS and Linux for desktop, gated by available tested dependency wheels. This is a release target, not a claim that every combination has been tested in this documentation exercise.

## 9. Headless execution and compact trace protocol

### 9.1. Running without graphics

```sh
python -m pip install tlfrobot
python -m tlfrobot run examples/relative/solution.py --mode headless --map - < examples/relative/map.toml > result.jsonl
python -m tlfrobot run examples/interactive/solution.py --mode headless --map examples/interactive/map.toml --inputs examples/interactive/inputs.toml > interactive.jsonl
python -m tlfrobot check examples/relative/map.toml result.jsonl --goal examples/relative/goal.toml
```

`headless` has no sleeps for animation and no graphical acknowledgements, but performs the same prepare/commit sequence and permissions. Explicit waits advance logical time; input waits consume a script. A missing script does not make an input wait return a fabricated value.

The `ejudge` mode uses the same semantics and output, with the exit-code treatment in §10. Do not silently choose headless because pygame is unavailable: report the missing desktop extra unless the mode was explicitly selected.

### 9.2. NDJSON version 2

Use UTF-8 JSON Lines: exactly one complete JSON object per line, newline-terminated. This is the application's own protocol, not an ejudge built-in JSON format. No BOM, blank lines, banners, debug text, NaN or Infinity are permitted. JSON object key order is irrelevant. Duplicate keys are invalid. Unknown mandatory-version records are rejected.

This specification selects **`v: 2` / `tlfrobot-trace/2`** and deliberately supersedes the more verbose draft trace/1. The compact form avoids per-call full maps and unnecessary patches; replay derives state changes from operations. Transport previews still carry before/after data needed for live animation. Do not confuse the compact persisted trace with the interactive request/response wire envelope.

| Record | Required content |
|---|---|
| `start` | `t`, `s=0`, `v=2`, one normalised public `world`, actor/controller IDs, source filename. Exactly one, first. |
| `call` | `t`, global `s`, increasing `n`, `op`, post-call `rev`; result/arguments/error as appropriate. |
| `input` | `t`, global `s`, increasing input `i`, `kind`, `value`; emitted when an input is delivered to a wait. |
| `output` | `t`, global `s`, `stream` and JSON-escaped `text`. Optional student output records. |
| `end` | `t`, global `s`, execution `status`, `rev`, `calls`, complete canonical final `state`; optional terminal `error`. Exactly one, last, for a fully recorded run. |

Global `s` starts at zero and increments by one for every record. `n` starts at one and increments by one for each dispatched robot API call. `i` starts at one for delivered input records. No random IDs or wall-clock dates are required in persisted traces. `actor="robot"` and `controller="student"` are declared once in `start` for R1.

`rev` increments once if a successfully committed action changes physical state, even if it changes both a bag and a cell. It does not change for sensing, no-op paint/erase, input, a wait, output, failed actions or cancellation. `time_us` is a separate explicit-wait accumulator and is not a physical-state revision.

For successful zero-argument actions, omit `args` and `result`; omitted action result means `None`. A sensor must include its exact `result`, including `null` for infinite `bag_count()`. `wait` must include `args` as the one-element list of the original validated numeric seconds. `wait_key` and `wait_click` include `result` and `input_id`. The immediately preceding undelivered `input` record is bound to that completed call; replay validates its ID, type and value against the trusted script when supplied.

A failed dispatched call has an `error` object with a stable code and message and an unchanged revision; it has no successful result. A cancelled dispatched call may have `cancelled: true`, no successful result and unchanged revision. `end.status` is `completed`, `error`, `cancelled` or `limit`. A Python failure before any robot call still has start/end records when the runner can catch it. No complete-end guarantee can be made after forcible process termination.

The trace records inputs **on delivery**, which is sufficient for replaying R1's serial interaction semantics. Raw arrival timestamps, unconsumed UI events and every pointer movement are optional local diagnostics, not authority for grading. A later timing-sensitive multi-controller protocol will need a richer event-order model.

### 9.3. Normalised world and final state

`start.world` contains `format`, `id`, normalised `rules`, `board`, `robot`, `cells` and optionally safe presentation data. Omit public/private `goal` and authoring-only comments. Expand missing defaults; convert ASCII to the same structured walls as every other board. Keep plane intervals finite/ray/line rather than expanding them.

Normalised `rules` has `movement`, sorted `tools`, sorted `sensors`, sorted `inputs`, and an explicit sorted `allowed_commands` array. Normalised `board` has `topology` and canonical `walls`, plus `origin` and `size` only for bounded boards. A wall has `axis`, `at`, `span`; after normalisation its gaps have been subtracted and wall unions merged. Implicit bounded outer walls are not repeated in the canonical internal-wall list. Redundant authored outer walls disappear from it.

Normalised `robot` has `at`, `heading` and `bag`; `bag` is a nonnegative integer, `"infinite"` or `null`. Normalised `cells` has `crystals` as `{at,count}` objects and `painted` coordinate pairs, both sorted by `(y,x)`. Final state uses the compact form:

```json
{"robot":{"at":[1,0],"heading":"east","bag":1},"crystals":[],"painted":[[1,0]],"time_us":0}
```

In final state `crystals` consists of `[x,y,count]` triples sorted by `(y,x)`; entries with zero are absent. This compact terminal representation is explicitly different from the human-facing `{at,count}` authoring records. The mapper between them is shared, tested code, not backend-specific guesswork. In a world without crystals, `bag` is null and the crystal list is empty. In absolute mode heading is null.

Store source filename once in start. A call may contain `line` and reliable optional `column`, `end_line`, `end_column`. These fields are diagnostics, not proof of which source line really ran. Unknown absolute filesystem paths or private environment data are not required in student-visible errors.

### 9.4. Example and size policy

The complete `examples/relative/result.jsonl` in the bundle contains a start record, four calls and an end record for the accompanying source/map. Typical intermediate records are:

```json
{"t":"call","s":1,"n":1,"op":"front_clear","result":true,"rev":0,"line":3}
{"t":"call","s":2,"n":2,"op":"move","rev":1,"line":4}
{"t":"call","s":3,"n":3,"op":"take","rev":2,"line":5}
{"t":"call","s":4,"n":4,"op":"paint","rev":3,"line":6}
```

Do not save full snapshots or rendered frames on every call. A replay UI may build private indexes/checkpoints for efficient seeking. These are not student output requirements.

Default host ceilings for initial testing: 1 MiB map text, 32 MiB total trace, 1 MiB student output, 100,000 calls, 100,000 sparse nondefault cells, 128 pending events per input type. Use a 16 MiB maximum for any single JSON record and reserve enough terminal-output budget for the allowed final state. The default compute-active budget is 5,000 ms after runtime/package startup; it excludes animation, explicit Pause and user-input waiting. A classroom or judge profile can tighten or explicitly replace these host defaults before applying map limits. The effective state ceiling is reduced when it cannot fit the reserved final snapshot. Do not commit a state transition that cannot be recorded and then silently discard its event. These are configuration defaults, not performance measurements or universal task limits.

### 9.5. Output separation and distrust

In headless mode library/bootstrap stdout contains only protocol objects. Capture ordinary Python stdout/stderr writes from the student and encode them as `output` records, with embedded newlines escaped. Infrastructure diagnostics go to actual stderr. A judge run uses one process by default to avoid requiring extra processes in a restrictive sandbox.

A same-process Python wrapper cannot prevent hostile `os.write(1, ...)`, monkeypatching or direct protocol construction. Such malformed bytes must fail the checker; do not claim the stdout wrapper is a security boundary. An optional supervisor with separate data channels may harden capture later, but must not become an undocumented fork requirement in R1 ejudge deployment. Never unpickle student-controlled IPC or trace data.

The checker validates the provided start world against its trusted test world, parses strict record shapes, re-executes each operation, verifies each sensor/input result and revision, and compares the reconstructed final state with end.state. Illegal operations, missing/inconsistent records, forged results, invalid counts, unknown operations or an unsuccessful final status cannot be accepted because the goal coordinates happen to match.

A valid trace proves a valid sequence of operations, not that a submitted program genuinely used a loop, did not inspect an in-process map, or did not generate JSON itself. Syntax restrictions require separate source analysis; hiding state from malicious Python requires a stronger trusted external world service. Those are not properties of import-star or of replay alone.

## 10. ejudge integration

### 10.1. Supported integration route

Target the documented scripting/multifile support available in **ejudge 3.13.0 and later**; do not assume that a header/footer source concatenation is necessary. The supplied release notes and incomplete-program documentation describe `enable_run_props`, `extra_src_dir` and Python-specific build environment variables. [S12, S13]

Use the standard Python build route with a submitted `solution.py` and a trusted `main.py` from the task's `build` directory. The bootstrap calls `tlfrobot.runtime.run_file`. Student source remains a normal file with `from tlfrobot import *`; its module-level variables and source line numbers are preserved.

Task integration fragment:

```ini
# Global contest setting.
enable_run_props

# Merge these settings into the configured robot problem.
[problem]
short_name = "ROBOT"
long_name = "Collect and paint"
extra_src_dir = "build"
lang_compiler_env = "*=EJUDGE_SOLUTION_FILE=solution"
lang_compiler_env = "*=EJUDGE_START_FILE=main"
lang_compiler_env = "*=EJUDGE_ARCHIVE=1"
check_cmd = "checker.py"
use_corr = 1
```

This is a settings fragment, not a complete contest configuration. Restrict the actual task to the intended Python language. The documented file names in `EJUDGE_SOLUTION_FILE` and `EJUDGE_START_FILE` are given without `.py`; the build scripts append the language suffix. Verify the site uses the compatible standard scripts and run-properties support. [S13]

The complete target bootstrap is:

```python
from pathlib import Path
from tlfrobot.runtime import run_file

raise SystemExit(
    run_file(
        Path(__file__).with_name("solution.py"),
        map_source="-",
        mode="ejudge",
    )
)
```

`run_file` returns an integer process-exit status. It reads the map before compiling/executing the separate student source, configures clean output, and guarantees normal finalisation when an exception can be caught. It is infrastructure API, not exported by import-star.

### 10.2. Checker adapter

```python
#!/usr/bin/env python3
from tlfrobot.checking.ejudge import main

raise SystemExit(main())
```

With `use_corr=1`, interpret `argv[1]` as trusted map/input file, `argv[2]` as contestant output and `argv[3]` as the private `tlfrobot-goal/1` answer document. Without use_corr, the default adapter requires an embedded public goal or an explicitly configured task checker; it must not guess a missing answer file. ejudge's documented argument order is authoritative. [S14]

Use these checker exit codes: **0 accepted, 1 wrong answer, 2 presentation error, 3 checker/infrastructure failure**. The first three are documented verdict mappings; 3 is deliberately outside the accepted checker verdict codes and therefore signals checker failure. Do not accidentally exchange WA and PE. [S15] A deployment may choose to treat all invalid traces as WA for a simpler course interface, but this must be a configured adapter policy rather than an accidental return-code difference.

A well-formed trace with a legal execution but wrong goal is WA. An illegal action or dishonest result is WA with its semantic diagnostic. Malformed/truncated JSON, unknown record shape or invalid sequence framing is PE. Invalid trusted maps, an impossible goal configuration or a checker crash is checker failure, not student WA.

### 10.3. Runtime exit codes and environment

A normal `headless` or desktop runner returns 0 for successful source completion, 1 for student/world failure and 2 for invalid invocation/map or infrastructure failure. The ejudge adapter may return 0 after a caught student/world failure **only after emitting a complete unsuccessful end record**, so the checker can provide the intended explanation. This is necessary to account for ejudge normally invoking checkers only after a solution exits correctly within system limits. [S16] It can result in WA/PE diagnostics instead of native Runtime Error, by design.

Do not mask external time, memory or output limit termination. A killed process may not emit an end record. Never add a catch-all that converts infrastructure failure to `completed`. For a syntax error, preserve SyntaxError and the student's line even though the bootstrap itself is syntactically valid.

Install a pinned base wheel into the **Python environment actually visible inside execution containers and inside the checker environment**. Installing only into an administrator's shell environment is not sufficient. Test imports in both. Do not call pip, access the network, invoke a GUI or download assets during each test. Configure system output limits to allow the selected trace budget; recognise when a lower ejudge limit wins first. No graphics, font discovery, sound devices or window servers are required.

Deliver and test the task/bootstrap/checker files as an integration example. The documentation bundle includes proposed adapter source, not a claim that a real ejudge installation has already run it. Record the tested ejudge version, Python path, package version, container settings and compiler script version in the release acceptance report.

## 11. Graphics and visual identity

### 11.1. Original design direction

Working theme: **a small maintenance robot in a modular workshop**. The robot collects crystalline components, marks inspected/repaired floor tiles with paint and navigates partition walls. This is a design brief, not a demand for a named branded character. An alternative original story is acceptable if it keeps the mechanics transparent.

Use one original top-down, roughly round or rounded-polygon body with an omnidirectional drive, an independently directed probe, a cargo port and compact interchangeable-looking tools. Relative mode enables a very obvious directional pointer. Absolute mode uses the same body with that pointer absent. Avoid a chassis whose dominant silhouette points forward even after its pointer is removed. No second character rig, alternate species or duplicated movement sprite set is needed.

Do not trace, recolour or combine the supplied Karel, robotzero or book illustrations. Do not reproduce their distinctive silhouette, facial arrangement, palette or costume. Start from new sketches. Conceptual ideas such as moving a gripper, looking toward an edge or rolling over paint are permitted design requirements; old asset geometry is not. Keep a provenance record for every delivered master and export. Do not claim a legal clearance assessment merely from this brief.

The theme must not imply new unimplemented rules. Crystals are not consumable movement energy; paint is not damage; an error is not death. No automatic rewards, unlocks, combat or explosions are required. Use a restrained high-contrast palette approved separately, rather than copying an old palette or fabricating current TLF brand colours.

### 11.2. What counts as an asset

The catalogue names **source SVG files**, not every generated direction, size or quantity. One robot master contains separately addressable parts. One controls sheet contains 12 named icons. Generated PNG exports, symbol sprites and thumbnails do not count as new independently designed source assets.

Grid lines, blank floor rectangles, text, numeric badges, turn arcs, rectangular reveal clips and camera transforms are procedural geometry. They need a documented style, but not a separate SVG file for every cell, number, direction, angle or map. A complete scene screenshot is not a runtime asset.

### 11.3. Complete required SVG inventory

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

No other character or environment artwork is required to cover the R1 mechanics. The default bare floor and grid are drawn procedurally. The quantity 0 is an absent pile, 1 is one symbol, and larger quantities are the same symbol with live text. Infinity is a live text/accessible label variant of the bag, not a new pile sprite.

### 11.4. Small art reserve, not extra R1 mechanics

| ID / file | Purpose | Limits |
|---|---|---|
| **X01** `reserve/gate.svg` | Sliding gate | Frame and sliding panel in separate groups; shown open/closed by translation. Rotate one horizontal master; no gate physics is promised in R1. |
| **X02** `reserve/switch.svg` | Push button | Base and cap in separate groups; pressed state by short translation. Mouse, touch and keyboard can later share the same semantic activation. |
| **X03** `reserve/lamp.svg` | Signal lamp | Outline and inner lens; off/on states differ in shape/detail as well as colour. Opacity/state replacement; no illumination shader. |

These three masters may be delivered in the same art work package at low incremental cost. They are not exposed as functional map elements until a later physics/input specification defines them. Their optional preview clips are sliding a panel, pressing a button and fading/replacing a lamp state. Do not inflate R1 with doors, wiring, collision timing or a second robot merely because these art files exist.

## 12. SVG construction and portable animation contract

### 12.1. Master coordinate system and parts

Use a 128×128 local SVG coordinate system for the robot and cell-scale objects. The robot rotation pivot is `(64,64)`. Canonical relative heading is north, toward decreasing local SVG y. Body geometry should stay inside a radius of approximately 42 units around the pivot, leaving room for walls and a readable current-cell badge. Tools may extend within the current cell or toward its adjacent edge as specified, not visually reach into an unrelated cell.

The robot master must contain stable groups or equivalent named parts:

| Part ID | Purpose |
|---|---|
| `body` | Neutral chassis and core silhouette. |
| `drive` | Drive ring/wheels that can animate without changing coordinates. |
| `heading` | Relative-only directional pointer. |
| `sensor` | Independent probe or sensor head. |
| `gripper-base`, `gripper-left`, `gripper-right` | Short reach and jaw opening/closing. |
| `roller` | Paint applicator. |
| `eraser` | Paint-only removal tool. |
| `cargo-hatch` | Visible point where carried crystals enter/leave. |
| `eyes`, `eyelids` | Optional simple facial expression/blink. |
| `shadow` | Grounded contact shadow; not a directional light baked into every pose. |

The manifest supplies exact anchors for `pivot`, `cargo`, `probe-origin`, `tool-mount`, `grip-contact`, `paint-contact`, `erase-contact` and a safe badge region. A group may be a fixed pose toggled by visibility rather than a deformable rig. Do not require an inverse-kinematics system or arbitrary path morphing to open a gripper.

Use nested renderer groups to separate camera, world placement, heading and local tool motion. Do not put screen-space text inside the rotating heading group. Absolute body presentation remains orientation-neutral. World and local SVG y directions must be converted explicitly; native desktop and web use the same declared anchors after conversion.

### 12.2. Allowed SVG subset

Required: `svg`, `g`, basic vector shapes and paths, fill/stroke, transforms and opacity. Simple clipping used by the renderer must have an equivalent desktop implementation. Assets must have an explicit viewBox, transparent background, bounded geometry and stable part IDs.

Do not embed raster images in SVG. Do not embed JavaScript, event handlers, external links, external fonts, `foreignObject`, imported CSS, filter-heavy glows or embedded animation timelines. Avoid nonportable gradients and masks unless an approved raster/export equivalence exists. A simple solid or layered shadow is preferable to a blur filter.

Human-language labels, `True`, `False`, `None`, numbers, coordinate labels, key names and errors are renderer-generated text. They must not be outlined into the drawings. Use system fonts through the host; font files are not part of the art handoff.

Namespace actual DOM IDs per scene instance and preserve logical part names via a manifest or `data-part`. Multiple labs on one page must not share SVG IDs, clip paths or `url(#...)` references accidentally. The asset build must inspect SVG content rather than assuming `.svg` guarantees vector-only, safe or editable content.

### 12.3. Layering and visibility

Draw ground/grid, paint, task markers, static walls, crystals, the robot and temporary action overlays in a documented order. Marker contours must remain visible above paint. Wall edges must not disappear beneath a whole-cell sprite. A current-cell crystal badge should stay readable even when the robot occupies the cell; prefer a stable small corner object/quantity placement over a sprite covering the entire cell.

Use one fixed current-cell object anchor. The animated crystal comes from that anchor, not from the neighbouring cell ahead. Inventory is a HUD element plus the cargo port on the robot; transfer animation may travel only to the port and update the HUD in synchrony. A crystal need not fly across the entire browser page to reach a distant inventory panel.

Frame `p=0` must match the displayed committed before-state. Frame `p=1` must match the prepared after-state that will be committed on successful completion. Stop before commit restores the committed before-state. Temporary sprites are removed on completion, cancellation, reset and renderer failure.

### 12.4. What an “SVG animation” means here

The runtime master is **SVG parts plus a parameterised clip definition**, not an autonomous animated SVG image with an inaccessible internal timer. Deliver named tracks with normalised progress `p ∈ [0,1]`, numeric transforms, opacity, visibility and a small number of agreed reveal/cue operations. A standalone demo can use SVG/WAAPI, but a self-running SMIL file or Lottie/video file is not the authoritative runtime representation.

Portable track primitives: translation, rotation about a declared pivot, scale, opacity, visibility, rectangular reveal/wipe, linear/polyline motion between named anchors, and renderer text/counter cues. Use a small shared easing set: linear, ease-in, ease-out, ease-in-out, defined by the same cubic Bezier parameters for web and desktop. Do not embed arbitrary JavaScript/Python expressions in track JSON. Parameters come from a validated clip-binding object.

A clip declares its assets, duration policy, accepted parameters, tracks, result-display cues, transient layers, reduced-motion behaviour and terminal cleanup. A pure evaluator or equivalent deterministic implementation must support seeking directly to any progress without depending on which previous frames were rendered. Composition reuses primitives; a sensor's boolean difference is a variant, not another character drawing.

## 13. Complete animation inventory and behaviour

### 13.1. Twenty reusable templates

Durations are proposed design defaults at 1×, not physical simulation times or measured performance. They may be tuned together during art review without changing command semantics. Waiting templates are request-controlled rather than a fixed clip that spontaneously completes.

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

### 13.2. Required outcome variants

The following combinations must be represented in the animation gallery and automated frame/behaviour tests. They reuse the templates above and do not require separate directional SVG files.

| Family | Mandatory variants |
|---|---|
| Movement | Four directions; relative preserving heading; absolute without heading; before/after near a wall; nonzero/negative world coordinates. |
| Turning | Every initial heading with left and right quarter turns; clockwise half-turn; wraparound north/west without an unintended long rotation. |
| Crystal transfer | Take/put; first/last/remaining pile; finite and infinite bag; pile on paint/target; count 1, 2 and a large count. |
| Paint | Fresh paint and repaint; with/without crystals; with/without a target; no accidental change of current cell. |
| Erase | Painted/clean; paint only removed; crystals and annotations remain. |
| Edge sensing | All relative directions and all absolute directions; True and False; exact adjacent edge; body heading unchanged. |
| Current-cell sensing | Crystal present/absent; painted/unpainted; count zero/nonzero; current-cell object anchor visible. |
| Bag sensing | Empty finite bag → `bag_empty` True; nonempty finite → False; infinite → False; count zero/positive/None. |
| Compass | Query equals/differs from actual heading; query arrow and body orientation not conflated. |
| Input | Waiting key/click/time; accepted key; accepted click with camera transform; input received during another action; exhaustion/mismatch/overflow. |
| Errors | Wall bump; missing crystal; empty bag; disallowed command; invalid argument; computation/call/trace budget; syntax/runtime error; transport error. |
| Lifecycle | Ready; neutral completed; user cancelled; trusted success; wrong result with concrete highlights. |
| Playback | Pause at several internal phases; resume; step; zero-duration/instant action; reduced motion; seek; reset; stale callback after reset. |

### 13.3. Crystal accounting and paint reveals

Crystal transfer must explain one-object movement. A suitable phase layout is reach `[0,.25]`, transfer `[.25,.70]`, deposit/settle `[.70,.85]`, retract `[.85,1]`. These are tuneable clip phases, not model commits.

During a take, the visual pile may show N−1 after pickup while the bag still shows B and one transient carried crystal is visible. After deposit it shows bag B+1. The visual sum includes that carried object; the logical state remains the pre-transaction state until commit. For put, invert the source/destination accounting. No phantom duplicate should appear as a second successful crystal. With an infinite bag, keep ∞ constant while the cell changes by one.

Show at most a small fixed number of decorative pile elements, regardless of quantity, plus a live number. Count changes are bound to transfer cues, not separate uncoordinated animations. The final state must be correct for the last crystal disappearing and for the first crystal appearing.

For paint, deploy the roller on the current cell and reveal a clipped paint patch behind it. Keep the reveal at the cell boundary, not the wall hit box. Repaint uses the same tool on an already fully painted tile; it does not add another opaque layer. Erase is the inverse paint-layer reveal with a different tool; it never removes targets or crystals.

### 13.4. Sensors teach evaluation

A sensor animation highlights the actual sampled subject and shows the literal returned Python value. A failed path predicate (`False`) is a normal result; use a boolean symbol, not the fatal error treatment. `not front_clear()` still animates the `front_clear()` result; the library must not invent a second sensor returning the negation. The editor may additionally explain the enclosing Python expression, but that is not another physical measurement.

A left/right/back check points a probe without changing heading. A cardinal check in absolute mode points in a world direction, not relative to a decorative face. Distance to the next wall is never implied: only the immediately adjacent edge is checked.

### 13.5. Accessibility, small scales and reduced motion

Every action has a concise text description; every sensor has a readable result. Do not encode state solely by hue. Maintain contrast against floor/paint and distinguish markers by outline shape. Support browser reduced-motion preference and a persistent explicit setting; desktop must expose the same option.

Reduced motion replaces nonessential travel, rotation, bounce and pulse with brief stable before/after or focus changes, but still settles the same request exactly once and displays its result. Explicit timed waits remain waits. Looping idle expression is disabled while paused, hidden or reduced-motion. Audio is not required in R1 and must not be the only signal.

At small zoom, prioritise walls, heading, the robot's cell and result text. Exact counts can be exposed in an inspector/focused cell when a label would be illegible, but the displayed number must not silently become a rounded gameplay value. Validate compositions at 32, 48, 64, 96 and 128 CSS-pixel cells, and on a high-density display. These are visual review targets, not separate hand-drawn asset sets.

## 14. Art handoff and developer deliverables

### 14.1. Separate art work package

The art team will supply the 22 required source SVG files, optional three reserve prop masters if commissioned, an art manifest, the 20 clip templates with their required variants, a browsable HTML animation gallery and derived PNG layer/atlas exports for desktop. These are the **separate promised art deliverables**, not files present in this requirements bundle.

The manifest must contain an art/schema version; original author/provenance and distribution permission metadata; per-file checksums; viewBoxes; part/symbol names; pivots and anchors; safe bounds; logical theme colour roles; and the mapping from clips to source assets and desktop exports. Unknown/missing required parts must fail validation before a classroom run.

Raster exports must retain alpha, source scale, pivot, trimmed bounds and anchor metadata. Export at suitable base sizes (for example 64, 128 and 256 physical pixels per cell) rather than requiring runtime SVG rendering. A reproducible export tool produces them from the approved SVGs. Do not include third-party font files. Gallery pages may be single HTML documents with embedded demos, but must not contain borrowed source art or hidden remote dependencies.

### 14.2. Implementation work package

Deliver the base Python wheel/sdist, optional desktop extra, web module/package, CodeMirror adapter, live bridge, renderer and clip evaluator, headless runner, strict map/goal/input parsers, compact trace writer/replayer, standard goal checker, ejudge adapter/example, and automated tests. Include English and Russian learner API documentation and setup instructions. Developer requirements remain in English.

The integration must run against a manifest-driven art provider, not hardcoded SVG path indexes. Missing production art can be an explicit developer-mode state, but loading a partial art bundle must not hang a command or silently show a wrong tool. Public R1 completion requires approved art, not only functional test shapes.

Provide a CLI with these commands:

| Command | Purpose |
|---|---|
| `python -m tlfrobot run SOURCE [--map PATH_OR_DASH] [--mode desktop\|headless\|ejudge] [--inputs PATH] [--trace PATH]` | Run source, using adjacent map.toml when no map source was specified. In desktop mode, `--trace` additionally saves a trace file. In headless/ejudge, stdout is already the trace and supplying `--trace` is a configuration error; use shell redirection. |
| `python -m tlfrobot validate MAP` | Validate and report map errors without executing code or importing GUI. |
| `python -m tlfrobot check MAP TRACE [--goal GOAL] [--inputs INPUTS]` | Replay and evaluate a trace using trusted inputs. |
| `python -m tlfrobot replay TRACE` | View the saved public world and events with no re-execution of source. |

`run_file(path, *, map_source=None, mode="desktop", inputs_path=None, trace_path=None) -> int` is the stable bootstrap entry point. A browser-specific `run_source(source, *, filename, map_source, transport)` must preserve the same semantics; it may return a structured result instead of a process status. Infrastructure configuration belongs to `tlfrobot.runtime`, not to import-star. A package-level `py.typed` marker and accurate function signatures support IDE completion.

### 14.3. Non-goals that must remain explicit

No multi-robot world, student threads, network multiplayer, physics engine, pathfinding primitive, automatic wall avoidance, coordinate getters, coloured-paint palette, consumable fuel, arbitrary map scripts, dynamically imported checker code, procedural art generator exposed to students, or self-hosted full IDE is required for R1.

A useful small browser world editor is in scope: load/save, wall drag, current robot placement, initial heading when relative, crystal counts, paint bit, tools/sensors/inputs, markers and undo/redo. It validates with the same Python parser/model and edits only stopped worlds. The desktop window needs run/replay/inspection, not a second full editor. Do not create two independent authoring grammars.

## 15. Test plan and acceptance criteria

### 15.1. Core and parser tests

Test every operation against each relevant heading/policy and capability restriction. Test finite/infinite bag behaviour, no-op paint/erase, failures without mutation, failed-session persistence, safe integer bounds and booleans incorrectly used as numbers. Test Python short-circuit evaluation and recursive/user-defined functions without language rewriting.

Map tests must cover ASCII versus equivalent structured walls, width/height 1, outer boundary closure, intervals sharing endpoints, overlapping walls, gap precedence, negative coordinates, infinite rays/lines, duplicate layers, forbidden heading/bag fields, unknown keys, malformed UTF-8 and resource limits. Verify identical normalisation on browser Python and CPython. Include cells with simultaneous paint, crystal, robot and multiple marker kinds.

### 15.2. Runtime and UI tests

A fake transport with a manually controlled completion gate must prove that the second Python command cannot begin before the first completes. Repeat for sensors and input. Test cancellation before/after commit, lost renderer, early notification, duplicate response, stale run IDs, pause/step transitions, hidden tab, failed asset load and a reset immediately followed by a new Run.

Use real browser integration tests with CodeMirror, the selected Pyodide build and required response headers, not only JavaScript mocks. Exercise source line mapping, UTF-16 conversion, map stdin EOF, stdout partial lines, keyboard focus, click-coordinate conversion after zoom/pan, queued keys during movement and a `while True: pass` Stop. Make a transport error resolve visibly rather than hang.

On desktop, test the launcher on the supported OS matrix, default map discovery from a different working directory, explicit missing paths, window lifetime after completion, graceful close, noncooperative student termination and repeated runs without leaked processes. Test headless startup with no display/audio environment and no installed pygame.

### 15.3. Cross-backend and checker tests

The deterministic examples must produce equivalent normalised traces/final states in CPython headless and Pyodide; exact drawing frame times are not compared. Scripted interaction must return the same Python values on browser, desktop and headless. Explicit wait time must agree even when wall-clock display speed differs.

Checker adversarial tests must include forged final state, forged sensor result, skipped/duplicated call ID, invalid JSON type, oversized line, duplicate key, nonfinite number, extra records after end, missing start/end, malformed output text, disabled command, illegal movement, terminal error followed by claimed success, counterfeit input and unchanged/partial paths for coverage tasks. The start cell counts as visited. An empty program cannot pass an all-reachable task unless the reachable component really is only the starting cell and all other goals are satisfied.

Run a real ejudge smoke task using the standard build route, both a passing and failing submission, and a deliberately invalid output. Verify that the package is installed in both execution and checker containers, the private goal is absent from student runtime files, return codes map correctly, and output limits are sufficient. Also test a genuine timeout and confirm that no successful end record is invented.

### 15.4. Art and animation tests

Validate all 22 required SVG paths, 12 controls symbols, declared part IDs, manifest references and 20 clip templates. Reject embedded rasters, scripts, external references, missing viewBoxes and broken duplicate DOM IDs. Check that every public API operation and every world error has a specified visual mapping. Optional reserve assets must not accidentally add unimplemented map kinds.

For each required clip variant, capture progress 0, .25, .5, .75 and 1; compare direct seek with sequential playback. Test cardinal rotations and absolute-mode direction neutrality. Compare key desktop/web poses semantically and visually; rasterisation may differ slightly, but direction, anchors, layer order, values and outcome must not.

Confirm no leaked transient crystal or paint reveal remains after cancel/reset. Confirm a false sensor looks different from a collision, neutral completion differs from verified success, an infinite bag displays the correct Python result, and small-scale overlaps remain legible. Run all clips under reduced motion and instant-action mode and verify exactly-once request settlement.

### 15.5. Release gates

R1 is complete when a learner can use the same source in the browser, the configured local IDE launcher and ejudge; all 32 functions have documented/testing coverage; all R1 visual templates are implemented with approved original art; the live wait contract works for movement, sensing and input; replay/checking uses trusted initial state; and real integration tests are recorded.

Performance acceptance uses a declared reference machine/browser and measured limits: responsive Stop, normal 50×50 worlds, bounded work for an infinite viewport, no continuous busy spinning while idle and no monotonic memory/process growth over repeated runs. Record cold/warm start and a 100-run resource test. Optimisation must not suppress educational action visibility or weaken checker validation.

## 16. Suggested implementation sequence

First implement the pure model/parser and a controlled fake transport, with finite/plane fixtures and transaction cancellation. Next implement headless output plus independent replay/checking, ensuring model logic is not duplicated. Then demonstrate one real Pyodide `move` awaiting a DOM animation and one `wait_key` waking from a UI event, with a working Stop and the intended deployment headers.

After that connect the full API catalogue, CodeMirror and the manifest-driven animation renderer. Implement the pygame adapter using the same fixtures and transform tracks. Integrate the real ejudge bootstrap/checker and original art bundle. Finish with accessibility, world editing, gallery/export tooling, documentation and cross-backend release tests. The three reserve props do not block this sequence.

Do not postpone testing the live bridge or ejudge packaging until every illustration has been drawn. Conversely, do not declare the visual product finished while only a route logger and a static robot icon exist.

## 17. Sources and traceability

The contracts above are proposed engineering requirements. They are not claims that the linked projects already implement `tlfrobot`. External technical statements were checked against the primary sources below on 4 October 2026. Library versions and deployment behaviour must still be pinned and tested by the implementation team.

- **S01 — CodeMirror:** custom completion sources and API metadata integration. <https://codemirror.net/examples/autocompletion/>
- **S02 — Pyodide streams:** stdin/stdout/stderr hooks, byte input and EOF. <https://pyodide.org/en/stable/usage/streams.html>
- **S03 — Pyodide Workers:** module Workers and separation from DOM access. <https://pyodide.org/en/stable/usage/webworker.html>
- **S04 — MDN Atomics.wait:** blocking only in a permitted Worker context and the shared-memory condition/notification contract. <https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Atomics/wait>
- **S05 — Pyodide ffi:** `run_sync`, required stack-entry conditions and experimental status. <https://pyodide.org/en/stable/usage/api/python-api/ffi.html#pyodide.ffi.run_sync>
- **S06 — micropip:** installing supported wheels in Pyodide. <https://micropip.pyodide.org/en/stable/project/usage.html>
- **S07 — Python tomllib:** TOML 1.0 parsing from Python 3.11, input-size caution and separate writing support. <https://docs.python.org/3/library/tomllib.html>
- **S08 — MDN Animation.finished:** the animation completion Promise. <https://developer.mozilla.org/en-US/docs/Web/API/Animation/finished>
- **S09 — MDN Animation.cancel:** cancellation rejects the current finished Promise. <https://developer.mozilla.org/en-US/docs/Web/API/Animation/cancel>
- **S10 — Pyodide interrupts:** interrupt buffer and interruptible JavaScript waits. <https://pyodide.org/en/stable/usage/keyboard-interrupts.html>
- **S11 — pygame-ce image:** SVG rasterisation, limited SVG support and Surface representation. <https://pyga.me/docs/ref/image.html>
- **S12 — ejudge 3.13.0 release notes:** run properties and improved incomplete-program support. <https://ejudge.ru/wiki/index.php/Изменения_в_версии_3.13.0>
- **S13 — ejudge incomplete programs:** extra source directory and Python build variables. <https://ejudge.ru/wiki/index.php/Задачи_на_неполные_программы>
- **S14 — ejudge checker arguments:** trusted input, contestant output and optional answer file. <https://ejudge.ru/wiki/index.php/Параметры_командной_строки_проверяющей_программы>
- **S15 — ejudge checker exit codes:** accepted, WA, PE and checker failure. <https://ejudge.ru/wiki/index.php/Коды_завершения_проверяющей_программы>
- **S16 — ejudge checker execution:** when checking is invoked and the ability to use a command-line Python checker. <https://ejudge.ru/wiki/index.php/Проверяющие_программы>
- **S17 — official ejudge repository:** deployment source reference supplied by the user; accessible repository metadata and scripting build support were consulted. <https://github.com/blackav/ejudge>

Project inputs: `tlfrobot-spec-v1.md`, `tlfrobot-live-execution-addendum.md`, `robotzero-review.html`, the provided `programming-high-school.zip`, the Karel task collection and `Programming_intro.pdf`. The earlier API, map conventions and live-execution decision are retained where stated. This revision makes the R1 scope, compact trace, default map discovery, input functions and original-art handoff explicit. No supplied character SVG is incorporated into the new art catalogue.

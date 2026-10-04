# tlfrobot

A grid robot for learning Python. One engine runs a student's program in the
browser (Pyodide, live animation), in the terminal and on ejudge, where a
checker replays the run from the trusted world.

```python
from tlfrobot import *

while front_clear():
    move()
take()
```

- `src/tlfrobot/` — the library: maps, rules, runtime, trace, checking.
- `web/` — the browser runtime and renderer (Timo art from `art/workshop/`).
- `docs/` — the R1 requirements and the art brief; `docs/sources/` the task collections.

```sh
python -m tlfrobot run solution.py            # uses map.toml next to it; prints the trace
python -m tlfrobot check map.toml trace.jsonl # replays it and checks the goal
python -m tlfrobot validate map.toml
```

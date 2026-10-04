/**
 * The robot's Python, in a module worker. Pyodide comes from the course's own
 * `s/pyrun/boot.js` (one pinned version for every worker in the course), the
 * library from its wheel beside flake8's.
 *
 * A robot call is synchronous for the student: Python calls `tlfrobotPerform`,
 * which posts the prepared call to the page and then blocks on the shared
 * mailbox until the page has animated it (or Stop cancelled it).
 *
 * main -> worker: {type:'init', mailbox, interrupt}
 *                 {type:'parse', id, maps: string[], goals: (string|null)[]}
 *                 {type:'run', runId, source, map, goal}
 * worker -> main: {type:'ready', version} | {type:'failed', error}
 *                 {type:'parsed', id, results}
 *                 {type:'request', runId, req} | {type:'out', runId, text}
 *                 {type:'done', runId, result}
 */
import { MB, STATUS } from "./types";

declare const __TLFROBOT_VERSION__: string;
const VERSION = __TLFROBOT_VERSION__;
const BOOT_URL = new URL("../pyrun/boot.js", import.meta.url).href;
const WHEEL_URL = new URL(`../pyodide/wheels/tlfrobot-${VERSION}-py3-none-any.whl`, import.meta.url).href;

const GLUE = `
import json
import js
from tlfrobot import maps, runtime, checking, __version__
from tlfrobot.errors import MapError


def _perform(request):
    return js.tlfrobotPerform(json.dumps(request))


def parse(map_texts, goal_texts):
    out = []
    for text, goal in zip(map_texts, goal_texts):
        try:
            world = maps.loads_world(text, path="world")
            if goal:
                maps.loads_goal(goal, world, path="goal")
            out.append({"ok": True, "world": world.normalised(),
                        "hasGoal": bool(goal) or world.goal is not None})
        except MapError as e:
            out.append({"ok": False, "error": e.message})
    return json.dumps(out)


def run(source, map_text, goal_text):
    try:
        world = maps.loads_world(map_text, path="world")
        goal = maps.loads_goal(goal_text, world, path="goal") if goal_text else world.goal
    except MapError as e:
        return json.dumps({"status": "map_error", "error": e.as_json(), "calls": 0, "state": None, "verdict": None})
    res = runtime.run_source(source, world, transport=runtime.CallbackTransport(_perform),
                             keep_records=True, capture_output=False)
    verdict = None
    if goal is not None and res.status == "completed":
        verdict = checking.check_records(world, res.records, goal).as_json()
    return json.dumps({"status": res.status, "error": res.error, "calls": res.calls,
                       "state": res.state.compact(), "verdict": verdict})
`;

let pyodide: any = null;
let mailbox: Int32Array;
let interrupt: Int32Array | null = null;
let currentRun = 0;
let out = "";
const decoder = new TextDecoder();

function flush(): void {
  if (out) {
    postMessage({ type: "out", runId: currentRun, text: out });
    out = "";
  }
}

(self as any).tlfrobotPerform = (json: string): string => {
  flush();
  const req = JSON.parse(json);
  postMessage({ type: "request", runId: currentRun, req });
  for (;;) {
    if (Atomics.load(mailbox, MB.CANCEL) === 1) return "cancelled";
    const seq = Atomics.load(mailbox, MB.SEQ);
    if (seq === req.n && Atomics.load(mailbox, MB.RUN) === currentRun) {
      return Atomics.load(mailbox, MB.STATUS) === STATUS.CANCELLED ? "cancelled" : "completed";
    }
    // Timed: a missed notify can only cost 100 ms, never a hang.
    Atomics.wait(mailbox, MB.SEQ, seq, 100);
  }
};

async function init(msg: any): Promise<void> {
  mailbox = new Int32Array(msg.mailbox);
  interrupt = msg.interrupt ? new Int32Array(msg.interrupt) : null;
  const { boot } = await import(/* @vite-ignore */ BOOT_URL);
  pyodide = await boot({ interrupt });
  await pyodide.loadPackage(WHEEL_URL);
  pyodide.setStdout({ write: (buf: Uint8Array) => { out += decoder.decode(buf, { stream: true }); return buf.length; } });
  pyodide.setStderr({ write: (buf: Uint8Array) => { out += decoder.decode(buf, { stream: true }); return buf.length; } });
  pyodide.setStdin({ stdin: () => null });
  pyodide.runPython(GLUE);
  const version = pyodide.runPython("__version__");
  if (version !== VERSION) throw new Error(`tlfrobot wheel ${version} does not match the web build ${VERSION}`);
  postMessage({ type: "ready", version });
}

self.onmessage = async (event: MessageEvent) => {
  const msg = event.data;
  try {
    if (msg.type === "init") {
      await init(msg);
    } else if (msg.type === "parse") {
      const parse = pyodide.globals.get("parse");
      const json = parse(msg.maps, msg.goals);
      parse.destroy();
      postMessage({ type: "parsed", id: msg.id, results: JSON.parse(json) });
    } else if (msg.type === "run") {
      currentRun = msg.runId;
      out = "";
      if (interrupt) interrupt[0] = 0;
      const run = pyodide.globals.get("run");
      let result;
      try {
        result = JSON.parse(run(msg.source, msg.map, msg.goal ?? null));
      } catch (e: any) {
        // KeyboardInterrupt outside a robot call (Stop during pure computation)
        // arrives here when the student's code itself is interrupted.
        const text = String(e?.message ?? e);
        result = text.includes("KeyboardInterrupt")
          ? { status: "cancelled", error: null, calls: 0, state: null, verdict: null }
          : { status: "crashed", error: { code: "RUNTIME_FAILURE", message: text }, calls: 0, state: null, verdict: null };
      } finally {
        run.destroy();
      }
      flush();
      postMessage({ type: "done", runId: msg.runId, result });
    }
  } catch (e: any) {
    if (msg.type === "init") postMessage({ type: "failed", error: String(e?.message ?? e) });
    else postMessage({ type: "done", runId: msg.runId, result: {
      status: "crashed", error: { code: "RUNTIME_FAILURE", message: String(e?.message ?? e) }, calls: 0, state: null, verdict: null } });
  }
};

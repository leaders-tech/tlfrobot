/**
 * RobotLab: a scene plus the Python that drives it. The page owns the controls;
 * this owns the protocol — requests are animated one at a time, answered
 * through the shared mailbox, and Stop always ends a run, by cancelling the
 * pending call, interrupting a computation, or as a last resort replacing the
 * worker.
 */
import { play, type Playback, Scene, type SceneOptions } from "./scene";
import { type Cell, MB, type ParsedWorld, type Request, type RunResult, STATUS, type World } from "./types";

const STOP_GRACE_MS = 1500;

export function support(): { ok: true } | { ok: false; reason: string } {
  if (typeof Worker !== "function") return { ok: false, reason: "this browser has no Web Workers" };
  if (typeof SharedArrayBuffer !== "function" || !(globalThis as any).crossOriginIsolated) {
    return { ok: false, reason: "this page is not cross-origin isolated, so the robot cannot wait for its animations" };
  }
  return { ok: true };
}

// ---------------------------------------------------------------------- host

type RunHandlers = { request(req: Request): void; out(text: string): void; done(result: RunResult): void };

/** One Pyodide worker per page, shared by every lab and picture on it. */
class Host {
  private worker: Worker | null = null;
  private ready: Promise<void> | null = null;
  // Shared memory exists only on a cross-origin isolated page. Without it the
  // worker can still parse worlds (pictures on a course page); runs refuse.
  private shared = support().ok;
  mailbox = new Int32Array(this.shared ? new SharedArrayBuffer(MB.LENGTH * 4) : new ArrayBuffer(MB.LENGTH * 4));
  interrupt = new Int32Array(this.shared ? new SharedArrayBuffer(4) : new ArrayBuffer(4));
  private nextId = 1;
  private parses = new Map<number, (r: ParsedWorld[]) => void>();
  private runs = new Map<number, RunHandlers>();
  private lock: Promise<void> = Promise.resolve();
  version = "";

  constructor(private workerUrl: URL) {}

  start(): Promise<void> {
    if (this.ready) return this.ready;
    this.ready = new Promise((resolve, reject) => {
      const w = new Worker(this.workerUrl, { type: "module" });
      this.worker = w;
      w.onmessage = (e) => {
        const m = e.data;
        if (m.type === "ready") { this.version = m.version; resolve(); }
        else if (m.type === "failed") { this.ready = null; reject(new Error(m.error)); }
        else if (m.type === "parsed") { this.parses.get(m.id)?.(m.results); this.parses.delete(m.id); }
        else if (m.type === "request") this.runs.get(m.runId)?.request(m.req);
        else if (m.type === "out") this.runs.get(m.runId)?.out(m.text);
        else if (m.type === "done") { const h = this.runs.get(m.runId); this.runs.delete(m.runId); h?.done(m.result); }
      };
      w.onerror = (e) => { this.ready = null; reject(new Error(e.message || "the robot worker failed to start")); };
      w.postMessage({ type: "init", mailbox: this.mailbox.buffer, interrupt: this.interrupt.buffer });
    });
    return this.ready;
  }

  /** Serialise: a running program blocks the worker. */
  private exclusive<T>(fn: () => Promise<T>): Promise<T> {
    const result = this.lock.then(fn, fn);
    this.lock = result.then(() => undefined, () => undefined);
    return result;
  }

  parse(maps: string[], goals: (string | null)[]): Promise<ParsedWorld[]> {
    return this.exclusive(async () => {
      await this.start();
      const id = this.nextId++;
      return new Promise<ParsedWorld[]>((resolve) => {
        this.parses.set(id, resolve);
        this.worker!.postMessage({ type: "parse", id, maps, goals });
      });
    });
  }

  run(source: string, map: string, goal: string | null, handlers: RunHandlers): { runId: number; finished: Promise<RunResult> } {
    const runId = this.nextId++;
    const why = support();
    if (!why.ok) {
      const result: RunResult = { status: "crashed", error: { code: "RUNTIME_FAILURE", message: why.reason }, calls: 0, state: null, verdict: null };
      queueMicrotask(() => handlers.done(result));
      return { runId, finished: Promise.resolve(result) };
    }
    const finished = this.exclusive(async () => {
      await this.start();
      Atomics.store(this.mailbox, MB.SEQ, 0);
      Atomics.store(this.mailbox, MB.CANCEL, 0);
      Atomics.store(this.mailbox, MB.RUN, runId);
      Atomics.store(this.interrupt, 0, 0);
      return new Promise<RunResult>((resolve) => {
        this.runs.set(runId, { ...handlers, done: (r) => { handlers.done(r); resolve(r); } });
        this.worker!.postMessage({ type: "run", runId, source, map, goal });
      });
    });
    return { runId, finished };
  }

  respond(runId: number, n: number, status: number): void {
    if (Atomics.load(this.mailbox, MB.RUN) !== runId) return;
    Atomics.store(this.mailbox, MB.STATUS, status);
    Atomics.store(this.mailbox, MB.SEQ, n);
    Atomics.notify(this.mailbox, MB.SEQ);
  }

  cancel(runId: number, computing: boolean): void {
    if (Atomics.load(this.mailbox, MB.RUN) !== runId) return;
    Atomics.store(this.mailbox, MB.CANCEL, 1);
    Atomics.notify(this.mailbox, MB.SEQ);
    if (computing) Atomics.store(this.interrupt, 0, 2); // SIGINT for a loop that makes no robot calls
  }

  /** The worker did not stop in time: replace it and end the run as cancelled. */
  kill(runId: number): void {
    const h = this.runs.get(runId);
    this.runs.delete(runId);
    this.worker?.terminate();
    this.worker = null;
    this.ready = null;
    h?.done({ status: "cancelled", error: null, calls: 0, state: null, verdict: null });
  }
}

let shared: Host | null = null;

export function host(workerUrl?: URL): Host {
  if (!shared) shared = new Host(workerUrl ?? new URL("./worker.js", import.meta.url));
  return shared;
}

// ---------------------------------------------------------------------- lab

export type LabWorld = { label: string; map: string; goal?: string | null };
export type LabState = "idle" | "loading" | "running" | "paused" | "done";
type Events = {
  state: (s: LabState) => void;
  call: (req: Request, phase: "start" | "end") => void;
  output: (text: string) => void;
  done: (r: RunResult) => void;
};

export class RobotLab {
  readonly scene: Scene;
  private host: Host;
  private worlds: LabWorld[] = [];
  private parsed: ParsedWorld[] = [];
  private index = 0;
  private listeners: { [K in keyof Events]: Events[K][] } = { state: [], call: [], output: [], done: [] };
  private runId = 0;
  private queue: Request[] = [];
  private playing: Playback | null = null;
  private pumping = false;
  private stepping = false;
  private stepToken = false;
  private stopping: ReturnType<typeof setTimeout> | null = null;
  state: LabState = "idle";
  speed = 1;

  constructor(container: Element, options: SceneOptions & { workerUrl?: URL } = {}) {
    this.scene = new Scene(container, options);
    this.host = host(options.workerUrl);
  }

  on<K extends keyof Events>(event: K, fn: Events[K]): () => void {
    this.listeners[event].push(fn);
    return () => { this.listeners[event] = this.listeners[event].filter((f) => f !== fn) as any; };
  }

  private emit<K extends keyof Events>(event: K, ...args: Parameters<Events[K]>): void {
    for (const fn of this.listeners[event]) (fn as any)(...args);
  }

  private setState(s: LabState): void {
    this.state = s;
    this.emit("state", s);
  }

  /** Parse every world with the library itself (one parser, never a JS copy). */
  async load(worlds: LabWorld[]): Promise<ParsedWorld[]> {
    this.worlds = worlds;
    this.setState("loading");
    this.parsed = await this.host.parse(worlds.map((w) => w.map), worlds.map((w) => w.goal ?? null));
    this.setState("idle");
    this.select(Math.min(this.index, worlds.length - 1));
    return this.parsed;
  }

  get worldCount(): number { return this.worlds.length; }
  get selected(): number { return this.index; }
  parsedWorld(i: number): ParsedWorld | undefined { return this.parsed[i]; }

  select(i: number): void {
    if (this.state === "running" || this.state === "paused") this.stop();
    this.index = Math.max(0, i);
    const p = this.parsed[this.index];
    if (p?.ok) {
      this.scene.setWorld(p.world);
      this.scene.setStatus(null);
    }
  }

  get world(): World | null {
    const p = this.parsed[this.index];
    return p?.ok ? p.world : null;
  }

  /** Run `source` on the selected world; `paused` starts it in step mode. */
  async run(source: string, options: { paused?: boolean } = {}): Promise<RunResult> {
    if (this.state === "running" || this.state === "paused") this.stop();
    this.stepping = !!options.paused;
    const w = this.worlds[this.index];
    if (!w || !this.parsed[this.index]?.ok) throw new Error("no valid world selected");
    this.scene.reset();
    this.queue = [];
    this.playing = null;
    this.stepToken = false;
    this.setState(this.stepping ? "paused" : "running");
    const { runId, finished } = this.host.run(source, w.map, w.goal ?? null, {
      request: (req) => { if (runId === this.runId) { this.queue.push(req); void this.pump(); } },
      out: (text) => { if (runId === this.runId) this.emit("output", text); },
      done: (r) => { if (runId === this.runId) this.finish(r); },
    });
    this.runId = runId;
    return finished;
  }

  private async pump(): Promise<void> {
    if (this.pumping) return;
    this.pumping = true;
    try {
      while (this.queue.length && (this.state === "running" || this.state === "paused")) {
        if (this.stepping && !this.stepToken) { this.setState("paused"); return; }
        this.stepToken = false;
        const req = this.queue.shift()!;
        const runId = this.runId;
        this.emit("call", req, "start");
        this.playing = play(this.scene, req, this.speed);
        try {
          await this.playing.finished;
        } catch {
          return; // cancelled: Stop has already answered the worker
        }
        if (runId !== this.runId) return;
        this.playing = null;
        this.scene.commit(req);
        this.host.respond(runId, req.n, STATUS.COMPLETED);
        this.emit("call", req, "end");
      }
    } finally {
      this.pumping = false;
    }
  }

  pause(): void {
    if (this.state !== "running") return;
    this.stepping = true;
    this.playing?.pause();
    this.setState("paused");
  }

  resume(): void {
    this.stepping = false;
    if (this.state === "paused") {
      this.setState("running");
      this.playing?.resume();
      void this.pump();
    }
  }

  /** Finish the call on screen, or let exactly the next one through. */
  step(): void {
    this.stepping = true;
    if (this.state !== "running" && this.state !== "paused") return;
    if (this.playing && !this.playing.done) { this.playing.resume(); return; }
    this.stepToken = true;
    this.setState("paused");
    void this.pump();
  }

  setSpeed(speed: number): void {
    this.speed = speed;
  }

  stop(): void {
    if (this.state !== "running" && this.state !== "paused") return;
    const runId = this.runId;
    const waiting = this.playing !== null || this.queue.length > 0;
    this.playing?.cancel();
    this.playing = null;
    this.queue = [];
    this.host.cancel(runId, !waiting);
    this.stopping = setTimeout(() => { if (this.runId === runId && this.state !== "done") this.host.kill(runId); }, STOP_GRACE_MS);
  }

  reset(): void {
    this.stop();
    this.scene.reset();
    this.setState("idle");
  }

  private finish(r: RunResult): void {
    if (this.stopping) { clearTimeout(this.stopping); this.stopping = null; }
    this.queue = [];
    this.playing = null;
    const text: Record<string, string> = {
      completed: "Program finished", error: "Stopped by an error", cancelled: "Stopped", limit: "Limit reached",
      map_error: "Invalid world", crashed: "Runtime failure",
    };
    if (r.verdict && r.status === "completed") {
      const ok = r.verdict.verdict === "accepted";
      this.scene.setStatus({ kind: ok ? "success" : "error", text: ok ? "Goal reached" : "Goal not reached" });
      const cells = ((r.verdict.details?.mismatches as any[]) ?? [])
        .map((m) => m.cell ?? (m.what === "robot_at" ? m.expected : null)).filter(Boolean) as Cell[];
      if (!ok) this.scene.markCells(cells);
    } else {
      this.scene.setStatus({ kind: r.status === "completed" ? "completed" : "error", text: text[r.status] ?? r.status });
    }
    this.setState("done");
    this.emit("done", r);
  }

  destroy(): void {
    this.stop();
    this.scene.destroy();
  }
}

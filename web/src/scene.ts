/**
 * The world on screen. A read-only projection of what Python committed: the
 * scene never decides whether a move is legal, it draws the facts (`fx`) a
 * prepared call carries.
 *
 * Every clip is a pure function of its request and a progress p in [0, 1]
 * (`frame`), so it can be paused, sought or cancelled at any point: p = 0 is
 * the committed state before the call, p = 1 the state the call will commit.
 */
import clips from "../../art/workshop/animation/clips.json";
import { anchor, el, mount, type Mounted, NS, PALETTE, Symbols } from "./art";
import type { Cell, Request, World } from "./types";

const CELL = 128;
const PAD = 28;
const HUD = 104;
const DIR_ANGLE: Record<string, number> = { north: 0, east: 90, south: 180, west: 270 };
const STEP: Record<string, Cell> = { north: [0, 1], east: [1, 0], south: [0, -1], west: [-1, 0] };

const clamp = (x: number) => Math.min(1, Math.max(0, x));
const smooth = (x: number) => { x = clamp(x); return x * x * (3 - 2 * x); };
const phase = (p: number, a: number, b: number) => smooth((p - a) / (b - a));
const pulse = (p: number) => Math.sin(Math.PI * clamp(p));
const key = (c: Cell) => `${c[0]},${c[1]}`;

type ClipInfo = { id: string; key: string; duration_ms: string };
const CLIP = Object.fromEntries((clips.items as ClipInfo[]).map((c) => [c.key, c]));

const ERROR_LABEL: Record<string, string> = {
  WALL_COLLISION: "Wall!",
  NO_CRYSTAL: "No crystal here",
  EMPTY_BAG: "The bag is empty",
  COMMAND_UNAVAILABLE: "Not available",
  SESSION_FAILED: "Stopped",
  CALL_LIMIT: "Too many calls",
  STATE_LIMIT: "Too many cells",
  NUMBER_RANGE: "Too far",
};

export function errorLabel(code: string): string {
  return ERROR_LABEL[code] ?? code;
}

export function clipFor(req: Request): string {
  if (req.error) {
    const code = req.error.code;
    if (code === "WALL_COLLISION") return "error.wall";
    if (code === "NO_CRYSTAL" || code === "EMPTY_BAG") return "error.object";
    return "error.status";
  }
  const op = req.op;
  if (op === "move" || op === "north" || op === "south" || op === "east" || op === "west") return "move.step";
  if (op.startsWith("turn_")) return "turn";
  if (op === "take" || op === "put") return "crystal.transfer";
  if (op === "paint") return "paint.apply";
  if (op === "erase") return "paint.erase";
  if (op.endsWith("_clear")) return "sense.edge";
  if (op.startsWith("facing_")) return "sense.heading";
  if (op === "bag_empty" || op === "bag_count") return "sense.bag";
  return "sense.cell";
}

export function durationFor(req: Request): number {
  const clip = clipFor(req);
  let ms = Number(CLIP[clip]?.duration_ms ?? 200);
  if (clip === "turn" && req.op === "turn_around") ms = 360;
  if (clip === "paint.apply" && !req.fx.fresh) ms = 180;
  if (clip === "paint.erase" && !req.fx.had) ms = 180;
  return ms;
}

export function pyRepr(v: unknown): string {
  if (v === true) return "True";
  if (v === false) return "False";
  if (v === null || v === undefined) return "None";
  return String(v);
}

type CrystalNodes = { g: SVGGElement; use: SVGUseElement; badge: SVGGElement; text: SVGTextElement };

export type SceneOptions = { reducedMotion?: boolean; hud?: boolean };

export class Scene {
  readonly svg: SVGSVGElement;
  private defs: SVGDefsElement;
  private symbols: Symbols;
  private layers!: Record<string, SVGGElement>;
  private world!: World;
  private view = { x0: 0, y0: 0, w: 1, h: 1 };
  // the committed state, as the scene shows it
  private at: Cell = [0, 0];
  private heading: string | null = null;
  private bag: number | "infinite" | null = null;
  private crystals = new Map<string, number>();
  private painted = new Set<string>();
  private markers = new Map<string, string[]>();
  // nodes
  private actor!: SVGGElement;
  private robot!: Mounted;
  private arm: SVGPathElement[] = [];
  private claw!: SVGGElement;
  private carried!: SVGUseElement;
  private crystalNodes = new Map<string, CrystalNodes>();
  private paintNodes = new Map<string, SVGUseElement>();
  private wipeRect!: SVGRectElement;
  private wipeClipId = "";
  private fx!: Record<string, SVGElement>;
  private hud!: { bagText: SVGTextElement; bagIcon: Mounted | null; bagRing: SVGElement; compass: Mounted | null;
    compassRing: SVGElement; callText: SVGTextElement; statusIcons: Record<string, SVGElement>; statusText: SVGTextElement };
  private bubble!: { g: SVGGElement; rect: SVGRectElement; text: SVGTextElement; icons: Record<string, SVGElement> };
  private verdictMarks: SVGElement[] = [];
  /** cells a clip frame changed, to put back at the next frame */
  private touchedCrystals = new Set<string>();
  private touchedPaint = new Set<string>();
  reducedMotion: boolean;
  private showHud: boolean;

  constructor(container: Element, options: SceneOptions = {}) {
    this.reducedMotion = options.reducedMotion ??
      (typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches);
    this.showHud = options.hud ?? true;
    this.svg = el("svg", { role: "img", class: "tlfrobot-scene" });
    this.svg.style.display = "block";
    this.svg.style.width = "100%";
    this.svg.style.height = "auto";
    this.defs = el("defs", {}, this.svg);
    this.symbols = new Symbols(this.defs);
    container.appendChild(this.svg);
  }

  // ------------------------------------------------------------------ layout

  setWorld(world: World): void {
    this.world = world;
    this.at = [...world.robot.at] as Cell;
    this.heading = world.robot.heading;
    this.bag = world.robot.bag;
    this.crystals = new Map(world.cells.crystals.map((c) => [key(c.at), c.count]));
    this.painted = new Set(world.cells.painted.map(key));
    this.markers = new Map();
    for (const m of world.presentation.markers) {
      const k = key(m.at);
      this.markers.set(k, [...(this.markers.get(k) ?? []), m.kind]);
    }
    const b = world.board;
    if (b.topology === "bounded") {
      this.view = { x0: b.origin![0], y0: b.origin![1], w: b.size![0], h: b.size![1] };
    } else {
      const [x0, y0, w, h] = world.presentation.viewport ?? [this.at[0] - 4, this.at[1] - 3, 9, 7];
      this.view = { x0, y0, w, h };
    }
    this.svg.setAttribute("aria-label", world.title ?? world.id);
    this.layout();
  }

  private px(x: number) { return (x - this.view.x0) * CELL + PAD; }
  private py(y: number) { return (this.view.y0 + this.view.h - 1 - y) * CELL + PAD + (this.showHud ? HUD : 0); }

  private layout(): void {
    for (const n of Array.from(this.svg.childNodes)) if (n !== this.defs) this.svg.removeChild(n);
    while (this.defs.firstChild) this.defs.removeChild(this.defs.firstChild);
    this.symbols = new Symbols(this.defs);
    const { w, h } = this.view;
    const width = w * CELL + 2 * PAD;
    const height = h * CELL + 2 * PAD + (this.showHud ? HUD : 0);
    this.svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    const names = ["floor", "paint", "markers", "walls", "crystals", "actor", "fx", "hud"];
    this.layers = Object.fromEntries(names.map((n) => [n, el("g", { "data-layer": n }, this.svg)]));
    this.wipeClipId = `tlfrobot-wipe-${Math.random().toString(36).slice(2)}`;
    const clip = el("clipPath", { id: this.wipeClipId, clipPathUnits: "userSpaceOnUse" }, this.defs);
    this.wipeRect = el("rect", { x: 0, y: 0, width: 0, height: CELL }, clip);
    this.drawFloor();
    this.drawWalls();
    this.paintNodes.clear();
    for (const k of this.painted) this.drawPaint(k);
    for (const [k, kinds] of this.markers) for (const kind of kinds) this.drawMarker(k, kind);
    this.crystalNodes.clear();
    this.touchedCrystals = new Set();
    this.touchedPaint = new Set();
    for (const [k, n] of this.crystals) this.drawCrystal(k, n);
    this.drawActor();
    this.drawFx();
    if (this.showHud) this.drawHud();
    this.restPose();
  }

  private inView(c: Cell) {
    const v = this.view;
    return c[0] >= v.x0 && c[0] < v.x0 + v.w && c[1] >= v.y0 && c[1] < v.y0 + v.h;
  }

  private drawFloor(): void {
    const g = this.layers.floor;
    const v = this.view;
    const tint: Record<string, string> = { finish: "#FDF1D6", target: "#E9EFF2" };
    for (let y = v.y0; y < v.y0 + v.h; y++) {
      for (let x = v.x0; x < v.x0 + v.w; x++) {
        const kinds = this.markers.get(key([x, y])) ?? [];
        const fill = kinds.includes("finish") ? tint.finish : kinds.includes("target") ? tint.target
          : (x + y) % 2 ? "#F5F7F5" : "#FBFCF9";
        el("rect", { x: this.px(x), y: this.py(y), width: CELL, height: CELL, fill, stroke: "#D8E2E4", "stroke-width": 1 }, g);
        el("circle", { cx: this.px(x) + 64, cy: this.py(y) + 64, r: 2, fill: "#CAD8DD" }, g);
      }
    }
    if (this.world.presentation.show_coordinates) {
      const style = { "font-size": 22, "font-family": "system-ui, sans-serif", fill: PALETTE.muted, "text-anchor": "middle" };
      for (let x = v.x0; x < v.x0 + v.w; x++) {
        const t = el("text", { x: this.px(x) + 64, y: this.py(v.y0) + CELL + 24, ...style }, g);
        t.textContent = String(x);
      }
      for (let y = v.y0; y < v.y0 + v.h; y++) {
        const t = el("text", { x: PAD / 2, y: this.py(y) + 72, ...style }, g);
        t.textContent = String(y);
      }
    }
  }

  private edges(): { axis: "h" | "v"; at: number; k: number }[] {
    const v = this.view;
    const out: { axis: "h" | "v"; at: number; k: number }[] = [];
    const lim = (s: number | string, lo: number, hi: number, low: boolean) => {
      if (s === "-inf") return lo;
      if (s === "+inf") return hi;
      return low ? Math.max(Number(s), lo) : Math.min(Number(s), hi);
    };
    for (const wall of this.world.board.walls) {
      const [lo, hi] = wall.axis === "h" ? [v.x0, v.x0 + v.w] : [v.y0, v.y0 + v.h];
      const [llo, lhi] = wall.axis === "h" ? [v.y0, v.y0 + v.h] : [v.x0, v.x0 + v.w];
      if (wall.at < llo || wall.at > lhi) continue;
      const a = lim(wall.span[0], lo, hi, true);
      const b = lim(wall.span[1], lo, hi, false);
      for (let k = a; k < b; k++) out.push({ axis: wall.axis, at: wall.at, k });
    }
    if (this.world.board.topology === "bounded") {
      for (let x = v.x0; x < v.x0 + v.w; x++) out.push({ axis: "h", at: v.y0, k: x }, { axis: "h", at: v.y0 + v.h, k: x });
      for (let y = v.y0; y < v.y0 + v.h; y++) out.push({ axis: "v", at: v.x0, k: y }, { axis: "v", at: v.x0 + v.w, k: y });
    }
    return out;
  }

  private drawWalls(): void {
    const g = this.layers.walls;
    const deg = new Map<string, Set<string>>();
    const touch = (vx: number, vy: number, d: string) => {
      const k = `${vx},${vy}`;
      if (!deg.has(k)) deg.set(k, new Set());
      deg.get(k)!.add(d);
    };
    for (const e of this.edges()) {
      if (e.axis === "h") {
        const X = this.px(e.k), Y = this.py(e.at) + CELL;
        this.symbols.use("world/wall.svg", g, X, Y - 12, CELL, 24);
        touch(e.k, e.at, "E");
        touch(e.k + 1, e.at, "W");
      } else {
        const X = this.px(e.at), Y = this.py(e.k);
        const grp = el("g", { transform: `translate(${X + 12} ${Y}) rotate(90)` }, g);
        this.symbols.use("world/wall.svg", grp, 0, 0, CELL, 24);
        touch(e.at, e.k, "N");
        touch(e.at, e.k + 1, "S");
      }
    }
    for (const [k, dirs] of deg) {
      const straight = dirs.size === 2 && ((dirs.has("E") && dirs.has("W")) || (dirs.has("N") && dirs.has("S")));
      if (straight) continue;
      const [vx, vy] = k.split(",").map(Number);
      this.symbols.use("world/wall-joint.svg", g, this.px(vx) - 12, this.py(vy) + CELL - 12, 24, 24);
    }
  }

  private cellXY(k: string): Cell {
    const [x, y] = k.split(",").map(Number);
    return [x, y];
  }

  private drawPaint(k: string): void {
    const c = this.cellXY(k);
    if (!this.inView(c)) return;
    this.paintNodes.get(k)?.remove();
    this.paintNodes.set(k, this.symbols.use("world/paint.svg", this.layers.paint, this.px(c[0]), this.py(c[1]), CELL, CELL));
  }

  private drawMarker(k: string, kind: string): void {
    const c = this.cellXY(k);
    if (!this.inView(c)) return;
    this.symbols.use(`world/marker-${kind}.svg`, this.layers.markers, this.px(c[0]), this.py(c[1]), CELL, CELL);
  }

  private drawCrystal(k: string, n: number): void {
    this.crystalNodes.get(k)?.g.remove();
    this.crystalNodes.delete(k);
    const c = this.cellXY(k);
    if (n <= 0 || !this.inView(c)) return;
    const g = el("g", { transform: `translate(${this.px(c[0])} ${this.py(c[1])})` }, this.layers.crystals);
    const use = this.symbols.use("world/crystal.svg", g, 0, 0, 64, 64);
    const badge = el("g", {}, g);
    el("rect", { x: -18, y: -10, width: 36, height: 20, rx: 9, fill: PALETTE.body, stroke: PALETTE.outline, "stroke-width": 1.5 }, badge);
    const text = el("text", { x: 0, y: 6, "text-anchor": "middle", "font-size": 15, "font-weight": 700,
      "font-family": "system-ui, sans-serif", fill: PALETTE.outline }, badge);
    const nodes = { g, use, badge, text };
    this.crystalNodes.set(k, nodes);
    this.placeCrystal(k, n, key(this.at) === k ? 1 : 0);
  }

  /** t = 0: the crystal sits in the middle of its cell; t = 1: tucked into the
   *  corner anchor because the robot is standing on it. */
  private placeCrystal(k: string, n: number, t: number): void {
    const nodes = this.crystalNodes.get(k);
    if (!nodes) return;
    this.touchedCrystals.add(k);
    const [ox, oy] = anchor("robot/robot.svg", "cell_object");
    const size = 60 + (34 - 60) * t;
    const cx = 64 + (ox - 64) * t, cy = 64 + (oy - 64) * t;
    nodes.use.setAttribute("x", String(cx - size / 2));
    nodes.use.setAttribute("y", String(cy - size / 2));
    nodes.use.setAttribute("width", String(size));
    nodes.use.setAttribute("height", String(size));
    const show = n >= 2;
    nodes.badge.setAttribute("opacity", show ? "1" : "0");
    nodes.text.textContent = show ? String(n) : "";
    const bx = cx + size * 0.42, by = cy + size * 0.42;
    nodes.badge.setAttribute("transform", `translate(${bx} ${by}) scale(${1 - 0.25 * t})`);
    nodes.g.setAttribute("opacity", n > 0 ? "1" : "0");
  }

  private drawActor(): void {
    this.actor = el("g", {}, this.layers.actor);
    this.robot = mount("robot/robot.svg", this.actor);
    this.arm = [
      el("path", { fill: "none", stroke: PALETTE.outline, "stroke-width": 6, "stroke-linecap": "round" }, this.actor),
      el("path", { fill: "none", stroke: PALETTE["body-shade"], "stroke-width": 3, "stroke-linecap": "round" }, this.actor),
    ];
    this.claw = el("g", {}, this.actor);
    for (const name of ["gripper-left", "gripper-right"]) {
      const c = this.robot.parts[name].cloneNode(true) as SVGElement;
      c.removeAttribute("id");
      c.removeAttribute("data-part");
      c.setAttribute("opacity", "1");
      for (const d of c.querySelectorAll("[id]")) d.removeAttribute("id");
      this.claw.appendChild(c);
    }
    this.carried = this.symbols.use("world/crystal.svg", this.layers.fx, 0, 0, 26, 26);
  }

  private drawFx(): void {
    const g = this.layers.fx;
    g.appendChild(this.carried);
    const edge = el("line", { "stroke-width": 7, "stroke-linecap": "round" }, g);
    const pulseG = el("g", {}, g);
    mount("hints/sensor-pulse.svg", pulseG, 0, 0, 64, 64);
    const arrowG = el("g", {}, g);
    mount("hints/direction-arrow.svg", arrowG, 0, 0, 64, 64);
    const focusCell = el("g", {}, g);
    mount("hints/focus-ring.svg", focusCell, 0, 0, CELL, CELL);
    const focusSmall = el("g", {}, g);
    mount("hints/focus-ring.svg", focusSmall, 0, 0, 52, 52);
    this.fx = { edge, pulse: pulseG, arrow: arrowG, focusCell, focusSmall };
    // the value bubble next to the robot
    const bg = el("g", { "pointer-events": "none" }, g);
    const rect = el("rect", { rx: 18, fill: "#FFFFFF", stroke: PALETTE.outline, "stroke-width": 2 }, bg);
    const icons: Record<string, SVGElement> = {};
    for (const s of ["boolean-true", "boolean-false", "error"]) {
      const ig = el("g", {}, bg);
      mount(`status/${s}.svg`, ig, 0, 0, 40, 40);
      icons[s] = ig;
    }
    const text = el("text", { "font-size": 30, "font-weight": 700, "font-family": "ui-monospace, SFMono-Regular, Menlo, monospace",
      fill: PALETTE.outline, "dominant-baseline": "central" }, bg);
    this.bubble = { g: bg, rect, text, icons };
  }

  private drawHud(): void {
    const g = this.layers.hud;
    const width = this.view.w * CELL + 2 * PAD;
    el("rect", { x: PAD, y: 12, width: width - 2 * PAD, height: HUD - 24, rx: 20, fill: "#EDF3F4" }, g);
    let x = PAD + 16;
    let bagIcon: Mounted | null = null;
    const bagRing = el("g", {}, g);
    const bagText = el("text", { "font-size": 34, "font-weight": 700, "font-family": "system-ui, sans-serif",
      fill: PALETTE.outline, "dominant-baseline": "central" }, g);
    if (this.world.rules.tools.includes("crystals")) {
      bagIcon = mount("hud/bag.svg", g, x, 20, 64, 64);
      mount("hints/focus-ring.svg", bagRing, x - 10, 10, 84, 84);
      bagText.setAttribute("x", String(x + 74));
      bagText.setAttribute("y", String(52));
      x += 160;
    }
    let compass: Mounted | null = null;
    const compassRing = el("g", {}, g);
    if (this.world.rules.sensors.includes("compass")) {
      compass = mount("hud/compass.svg", g, x, 20, 64, 64);
      mount("hints/focus-ring.svg", compassRing, x - 10, 10, 84, 84);
      x += 100;
    }
    const statusIcons: Record<string, SVGElement> = {};
    for (const s of ["completed", "success", "error"]) {
      const ig = el("g", {}, g);
      mount(`status/${s}.svg`, ig, width - PAD - 70, 24, 56, 56);
      statusIcons[s] = ig;
    }
    const statusText = el("text", { x: width - PAD - 84, y: 52, "text-anchor": "end", "font-size": 28, "font-weight": 600,
      "font-family": "system-ui, sans-serif", fill: PALETTE.outline, "dominant-baseline": "central" }, g);
    const callText = el("text", { x, y: 52, "font-size": 28, "font-family": "ui-monospace, SFMono-Regular, Menlo, monospace",
      fill: PALETTE.frame, "dominant-baseline": "central" }, g);
    this.hud = { bagText, bagIcon, bagRing, compass, compassRing, callText, statusIcons, statusText };
  }

  // ------------------------------------------------------------------ poses

  private setPart(name: string, transform: string, alpha: number | null = null): void {
    const n = this.robot.parts[name];
    if (!n) return;
    if (transform) n.setAttribute("transform", transform);
    else n.removeAttribute("transform");
    if (alpha !== null) n.setAttribute("opacity", String(alpha));
  }

  private headingAngle(): number {
    return this.heading ? DIR_ANGLE[this.heading] : 0;
  }

  private placeActor(c: Cell | [number, number]): void {
    this.actor.setAttribute("transform", `translate(${this.px(c[0])} ${this.py(c[1])})`);
  }

  /** Everything transient off; the robot at rest on its committed cell. */
  private restPose(): void {
    for (const [name, b] of Object.entries(this.robot.base)) {
      if (b.transform) this.robot.parts[name].setAttribute("transform", b.transform);
      else this.robot.parts[name].removeAttribute("transform");
      this.robot.parts[name].setAttribute("opacity", b.opacity);
    }
    for (const name of ["gripper-base", "gripper-left", "gripper-right", "roller", "eraser", "eyelids"]) this.setPart(name, "", 0);
    const a = this.headingAngle();
    for (const name of ["drive", "body", "heading"]) this.setPart(name, `rotate(${a} 64 64)`, 1);
    this.robot.parts.heading?.setAttribute("opacity", this.world.rules.movement === "absolute" ? "0" : "1");
    this.setPart("sensor", "", 1);
    this.placeActor(this.at);
    for (const p of this.arm) { p.removeAttribute("d"); p.setAttribute("opacity", "0"); }
    this.claw.setAttribute("opacity", "0");
    this.carried.setAttribute("opacity", "0");
    for (const n of Object.values(this.fx)) n.setAttribute("opacity", "0");
    this.bubble.g.setAttribute("opacity", "0");
    this.wipeRect.setAttribute("width", "0");
    const here = key(this.at);
    const crystalKeys = [...this.touchedCrystals, here];
    this.touchedCrystals = new Set();
    for (const k of crystalKeys) {
      if (this.crystalNodes.has(k)) this.placeCrystal(k, this.crystals.get(k) ?? 0, k === here ? 1 : 0);
    }
    for (const k of this.touchedPaint) {
      const node = this.paintNodes.get(k);
      if (!node) continue;
      node.removeAttribute("clip-path");
      node.setAttribute("opacity", this.painted.has(k) ? "1" : "0");
    }
    this.touchedPaint = new Set();
    if (this.hud) {
      this.hud.bagText.textContent = this.bag === "infinite" ? "∞" : this.bag === null ? "" : String(this.bag);
      if (this.hud.bagIcon) this.hud.bagIcon.parts["bag-contents"]?.setAttribute("opacity", this.bag === 0 ? "0" : "1");
      this.hud.bagRing.setAttribute("opacity", "0");
      this.hud.compassRing.setAttribute("opacity", "0");
      if (this.hud.compass) this.hud.compass.parts["compass-pointer"]?.setAttribute("transform", `rotate(${this.headingAngle()} 32 32)`);
    }
  }

  private showBubble(text: string, icon: string | null, alpha: number, at: [number, number] = this.at): void {
    const b = this.bubble;
    b.text.textContent = text;
    const tw = Math.max(40, text.length * 18);
    const w = tw + (icon ? 60 : 28);
    const h = 56;
    const cx = this.px(at[0]) + 64;
    let top = this.py(at[1]) - h - 6;
    if (top < (this.showHud ? HUD : 0)) top = this.py(at[1]) + CELL + 6;
    const x = cx - w / 2;
    b.rect.setAttribute("x", String(x));
    b.rect.setAttribute("y", String(top));
    b.rect.setAttribute("width", String(w));
    b.rect.setAttribute("height", String(h));
    for (const [name, node] of Object.entries(b.icons)) {
      node.setAttribute("opacity", name === icon ? "1" : "0");
      node.setAttribute("transform", `translate(${x + 10} ${top + 8})`);
    }
    b.text.setAttribute("x", String(x + (icon ? 56 : 14)));
    b.text.setAttribute("y", String(top + h / 2));
    b.g.setAttribute("opacity", String(alpha));
  }

  private edgeLine(cell: Cell | [number, number], dir: string): [number, number, number, number] {
    const x = this.px(cell[0]), y = this.py(cell[1]);
    const m = 14;
    if (dir === "north") return [x + m, y, x + CELL - m, y];
    if (dir === "south") return [x + m, y + CELL, x + CELL - m, y + CELL];
    if (dir === "east") return [x + CELL, y + m, x + CELL, y + CELL - m];
    return [x, y + m, x, y + CELL - m];
  }

  private armTo(x: number, y: number, alpha: number): void {
    const [mx, my] = anchor("robot/robot.svg", "tool_mount");
    const [gx, gy] = anchor("robot/robot.svg", "grip_contact");
    const d = `M ${mx} ${my} Q ${mx + 13} ${my + 6} ${x} ${y}`;
    for (const p of this.arm) { p.setAttribute("d", d); p.setAttribute("opacity", String(alpha)); }
    this.claw.setAttribute("transform", `translate(${x - gx} ${y - gy})`);
    this.claw.setAttribute("opacity", String(alpha));
  }

  // ------------------------------------------------------------------ clips

  /** Draw `req` at progress p. Pure: depends only on (committed state, req, p). */
  frame(req: Request, p: number): void {
    p = clamp(p);
    this.restPose();
    const clip = clipFor(req);
    const fx = req.fx ?? {};
    const reduced = this.reducedMotion;
    const q = reduced ? (p >= 1 ? 1 : 0) : smooth(p);
    const shown = phase(p, 0, 0.22);
    const active = p > 0 && p < 1;
    const here = key(this.at);
    switch (clip) {
      case "move.step": {
        const from = fx.from as Cell, to = fx.to as Cell;
        const pos: [number, number] = [from[0] + (to[0] - from[0]) * q, from[1] + (to[1] - from[1]) * q];
        this.placeActor(pos);
        const fk = key(from), tk = key(to);
        if (this.crystals.has(fk)) this.placeCrystal(fk, this.crystals.get(fk)!, 1 - q);
        if (this.crystals.has(tk)) this.placeCrystal(tk, this.crystals.get(tk)!, q);
        if (this.world.rules.movement === "absolute" && active) {
          const a = DIR_ANGLE[fx.dir as string];
          this.fx.arrow.setAttribute("transform",
            `translate(${this.px(pos[0]) + 64} ${this.py(pos[1]) + 64}) rotate(${a}) translate(-24 -84) scale(0.75)`);
          this.fx.arrow.setAttribute("opacity", String(pulse(p)));
        }
        break;
      }
      case "turn": {
        const angle = Number(fx.angle);
        const a = DIR_ANGLE[fx.from as string] + angle * q;
        for (const name of ["drive", "body", "heading"]) this.setPart(name, `rotate(${a} 64 64)`, 1);
        if (this.hud?.compass) this.hud.compass.parts["compass-pointer"]?.setAttribute("transform", `rotate(${a} 32 32)`);
        break;
      }
      case "crystal.transfer": {
        const putting = req.op === "put";
        const picked = reduced ? p >= 1 : p >= 0.25;
        const deposited = reduced ? p >= 1 : p >= 0.8;
        let t = phase(p, 0.25, 0.8);
        if (putting) t = 1 - t;
        const [ox, oy] = anchor("robot/robot.svg", "cell_object");
        const [cx, cy] = anchor("robot/robot.svg", "cargo");
        const x = ox + (cx - ox) * t, y = oy + (cy - oy) * t - 8 * Math.sin(Math.PI * t);
        if (active && !reduced) this.armTo(x, y, 1);
        if (picked && !deposited) {
          this.carried.setAttribute("opacity", "1");
          this.carried.setAttribute("x", String(this.px(this.at[0]) + x - 13));
          this.carried.setAttribute("y", String(this.py(this.at[1]) + y - 13));
        }
        let cell = Number(fx.cell_before);
        let bag = fx.bag_before as number | "infinite";
        if (putting) {
          if (picked && bag !== "infinite") bag = (bag as number) - 1;
          if (deposited) cell += 1;
        } else {
          if (picked) cell -= 1;
          if (deposited && bag !== "infinite") bag = (bag as number) + 1;
        }
        this.showCellCount(here, cell);
        if (this.hud) this.hud.bagText.textContent = bag === "infinite" ? "∞" : String(bag);
        if (!reduced) this.setPart("cargo-hatch", `rotate(${-14 * pulse(p)} 64 84)`, 1);
        this.hud?.bagRing.setAttribute("opacity", String(active ? 0.5 : 0));
        break;
      }
      case "paint.apply":
      case "paint.erase": {
        const erasing = clip === "paint.erase";
        const relevant = erasing ? fx.had : fx.fresh;
        let t = phase(p, 0.15, 0.85);
        if (reduced) t = p >= 1 ? 1 : 0;
        const tool = erasing ? "eraser" : "roller";
        const contact = anchor("robot/robot.svg", erasing ? "erase_contact" : "paint_contact")[0];
        if (active && !reduced) this.setPart(tool, `translate(${28 + 78 * phase(p, 0.15, 0.85) - contact} 0)`, 1);
        if (relevant) {
          let node = this.paintNodes.get(here);
          if (!node) {
            this.drawPaint(here);
            node = this.paintNodes.get(here)!;
          }
          const X = this.px(this.at[0]), Y = this.py(this.at[1]);
          this.wipeRect.setAttribute("y", String(Y));
          if (erasing) {
            this.wipeRect.setAttribute("x", String(X + CELL * t));
            this.wipeRect.setAttribute("width", String(CELL * (1 - t)));
          } else {
            this.wipeRect.setAttribute("x", String(X));
            this.wipeRect.setAttribute("width", String(CELL * t));
          }
          node.setAttribute("clip-path", `url(#${this.wipeClipId})`);
          this.touchedPaint.add(here);
          node.setAttribute("opacity", "1");
        }
        break;
      }
      case "sense.edge": {
        const dir = fx.dir as string;
        const a = DIR_ANGLE[dir];
        const result = req.result === true;
        const [x1, y1, x2, y2] = this.edgeLine(this.at, dir);
        const e = this.fx.edge;
        e.setAttribute("x1", String(x1)); e.setAttribute("y1", String(y1));
        e.setAttribute("x2", String(x2)); e.setAttribute("y2", String(y2));
        e.setAttribute("stroke", result ? PALETTE.positive : PALETTE.frame);
        e.setAttribute("opacity", String(shown * 0.8 * (1 - phase(p, 0.85, 1))));
        if (!reduced) this.setPart("sensor", `rotate(${(a > 180 ? a - 360 : a) * phase(p, 0, 0.3) * (1 - phase(p, 0.8, 1))} 64 64)`, 1);
        this.fx.pulse.setAttribute("transform",
          `translate(${this.px(this.at[0]) + 64} ${this.py(this.at[1]) + 64}) rotate(${a}) translate(-32 -62)`);
        this.fx.pulse.setAttribute("opacity", String(active ? pulse(p) : 0));
        this.showBubble(pyRepr(req.result), result ? "boolean-true" : "boolean-false", shown);
        break;
      }
      case "sense.cell": {
        const subject = fx.subject as string;
        const ring = subject === "paint" ? this.fx.focusCell : this.fx.focusSmall;
        if (subject === "paint") {
          ring.setAttribute("transform", `translate(${this.px(this.at[0])} ${this.py(this.at[1])})`);
        } else {
          const [ox, oy] = anchor("robot/robot.svg", "cell_object");
          ring.setAttribute("transform", `translate(${this.px(this.at[0]) + ox - 26} ${this.py(this.at[1]) + oy - 26})`);
        }
        ring.setAttribute("opacity", String(shown));
        const isBool = typeof req.result === "boolean";
        this.showBubble(pyRepr(req.result), isBool ? (req.result ? "boolean-true" : "boolean-false") : null, shown);
        break;
      }
      case "sense.bag": {
        this.hud?.bagRing.setAttribute("opacity", String(shown));
        const isBool = typeof req.result === "boolean";
        this.showBubble(pyRepr(req.result), isBool ? (req.result ? "boolean-true" : "boolean-false") : null, shown);
        break;
      }
      case "sense.heading": {
        this.hud?.compassRing.setAttribute("opacity", String(shown));
        if (this.hud?.compass) {
          this.hud.compass.parts["compass-pointer"]?.setAttribute("transform", `rotate(${DIR_ANGLE[fx.query as string]} 32 32)`);
        }
        this.showBubble(pyRepr(req.result), req.result ? "boolean-true" : "boolean-false", shown);
        break;
      }
      case "error.wall": {
        const dir = fx.dir as string;
        const [dx, dy] = STEP[dir];
        const t = reduced ? 0 : 0.12 * pulse(p);
        this.placeActor([this.at[0] + dx * t, this.at[1] + dy * t]);
        const [x1, y1, x2, y2] = this.edgeLine(this.at, dir);
        const e = this.fx.edge;
        e.setAttribute("x1", String(x1)); e.setAttribute("y1", String(y1));
        e.setAttribute("x2", String(x2)); e.setAttribute("y2", String(y2));
        e.setAttribute("stroke", PALETTE.error);
        e.setAttribute("opacity", String(shown));
        this.showBubble(errorLabel(req.error!.code), "error", shown);
        break;
      }
      case "error.object": {
        const bagTarget = fx.target === "bag";
        const [ox, oy] = anchor("robot/robot.svg", "cell_object");
        if (active && !reduced) this.armTo(bagTarget ? 73 : ox, bagTarget ? 95 : oy, pulse(p));
        if (bagTarget) this.hud?.bagRing.setAttribute("opacity", String(shown));
        else {
          this.fx.focusSmall.setAttribute("transform", `translate(${this.px(this.at[0]) + ox - 26} ${this.py(this.at[1]) + oy - 26})`);
          this.fx.focusSmall.setAttribute("opacity", String(shown));
        }
        this.showBubble(errorLabel(req.error!.code), "error", shown);
        break;
      }
      default: {
        this.showBubble(errorLabel(req.error?.code ?? "?"), "error", shown);
      }
    }
  }

  private showCellCount(k: string, n: number): void {
    if (n > 0 && !this.crystalNodes.has(k)) this.drawCrystal(k, n);
    const nodes = this.crystalNodes.get(k);
    if (!nodes) return;
    this.placeCrystal(k, n, k === key(this.at) ? 1 : 0);
  }

  /** The call completed: take its after-state as the new committed state. */
  commit(req: Request): void {
    const fx = req.fx ?? {};
    if (!req.error) {
      switch (clipFor(req)) {
        case "move.step":
          this.at = [...(fx.to as Cell)] as Cell;
          if (!this.inView(this.at)) this.follow();
          break;
        case "turn":
          this.heading = fx.to as string;
          break;
        case "crystal.transfer": {
          const k = key(fx.cell as Cell);
          const n = Number(fx.cell_after);
          if (n > 0) this.crystals.set(k, n);
          else this.crystals.delete(k);
          this.drawCrystal(k, n);
          this.bag = fx.bag_after as number | "infinite";
          break;
        }
        case "paint.apply":
          this.painted.add(key(fx.cell as Cell));
          this.drawPaint(key(fx.cell as Cell));
          break;
        case "paint.erase": {
          const k = key(fx.cell as Cell);
          this.painted.delete(k);
          this.paintNodes.get(k)?.remove();
          this.paintNodes.delete(k);
          break;
        }
      }
    }
    this.restPose();
    if (req.error) this.showBubble(errorLabel(req.error.code), "error", 1);
    this.setCall(req);
  }

  setCall(req: Request | null): void {
    if (!this.hud) return;
    if (!req) { this.hud.callText.textContent = ""; return; }
    const value = req.kind === "sensor" && !req.error ? ` → ${pyRepr(req.result)}` : "";
    this.hud.callText.textContent = `${req.op}()${value}`;
  }

  /** A plane's camera follows the robot out of the viewport. */
  private follow(): void {
    const v = this.view;
    const [x, y] = this.at;
    if (x < v.x0) v.x0 = x - 1;
    if (x >= v.x0 + v.w) v.x0 = x - v.w + 2;
    if (y < v.y0) v.y0 = y - 1;
    if (y >= v.y0 + v.h) v.y0 = y - v.h + 2;
    this.layout();
  }

  /** Back to the world's initial state (C17: a reset, not a reverse route). */
  reset(): void {
    this.setWorld(this.world);
    this.setStatus(null);
  }

  setStatus(status: { kind: "completed" | "success" | "error"; text: string } | null): void {
    if (!this.hud) return;
    for (const [name, node] of Object.entries(this.hud.statusIcons)) {
      node.setAttribute("opacity", status && status.kind === name ? "1" : "0");
    }
    this.hud.statusText.textContent = status?.text ?? "";
    for (const m of this.verdictMarks) m.remove();
    this.verdictMarks = [];
  }

  /** C16: point at the cells a failed goal names. */
  markCells(cells: Cell[]): void {
    for (const c of cells) {
      if (!this.inView(c)) continue;
      const g = el("g", { transform: `translate(${this.px(c[0])} ${this.py(c[1])})` }, this.layers.fx);
      el("rect", { x: 6, y: 6, width: CELL - 12, height: CELL - 12, rx: 14, fill: "none", stroke: PALETTE.error,
        "stroke-width": 6, "stroke-dasharray": "18 10" }, g);
      this.verdictMarks.push(g);
    }
  }

  get committed() {
    return { at: this.at, heading: this.heading, bag: this.bag };
  }

  destroy(): void {
    this.svg.remove();
  }
}

// ---------------------------------------------------------------------- driver

export type Playback = {
  finished: Promise<void>;
  pause(): void;
  resume(): void;
  cancel(): void;
  readonly done: boolean;
};

/** Play `req` on `scene`: rAF-driven progress, speed, pause, cancel. Hidden
 *  tabs get no animation frames, so a run there simply waits. */
export function play(scene: Scene, req: Request, speed: number): Playback {
  const duration = durationFor(req);
  let resolve!: () => void, reject!: (e: unknown) => void;
  const finished = new Promise<void>((a, b) => { resolve = a; reject = b; });
  let raf = 0, elapsed = 0, previous = 0, paused = false, done = false;
  const finish = () => {
    if (done) return;
    done = true;
    cancelAnimationFrame(raf);
    scene.frame(req, 1);
    resolve();
  };
  const tick = (now: number) => {
    if (done || paused) return;
    if (previous) elapsed += (now - previous) * speed;
    previous = now;
    const p = duration > 0 ? elapsed / duration : 1;
    scene.frame(req, p);
    if (p >= 1) finish();
    else raf = requestAnimationFrame(tick);
  };
  const ctl: Playback = {
    finished,
    pause() { paused = true; cancelAnimationFrame(raf); },
    resume() { if (!done && paused) { paused = false; previous = 0; raf = requestAnimationFrame(tick); } },
    cancel() {
      if (done) return;
      done = true;
      cancelAnimationFrame(raf);
      scene.frame(req, 0);
      reject(new DOMException("Animation cancelled", "AbortError"));
    },
    get done() { return done; },
  };
  if (!Number.isFinite(speed)) {
    queueMicrotask(finish);
  } else {
    scene.frame(req, 0);
    raf = requestAnimationFrame(tick);
  }
  return ctl;
}

export { NS };

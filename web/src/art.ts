/**
 * The Timo art, bundled as SVG text and addressed only through its manifest:
 * part ids, anchors and the palette. Nothing here measures paths.
 */
import manifest from "../../art/workshop/manifest.json";
import robot from "../../art/workshop/robot/robot.svg";
import crystal from "../../art/workshop/world/crystal.svg";
import paint from "../../art/workshop/world/paint.svg";
import wall from "../../art/workshop/world/wall.svg";
import wallJoint from "../../art/workshop/world/wall-joint.svg";
import markerStart from "../../art/workshop/world/marker-start.svg";
import markerFinish from "../../art/workshop/world/marker-finish.svg";
import markerTarget from "../../art/workshop/world/marker-target.svg";
import bag from "../../art/workshop/hud/bag.svg";
import compass from "../../art/workshop/hud/compass.svg";
import arrow from "../../art/workshop/hints/direction-arrow.svg";
import pulse from "../../art/workshop/hints/sensor-pulse.svg";
import focus from "../../art/workshop/hints/focus-ring.svg";
import yes from "../../art/workshop/status/boolean-true.svg";
import no from "../../art/workshop/status/boolean-false.svg";
import error from "../../art/workshop/status/error.svg";
import completed from "../../art/workshop/status/completed.svg";
import success from "../../art/workshop/status/success.svg";

export const NS = "http://www.w3.org/2000/svg";

export const ASSETS: Record<string, string> = {
  "robot/robot.svg": robot,
  "world/crystal.svg": crystal,
  "world/paint.svg": paint,
  "world/wall.svg": wall,
  "world/wall-joint.svg": wallJoint,
  "world/marker-start.svg": markerStart,
  "world/marker-finish.svg": markerFinish,
  "world/marker-target.svg": markerTarget,
  "hud/bag.svg": bag,
  "hud/compass.svg": compass,
  "hints/direction-arrow.svg": arrow,
  "hints/sensor-pulse.svg": pulse,
  "hints/focus-ring.svg": focus,
  "status/boolean-true.svg": yes,
  "status/boolean-false.svg": no,
  "status/error.svg": error,
  "status/completed.svg": completed,
  "status/success.svg": success,
};

type Asset = { id: string; path: string; viewBox: number[]; parts?: string[]; anchors?: Record<string, number[]> };
const byPath = new Map<string, Asset>((manifest.assets as Asset[]).map((a) => [a.path, a]));

export const PALETTE = manifest.palette as Record<string, string>;
export const ART_REVISION = manifest.revision as string;

export function anchor(path: string, name: string): number[] {
  const a = byPath.get(path)?.anchors?.[name];
  if (!a) throw new Error(`art manifest: ${path} has no anchor ${name}`);
  return a;
}

export function viewBox(path: string): number[] {
  const a = byPath.get(path);
  if (!a) throw new Error(`art manifest: no asset ${path}`);
  return a.viewBox;
}

let nextId = 0;

export function el<K extends keyof SVGElementTagNameMap>(
  tag: K, attrs: Record<string, string | number> = {}, parent?: Element,
): SVGElementTagNameMap[K] {
  const node = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, String(v));
  if (parent) parent.appendChild(node);
  return node;
}

function parse(path: string): SVGSVGElement {
  const text = ASSETS[path];
  if (!text) throw new Error(`art: ${path} is not bundled`);
  const doc = new DOMParser().parseFromString(text, "image/svg+xml");
  if (doc.querySelector("parsererror")) throw new Error(`art: ${path} is not valid SVG`);
  const node = document.importNode(doc.documentElement, true) as unknown as SVGSVGElement;
  for (const t of node.querySelectorAll("title, desc")) t.remove();
  return node;
}

/** Namespace every id so several scenes can share a page (ported from player.js). */
function namespace(node: Element): Map<string, string> {
  const prefix = `timo-${++nextId}-`;
  const ids = new Map<string, string>();
  for (const n of [node, ...node.querySelectorAll("[id]")]) {
    if (n.id) {
      ids.set(n.id, prefix + n.id);
      n.id = prefix + n.id;
    }
  }
  for (const n of [node, ...node.querySelectorAll("*")]) {
    for (const attr of Array.from(n.attributes)) {
      let value = attr.value;
      if (attr.localName === "href" && value.startsWith("#") && ids.has(value.slice(1))) value = "#" + ids.get(value.slice(1));
      value = value.replace(/url\(#([^)]+)\)/g, (all, id) => (ids.has(id) ? `url(#${ids.get(id)})` : all));
      if (value !== attr.value) n.setAttributeNS(attr.namespaceURI, attr.name, value);
    }
  }
  return ids;
}

/** A live, animatable copy: parts are reachable by their logical names. */
export type Mounted = { node: SVGSVGElement; parts: Record<string, SVGElement>; base: Record<string, { transform: string; opacity: string }> };

export function mount(path: string, parent: Element, x = 0, y = 0, w?: number, h?: number): Mounted {
  const node = parse(path);
  namespace(node);
  const [, , vw, vh] = viewBox(path);
  node.setAttribute("x", String(x));
  node.setAttribute("y", String(y));
  node.setAttribute("width", String(w ?? vw));
  node.setAttribute("height", String(h ?? vh));
  node.setAttribute("overflow", "visible");
  node.removeAttribute("role");
  parent.appendChild(node);
  const parts: Record<string, SVGElement> = {};
  const base: Mounted["base"] = {};
  for (const n of node.querySelectorAll<SVGElement>("[data-part]")) {
    const name = n.dataset.part!;
    parts[name] = n;
    base[name] = { transform: n.getAttribute("transform") || "", opacity: n.getAttribute("opacity") ?? "1" };
  }
  return { node, parts, base };
}

/**
 * Static, many-times objects (walls, crystals, markers, paint) become <symbol>s
 * once per scene and are placed with <use>.
 */
export class Symbols {
  private ids = new Map<string, string>();
  constructor(private defs: SVGDefsElement) {}

  ref(path: string): string {
    let id = this.ids.get(path);
    if (id) return id;
    const svg = parse(path);
    namespace(svg);
    id = `timo-sym-${++nextId}`;
    const sym = el("symbol", { id, viewBox: viewBox(path).join(" "), overflow: "visible" }, this.defs);
    while (svg.firstChild) sym.appendChild(svg.firstChild);
    this.ids.set(path, id);
    return id;
  }

  use(path: string, parent: Element, x: number, y: number, w?: number, h?: number, extra: Record<string, string | number> = {}): SVGUseElement {
    const [, , vw, vh] = viewBox(path);
    return el("use", { href: "#" + this.ref(path), x, y, width: w ?? vw, height: h ?? vh, ...extra }, parent);
  }
}

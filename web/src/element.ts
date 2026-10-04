/**
 * <tlfrobot-worlds>: the worlds of a problem, drawn as pictures.
 *
 *   <tlfrobot-worlds>
 *     <script type="text/plain" data-kind="map" data-label="World 1">…TOML…</script>
 *     <script type="text/plain" data-kind="goal">…TOML…</script>   (optional, for the map before it)
 *   </tlfrobot-worlds>
 *
 * The TOML is parsed by the library itself, in the page's shared worker.
 */
import { host, type LabWorld } from "./lab";
import { Scene } from "./scene";

export function readWorlds(root: Element): LabWorld[] {
  const worlds: LabWorld[] = [];
  for (const s of root.querySelectorAll<HTMLScriptElement>(":scope > script[type='text/plain']")) {
    const kind = s.dataset.kind ?? "map";
    if (kind === "map") worlds.push({ label: s.dataset.label || `World ${worlds.length + 1}`, map: s.textContent ?? "", goal: null });
    else if (kind === "goal" && worlds.length) worlds[worlds.length - 1].goal = s.textContent ?? "";
  }
  return worlds;
}

export class TlfrobotWorlds extends HTMLElement {
  private started = false;

  connectedCallback(): void {
    if (this.started) return;
    this.started = true;
    const worlds = readWorlds(this);
    const box = document.createElement("div");
    box.className = "tlfrobot-worlds";
    box.style.cssText = "display:flex;flex-wrap:wrap;gap:12px;align-items:flex-start";
    this.appendChild(box);
    host().parse(worlds.map((w) => w.map), worlds.map((w) => w.goal ?? null)).then((parsed) => {
      parsed.forEach((p, i) => {
        const fig = document.createElement("figure");
        fig.style.cssText = "margin:0;flex:1 1 220px;max-width:420px";
        box.appendChild(fig);
        if (p.ok) {
          const scene = new Scene(fig, { hud: false });
          scene.setWorld(p.world);
        } else {
          const err = document.createElement("pre");
          err.textContent = p.error;
          fig.appendChild(err);
        }
        const cap = document.createElement("figcaption");
        cap.textContent = worlds[i].label;
        cap.style.cssText = "text-align:center;font-size:.85em;opacity:.8";
        fig.appendChild(cap);
      });
    }, (e) => {
      box.textContent = `The robot worlds could not be drawn: ${e.message}`;
    });
  }
}

export function define(): void {
  if (!customElements.get("tlfrobot-worlds")) customElements.define("tlfrobot-worlds", TlfrobotWorlds);
}

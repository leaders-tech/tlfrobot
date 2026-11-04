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
import type { GoalPreview, World } from "./types";
import worldStyles from "./worlds.css";

export function readWorlds(root: Element): LabWorld[] {
  const worlds: LabWorld[] = [];
  for (const s of root.querySelectorAll<HTMLScriptElement>(":scope > script[type='text/plain']")) {
    const kind = s.dataset.kind ?? "map";
    if (kind === "map") worlds.push({ label: s.dataset.label || `World ${worlds.length + 1}`, map: s.textContent ?? "", goal: null });
    else if (kind === "goal" && worlds.length) worlds[worlds.length - 1].goal = s.textContent ?? "";
  }
  return worlds;
}

type Language = "ru" | "en";
const words = {
  ru: { before: "До", after: "После", karel: "Карел", column: "столбец", row: "ряд снизу",
    bag: "В сумке", under: "Под Карелом", crystals: "Кристаллы", paint: "Закраска", heading: "Направление",
    unchecked: "не проверяется", uncheckedPlural: "не проверяются", world: "Мир",
    directions: { north: "север", east: "восток", south: "юг", west: "запад" } },
  en: { before: "Before", after: "After", karel: "Karel", column: "column", row: "row from the bottom",
    bag: "In the bag", under: "Under Karel", crystals: "Crystals", paint: "Paint", heading: "Heading",
    unchecked: "not checked", uncheckedPlural: "not checked", world: "World",
    directions: { north: "north", east: "east", south: "south", west: "west" } },
};

function languageCode(value: string | null): Language | undefined {
  return value?.match(/^(ru|en)(?:-|$)/i)?.[1].toLowerCase() as Language | undefined;
}

function statementLanguage(root: HTMLElement, worlds: LabWorld[]): Language {
  const marked = root.closest<HTMLElement>("[lang]");
  const localLanguage = marked !== root.ownerDocument.documentElement && languageCode(marked?.lang ?? null);
  if (localLanguage) return localLanguage;

  // The portal can switch the statement language independently of the page shell.
  const current = root.ownerDocument.querySelectorAll(
    "button[aria-pressed=true], [role=tab][aria-selected=true], [aria-current=page], [aria-current=true], button.active, button.selected",
  );
  for (const button of current) {
    const code = languageCode(button.textContent?.trim() ?? null);
    if (code) return code;
  }
  const heading = root.closest("section, article")?.querySelector("h3, h2, h1")?.textContent ?? "";
  const labels = worlds.map((w) => w.label).join(" ");
  if (/[а-яё]/i.test(heading + labels)) return "ru";
  if (/[a-z]/i.test(heading)) return "en";
  return languageCode(marked?.lang ?? null) ?? "en";
}

// The statement uses a 3 × 3 map as its size reference. Measure it with the
// same Scene, so a change to the cell size or padding changes both together.
let referenceSide = 0;
function draw(scene: Scene, world: World): void {
  if (!referenceSide) {
    scene.setWorld({ ...world, board: { topology: "bounded", origin: [0, 0], size: [3, 3], walls: [] },
      robot: { ...world.robot, at: [0, 0] }, cells: { crystals: [], painted: [] },
      presentation: { ...world.presentation, markers: [] } });
    referenceSide = scene.svg.viewBox.baseVal.width;
  }
  scene.setWorld(world);
  const { width, height } = scene.svg.viewBox.baseVal;
  const displayWidth = Math.round(width * Math.min(258 / referenceSide, 306 / width, 258 / height));
  const fraction = Math.min(100, 100 * displayWidth / 258);
  scene.svg.style.width = `min(${displayWidth}px, ${fraction}%)`;
  scene.svg.style.margin = "0 auto";
}

function showState(scene: Scene, caption: HTMLElement, world: World, lang: Language, goal?: GoalPreview): void {
  const t = words[lang];
  const [x, y] = world.robot.at;
  const origin = world.board.origin;
  const position = origin ? `${t.column} ${x - origin[0] + 1}, ${t.row} ${y - origin[1] + 1}` : `(${x}, ${y})`;
  const notes = [`${t.karel}: ${position}`];
  // A relative robot normally has an arrow. An unspecified final heading must
  // not show the initial direction, or north, as part of the required answer.
  const noHeading = world.rules.movement === "relative" && goal && !goal.headingSpecified;
  draw(scene, noHeading ? { ...world, robot: { ...world.robot, heading: null },
    rules: { ...world.rules, movement: "absolute" } } : world);

  if (world.rules.movement === "relative") {
    const heading = world.robot.heading as keyof typeof t.directions | null;
    notes.push(`${t.heading}: ${noHeading || !heading ? t.unchecked : t.directions[heading]}`);
  }
  if (world.rules.tools.includes("crystals")) {
    const bag = world.robot.bag === "infinite" ? "∞" : world.robot.bag;
    notes.push(`${t.bag}: ${goal && !goal.bagSpecified ? t.unchecked : bag}`);
    if (goal && !goal.crystalsSpecified) notes.push(`${t.crystals}: ${t.uncheckedPlural}`);
    else {
      const here = world.cells.crystals.find((c) => c.at[0] === x && c.at[1] === y)?.count ?? 0;
      notes.push(`${t.under}: ${here}`);
    }
  }
  if (world.rules.tools.includes("paint") && goal && !goal.paintSpecified) notes.push(`${t.paint}: ${t.unchecked}`);
  caption.textContent = notes.join("\n");
  scene.svg.setAttribute("aria-label", notes.join(". "));
}

let groupNumber = 0;
// A language switch can replace the entire statement. Remember each selected
// goal by problem and world, without keeping any student data across reloads.
const selectedGoals = new Set<string>();

function comparison(label: string, start: World, goal: GoalPreview, lang: Language, key?: string): HTMLElement {
  const group = document.createElement("fieldset");
  group.className = "tlfrobot-comparison";
  const legend = document.createElement("legend");
  legend.textContent = label;
  const options = document.createElement("div");
  options.className = "tlfrobot-view-options";
  group.append(legend, options);
  const name = `tlfrobot-state-${++groupNumber}`;
  const image = document.createElement("figure");
  const board = document.createElement("div");
  image.append(board);
  const scene = new Scene(board, { hud: false });
  const caption = document.createElement("figcaption");
  caption.setAttribute("aria-live", "polite");
  image.append(caption);
  const render = (after: boolean) => showState(scene, caption, after ? goal.world : start, lang, after ? goal : undefined);
  const after = key !== undefined && selectedGoals.has(key);
  for (const state of ["before", "after"] as const) {
    const choice = document.createElement("label");
    const radio = document.createElement("input");
    radio.type = "radio";
    radio.name = name;
    radio.value = state;
    radio.checked = radio.defaultChecked = (state === "after") === after;
    radio.addEventListener("change", () => {
      if (!radio.checked) return;
      if (key !== undefined) {
        if (state === "after") selectedGoals.add(key);
        else selectedGoals.delete(key);
      }
      render(state === "after");
    });
    const text = document.createElement("span");
    text.textContent = words[lang][state];
    choice.append(radio, text);
    options.append(choice);
  }
  group.append(image);
  render(after);
  return group;
}

export class TlfrobotWorlds extends HTMLElement {
  private started = false;
  private waiting: MutationObserver | null = null;

  connectedCallback(): void {
    if (this.started || this.hidden) return;
    // Custom elements can connect before the HTML parser or portal finishes
    // inserting the maps and their following goal scripts.
    if (this.ownerDocument.readyState === "loading") {
      this.ownerDocument.addEventListener("DOMContentLoaded", this.start, { once: true });
    } else queueMicrotask(this.start);
  }

  disconnectedCallback(): void {
    this.ownerDocument.removeEventListener("DOMContentLoaded", this.start);
    this.waiting?.disconnect();
    this.waiting = null;
  }

  private start = (): void => {
    if (this.started || !this.isConnected || this.hidden) return;
    const worlds = readWorlds(this);
    if (!worlds.length) {
      if (!this.waiting) {
        this.waiting = new MutationObserver(this.start);
        this.waiting.observe(this, { childList: true });
      }
      return;
    }
    this.waiting?.disconnect();
    this.waiting = null;
    this.started = true;
    this.render(worlds);
  };

  private render(worlds: LabWorld[]): void {
    const lang = statementLanguage(this, worlds);
    const box = document.createElement("div");
    if (!this.ownerDocument.getElementById("tlfrobot-worlds-style")) {
      const style = this.ownerDocument.createElement("style");
      style.id = "tlfrobot-worlds-style";
      style.textContent = worldStyles;
      this.ownerDocument.head.append(style);
    }
    box.className = "tlfrobot-worlds";
    const problem = this.closest('[id^="prob_"]')?.id ??
      this.closest("section.problem")?.querySelector("[data-problem]")?.getAttribute("data-problem");
    this.appendChild(box);
    host().parse(worlds.map((w) => w.map), worlds.map((w) => w.goal ?? null)).then((parsed) => {
      parsed.forEach((p, i) => {
        const label = worlds[i].label === `World ${i + 1}` ? `${words[lang].world} ${i + 1}` : worlds[i].label;
        if (p.ok && p.preview) {
          const key = problem ? JSON.stringify([location.pathname, problem, p.world.id, i]) : undefined;
          box.append(comparison(label, p.world, p.preview, lang, key));
          return;
        }
        const fig = document.createElement("figure");
        fig.style.cssText = "margin:0;flex:0 1 auto;min-width:0;max-width:100%;text-align:center";
        box.append(fig);
        if (p.ok) draw(new Scene(fig, { hud: false }), p.world);
        else {
          const err = document.createElement("pre");
          err.textContent = p.error;
          fig.append(err);
        }
        if (worlds.length > 1) {
          const cap = document.createElement("figcaption");
          cap.textContent = label;
          cap.style.cssText = "font-size:.85em;opacity:.8";
          fig.append(cap);
        }
      });
    }, (e) => {
      box.textContent = `${lang === "ru" ? "Не удалось показать карты" : "The robot worlds could not be drawn"}: ${e.message}`;
    });
  }
}

export function define(): void {
  if (!customElements.get("tlfrobot-worlds")) customElements.define("tlfrobot-worlds", TlfrobotWorlds);
}

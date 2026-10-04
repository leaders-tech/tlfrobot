/** tlfrobot in the browser: the lab (scene + Python), static world pictures,
 *  and the function catalogue for editor completion. */
import catalog from "../catalog.json";
import { define } from "./element";

declare const __TLFROBOT_VERSION__: string;
export const VERSION = __TLFROBOT_VERSION__;
export const CATALOG = catalog;

export { RobotLab, support, host, type LabWorld, type LabState } from "./lab";
export { Scene, play, pyRepr, errorLabel } from "./scene";
export { readWorlds, TlfrobotWorlds, define } from "./element";
export type { World, Request, RunResult, ParsedWorld, Verdict, Cell } from "./types";

if (typeof customElements !== "undefined") define();

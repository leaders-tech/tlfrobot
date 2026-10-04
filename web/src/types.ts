export type Cell = [number, number];
export type End = number | "-inf" | "+inf";

/** The normalised world, exactly as Python's `World.normalised()` writes it. */
export type World = {
  format: string;
  id: string;
  title?: string;
  rules: { movement: "relative" | "absolute"; tools: string[]; sensors: string[]; inputs: string[]; allowed_commands: string[] };
  board: { topology: "bounded" | "plane"; origin?: Cell; size?: Cell; walls: { axis: "h" | "v"; at: number; span: [End, End] }[] };
  robot: { at: Cell; heading: string | null; bag: number | "infinite" | null };
  cells: { crystals: { at: Cell; count: number }[]; painted: Cell[] };
  presentation: { theme: string; show_coordinates: boolean; viewport?: [number, number, number, number]; markers: { at: Cell; kind: string }[] };
};

/** A prepared robot call, sent by Python before it is committed. */
export type Request = {
  n: number;
  op: string;
  kind: "action" | "sensor";
  line: number | null;
  rev: number;
  fx: Record<string, unknown>;
  result?: boolean | number | null;
  error?: { code: string; message: string; details?: Record<string, unknown> };
};

export type Verdict = { verdict: string; code: string; message: string; details: Record<string, unknown> };

export type RunResult = {
  status: "completed" | "error" | "cancelled" | "limit" | "map_error" | "crashed";
  error: { code: string; message: string; details?: Record<string, unknown> } | null;
  calls: number;
  state: { robot: { at: Cell; heading: string | null; bag: number | "infinite" | null } } | null;
  verdict: Verdict | null;
};

export type ParsedWorld = { ok: true; world: World; hasGoal: boolean } | { ok: false; error: string };

/** Shared mailbox (Int32 slots). The worker blocks on it inside a robot call. */
export const MB = { SEQ: 0, STATUS: 1, RUN: 2, CANCEL: 3, LENGTH: 4 } as const;
export const STATUS = { COMPLETED: 1, CANCELLED: 2 } as const;

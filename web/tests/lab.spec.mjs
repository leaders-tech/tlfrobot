// The live contract, in a real browser with the real Pyodide and wheel.
import { expect, test } from "@playwright/test";

const ROUTE = `from tlfrobot import *
move()
move()
take()
turn_around()
move()
turn_right()
move()
turn_right()
while front_clear():
    move()
turn_right()
move()
`;

async function open(page) {
  await page.goto("/");
  await page.evaluate(() => window.ready);
  expect(await page.evaluate(() => crossOriginIsolated)).toBe(true);
}

/** Record every call's start/end with the committed robot position at that moment. */
async function record(page) {
  await page.evaluate(() => {
    window.events = [];
    lab.on("call", (req, phase) => window.events.push({ n: req.n, op: req.op, phase, at: [...lab.scene.committed.at], result: req.result }));
  });
}

const run = (page, code, opts = {}) => page.evaluate(([c, o]) => lab.run(c, o), [code, opts]);

test("a full run reaches the goal and the trace agrees with CPython", async ({ page }) => {
  await open(page);
  await page.evaluate(() => lab.setSpeed(4));
  const r = await run(page, ROUTE);
  expect(r.status).toBe("completed");
  expect(r.verdict.verdict).toBe("accepted");
  expect(r.calls).toBe(17);
  expect(r.state.robot).toEqual({ at: [4, 0], heading: "south", bag: 1 });
});

test("the next call does not start before the previous animation ends", async ({ page }) => {
  await open(page);
  await record(page);
  await page.evaluate(() => lab.setSpeed(2));
  await run(page, "from tlfrobot import *\nmove()\nfront_clear()\nmove()\n");
  const ev = await page.evaluate(() => window.events);
  expect(ev.map((e) => `${e.op}:${e.phase}`)).toEqual(
    ["move:start", "move:end", "front_clear:start", "front_clear:end", "move:start", "move:end"]);
  // committed state changes only at the end of a move
  expect(ev[0].at).toEqual([0, 0]);
  expect(ev[2].at).toEqual([1, 0]);
});

test("the sensor value shown is the value Python got", async ({ page }) => {
  await open(page);
  await page.evaluate(() => lab.setSpeed(Infinity));
  await page.evaluate(() => { window.printed = ""; lab.on("output", (t) => (window.printed += t)); });
  await record(page);
  await run(page, "from tlfrobot import *\nprint(front_clear(), right_clear())\n");
  const ev = await page.evaluate(() => window.events.filter((e) => e.phase === "end").map((e) => e.result));
  expect(ev).toEqual([true, false]);
  expect(await page.evaluate(() => window.printed)).toBe("True False\n");
});

test("Stop during a move cancels it without committing", async ({ page }) => {
  await open(page);
  await page.evaluate(() => lab.setSpeed(0.25));
  const p = run(page, "from tlfrobot import *\nmove()\nmove()\n");
  await page.waitForTimeout(700);
  await page.evaluate(() => lab.stop());
  const r = await p;
  expect(r.status).toBe("cancelled");
  expect(r.state.robot.at).toEqual([0, 0]);
  expect(await page.evaluate(() => lab.scene.committed.at)).toEqual([0, 0]);
});

test("Stop ends a loop that makes no robot calls", async ({ page }) => {
  await open(page);
  const p = run(page, "x = 0\nwhile True:\n    x += 1\n");
  await page.waitForTimeout(800);
  const t0 = Date.now();
  await page.evaluate(() => lab.stop());
  const r = await p;
  expect(r.status).toBe("cancelled");
  expect(Date.now() - t0).toBeLessThan(1400);
});

test("reset straight after a run, then another run", async ({ page }) => {
  await open(page);
  await page.evaluate(() => lab.setSpeed(0.5));
  const first = run(page, "from tlfrobot import *\nmove()\nmove()\n");
  await page.waitForTimeout(300);
  await page.evaluate(() => lab.reset());
  await first;
  await page.evaluate(() => lab.setSpeed(Infinity));
  const r = await run(page, "from tlfrobot import *\nmove()\n");
  expect(r.status).toBe("completed");
  expect(r.state.robot.at).toEqual([1, 0]);
});

test("step mode lets exactly one call through", async ({ page }) => {
  await open(page);
  await record(page);
  await page.evaluate(() => lab.setSpeed(Infinity));
  const p = run(page, "from tlfrobot import *\nmove()\nfront_clear()\nmove()\n", { paused: true });
  await page.waitForTimeout(500);
  expect(await page.evaluate(() => window.events.length)).toBe(0);
  await page.evaluate(() => lab.step());
  await page.waitForTimeout(300);
  expect(await page.evaluate(() => window.events.map((e) => `${e.op}:${e.phase}`))).toEqual(["move:start", "move:end"]);
  await page.evaluate(() => lab.step());
  await page.waitForTimeout(300);
  expect(await page.evaluate(() => window.events.length)).toBe(4);
  await page.evaluate(() => lab.resume());
  const r = await p;
  expect(r.status).toBe("completed");
});

test("errors: wall, Python exception with its line, non-ASCII source", async ({ page }) => {
  await open(page);
  await page.evaluate(() => lab.setSpeed(Infinity));
  let r = await run(page, "from tlfrobot import *\nmove()\nmove()\nturn_left()\nmove()\n");
  expect(r.status).toBe("error");
  expect(r.error.code).toBe("WALL_COLLISION");
  r = await run(page, "from tlfrobot import *\n# Привет, мир 🤖\nmove()\nx = 1 / 0\n");
  expect(r.status).toBe("error");
  expect(r.error.details.line).toBe(4);
  expect(r.error.message).toContain("ZeroDivisionError");
});

test("worlds are parsed by the library and bad maps are reported", async ({ page }) => {
  await open(page);
  const parsed = await page.evaluate(() => lab.load([
    { label: "ok", map: 'format = "tlfrobot-world/1"\nid = "a"\n[rules]\nmovement = "absolute"\n[board]\nsize = [2, 2]\n[robot]\nat = [0, 0]\n' },
    { label: "bad", map: 'format = "tlfrobot-world/1"\nid = "b"\n[rules]\nmovement = "sideways"\n[board]\nsize = [2, 2]\n[robot]\nat = [0, 0]\n' },
  ]));
  expect(parsed[0].ok).toBe(true);
  expect(parsed[0].world.robot.heading).toBe(null);
  expect(parsed[1].ok).toBe(false);
  expect(parsed[1].error).toContain("movement");
});

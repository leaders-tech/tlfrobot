// Run with Node's TypeScript support: node --test web/tests/load-wheel.test.mjs
import assert from "node:assert/strict";
import { test } from "node:test";
import { loadRobotWheel } from "../src/load-wheel.ts";

const url = "https://course.example/s/pyodide/wheels/tlfrobot-0.1.1-py3-none-any.whl";

test("a successful installation needs no extra download", async (t) => {
  const fetch = t.mock.method(globalThis, "fetch", async () => assert.fail("unexpected download"));
  const runtime = {
    loadedPackages: {},
    async loadPackage(requested) {
      assert.equal(requested, url);
      this.loadedPackages.tlfrobot = url;
    },
  };
  await loadRobotWheel(runtime, url);
  assert.equal(fetch.mock.callCount(), 0);
});

test("a cached 403 is refreshed before Pyodide retries", async (t) => {
  let cachedError = true;
  let attempts = 0;
  t.mock.method(globalThis, "fetch", async (requested, options) => {
    assert.equal(requested, url);
    assert.equal(options.cache, "reload");
    return {
      ok: true,
      async arrayBuffer() {
        // The next installation must wait for the complete fresh response.
        await new Promise((resolve) => setImmediate(resolve));
        cachedError = false;
        return new ArrayBuffer(4);
      },
    };
  });
  const runtime = {
    loadedPackages: {},
    async loadPackage(_url, { errorCallback }) {
      attempts++;
      if (cachedError) errorCallback("HTTP 403 Forbidden");
      else this.loadedPackages.tlfrobot = url;
    },
  };
  await loadRobotWheel(runtime, url);
  assert.equal(attempts, 2);
  assert.equal(runtime.loadedPackages.tlfrobot, url);
});

test("a thrown loading error also gets one retry", async (t) => {
  const fetch = t.mock.method(globalThis, "fetch", async () => new Response("wheel"));
  let attempts = 0;
  const runtime = {
    loadedPackages: {},
    async loadPackage() {
      if (++attempts === 1) throw new TypeError("Failed to fetch");
      this.loadedPackages.tlfrobot = url;
    },
  };
  await loadRobotWheel(runtime, url);
  assert.equal(attempts, 2);
  assert.equal(fetch.mock.callCount(), 1);
});

test("a real server error stops with its HTTP status", async (t) => {
  const fetch = t.mock.method(globalThis, "fetch", async () =>
    new Response("Forbidden", { status: 403, statusText: "Forbidden" }));
  let attempts = 0;
  const runtime = {
    loadedPackages: {},
    async loadPackage() { attempts++; },
  };
  await assert.rejects(loadRobotWheel(runtime, url), /Could not download the robot package:.*HTTP 403 Forbidden/);
  assert.equal(attempts, 1);
  assert.equal(fetch.mock.callCount(), 1);
});

test("a failed second installation is reported and never loops", async (t) => {
  const fetch = t.mock.method(globalThis, "fetch", async () => new Response("invalid wheel"));
  let attempts = 0;
  const runtime = {
    loadedPackages: {},
    async loadPackage(_url, { errorCallback }) {
      attempts++;
      errorCallback("Invalid wheel archive");
    },
  };
  await assert.rejects(loadRobotWheel(runtime, url), /Could not install the robot package after retry: Invalid wheel archive/);
  assert.equal(attempts, 2);
  assert.equal(fetch.mock.callCount(), 1);
});

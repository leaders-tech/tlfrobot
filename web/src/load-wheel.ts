type WheelRuntime = {
  loadedPackages: Record<string, string>;
  loadPackage: (url: string, options: { errorCallback: (message: string) => void }) => Promise<unknown>;
};

/** Recover once from a cached HTTP error without discarding other browser data. */
export async function loadRobotWheel(pyodide: WheelRuntime, url: string): Promise<void> {
  async function install(): Promise<string | null> {
    const errors: string[] = [];
    try {
      // Pyodide can resolve even when downloading or installing a wheel failed.
      await pyodide.loadPackage(url, { errorCallback: (message) => errors.push(message) });
    } catch (error) {
      errors.push(String(error));
    }
    return pyodide.loadedPackages.tlfrobot ? null : errors.join("; ") || "the package was not installed";
  }

  if (await install() === null) return;

  // An old 403 may have an immutable cache policy. Refresh this URL only,
  // consuming the body before Pyodide requests the now-refreshed cache entry.
  try {
    const response = await fetch(url, { cache: "reload" });
    if (!response.ok) throw new Error(`HTTP ${response.status} ${response.statusText}`.trim());
    await response.arrayBuffer();
  } catch (error) {
    throw new Error(`Could not download the robot package: ${String(error)}`);
  }

  const error = await install();
  if (error !== null) throw new Error(`Could not install the robot package after retry: ${error}`);
}

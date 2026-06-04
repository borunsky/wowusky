import { app, BrowserWindow, ipcMain, shell, dialog } from "electron";
import {
  spawn,
  spawnSync,
  ChildProcessWithoutNullStreams,
} from "child_process";
import { join, resolve } from "path";
import * as readline from "readline";

/**
 * Resolve the Python interpreter to run the bridge with. Honors an explicit
 * WOWUSKY_PYTHON override, otherwise tries `python3` then `python` (some
 * distros — e.g. Arch — only ship one of the two).
 */
function resolvePython(): string {
  if (process.env.WOWUSKY_PYTHON) return process.env.WOWUSKY_PYTHON;
  for (const candidate of ["python3", "python"]) {
    const probe = spawnSync(candidate, ["--version"]);
    if (probe.status === 0) return candidate;
  }
  return "python3"; // fall back; failure surfaces as a bridge error
}

// ---------------------------------------------------------------------------
// Python JSON-RPC bridge client
// ---------------------------------------------------------------------------

type Pending = { resolve: (v: unknown) => void; reject: (e: Error) => void };

class Bridge {
  private proc: ChildProcessWithoutNullStreams | null = null;
  private nextId = 1;
  private pending = new Map<number, Pending>();
  private onNotify: (method: string, params: unknown) => void;

  constructor(onNotify: (method: string, params: unknown) => void) {
    this.onNotify = onNotify;
  }

  start(): void {
    const pythonBin = resolvePython();
    // Dev: repo root is the parent of desktop/.
    // Packaged: the wowusky Python package is installed system-wide; CWD just
    // needs to be somewhere harmless — we use the resources dir.
    const repoRoot = process.env.WOWUSKY_REPO_ROOT || (
      app.isPackaged ? process.resourcesPath : resolve(app.getAppPath(), "..")
    );

    this.proc = spawn(pythonBin, ["-m", "wowusky.bridge"], {
      cwd: repoRoot,
      env: { ...process.env, PYTHONUNBUFFERED: "1" },
    });

    const rl = readline.createInterface({ input: this.proc.stdout });
    rl.on("line", (line) => this.handleLine(line));

    this.proc.stderr.on("data", (d: Buffer) => {
      // Bridge diagnostics — surface in the main process console only.
      process.stderr.write(d);
    });
    this.proc.on("exit", (code) => {
      for (const [, p] of this.pending) {
        p.reject(new Error(`bridge exited (code ${code})`));
      }
      this.pending.clear();
      this.proc = null;
    });
  }

  private handleLine(line: string): void {
    const trimmed = line.trim();
    if (!trimmed) return;
    let msg: Record<string, unknown>;
    try {
      msg = JSON.parse(trimmed);
    } catch {
      process.stderr.write(`[bridge] non-JSON line: ${trimmed}\n`);
      return;
    }
    const id = msg.id as number | undefined;
    if (id === undefined || id === null) {
      // Notification (streaming event).
      this.onNotify(msg.method as string, msg.params);
      return;
    }
    const pending = this.pending.get(id);
    if (!pending) return;
    this.pending.delete(id);
    if (msg.error) {
      const err = msg.error as { message?: string };
      pending.reject(new Error(err.message || "bridge error"));
    } else {
      pending.resolve(msg.result);
    }
  }

  call(method: string, params: Record<string, unknown> = {}): Promise<unknown> {
    if (!this.proc) return Promise.reject(new Error("bridge not running"));
    const id = this.nextId++;
    const payload = JSON.stringify({ jsonrpc: "2.0", id, method, params });
    return new Promise((resolveFn, rejectFn) => {
      this.pending.set(id, { resolve: resolveFn, reject: rejectFn });
      this.proc!.stdin.write(payload + "\n");
    });
  }

  stop(): void {
    this.proc?.kill();
    this.proc = null;
  }
}

// ---------------------------------------------------------------------------
// Window + app lifecycle
// ---------------------------------------------------------------------------

let mainWindow: BrowserWindow | null = null;
let bridge: Bridge | null = null;

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1180,
    height: 760,
    minWidth: 420,
    minHeight: 520,
    show: false,
    frame: false, // custom titlebar from the redesign
    backgroundColor: "#0a0e16",
    webPreferences: {
      preload: join(__dirname, "../preload/index.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  mainWindow.on("ready-to-show", () => mainWindow?.show());

  // Open external links in the system browser, not inside the app.
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });

  const devUrl = process.env["ELECTRON_RENDERER_URL"];
  if (devUrl) {
    mainWindow.loadURL(devUrl);
  } else {
    mainWindow.loadFile(join(__dirname, "../renderer/index.html"));
  }
}

app.whenReady().then(() => {
  bridge = new Bridge((method, params) => {
    mainWindow?.webContents.send("bridge:notify", { method, params });
  });
  bridge.start();

  // Renderer -> Python RPC.
  ipcMain.handle("bridge:call", async (_e, method: string, params) => {
    return bridge!.call(method, params || {});
  });

  // Directory picker (for Set Path in Settings).
  ipcMain.handle("dialog:openDirectory", async () => {
    if (!mainWindow) return null;
    const result = await dialog.showOpenDialog(mainWindow, {
      properties: ["openDirectory"],
      title: "Select AddOns folder",
    });
    return result.canceled ? null : (result.filePaths[0] ?? null);
  });

  // Window controls for the custom titlebar.
  ipcMain.on("win:minimize", () => mainWindow?.minimize());
  ipcMain.on("win:maximize", () => {
    if (!mainWindow) return;
    mainWindow.isMaximized() ? mainWindow.unmaximize() : mainWindow.maximize();
  });
  ipcMain.on("win:close", () => mainWindow?.close());

  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  bridge?.stop();
  if (process.platform !== "darwin") app.quit();
});

import { contextBridge, ipcRenderer } from "electron";

type NotifyHandler = (method: string, params: unknown) => void;

const api = {
  /** Call a Python JSON-RPC method and await its result. */
  call<T = unknown>(method: string, params?: Record<string, unknown>): Promise<T> {
    return ipcRenderer.invoke("bridge:call", method, params) as Promise<T>;
  },

  /** Subscribe to streaming notifications (progress, toasts, …). */
  onNotify(handler: NotifyHandler): () => void {
    const listener = (_e: unknown, payload: { method: string; params: unknown }) =>
      handler(payload.method, payload.params);
    ipcRenderer.on("bridge:notify", listener);
    return () => ipcRenderer.removeListener("bridge:notify", listener);
  },

  /** Open a native directory picker, returns the chosen path or null. */
  openDirectory: (): Promise<string | null> =>
    ipcRenderer.invoke("dialog:openDirectory"),

  // Custom titlebar window controls.
  minimize: () => ipcRenderer.send("win:minimize"),
  maximize: () => ipcRenderer.send("win:maximize"),
  close: () => ipcRenderer.send("win:close"),

  /** Set the taskbar/dock badge count (0 clears it). */
  setBadgeCount: (count: number) => ipcRenderer.send("badge:set", count),

  /** Write text to the system clipboard. */
  clipboardWrite: (text: string): Promise<boolean> =>
    ipcRenderer.invoke("clipboard:write", text),

  /** Read text from the system clipboard. */
  clipboardRead: (): Promise<string> => ipcRenderer.invoke("clipboard:read"),

  /** Show a native desktop notification. */
  notify: (title: string, body: string) =>
    ipcRenderer.send("notify", { title, body }),
};

contextBridge.exposeInMainWorld("wowusky", api);

export type WowuskyApi = typeof api;

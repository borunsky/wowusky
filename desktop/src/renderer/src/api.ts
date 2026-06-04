// Typed wrapper around the preload-exposed bridge API.

export type NotifyHandler = (method: string, params: unknown) => void;

interface WowuskyBridge {
  call<T = unknown>(method: string, params?: Record<string, unknown>): Promise<T>;
  onNotify(handler: NotifyHandler): () => void;
  openDirectory(): Promise<string | null>;
  minimize(): void;
  maximize(): void;
  close(): void;
}

declare global {
  interface Window {
    wowusky: WowuskyBridge;
  }
}

export const bridge = window.wowusky;

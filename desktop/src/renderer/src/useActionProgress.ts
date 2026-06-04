import { useEffect, useState } from "react";
import { bridge } from "./api";

export interface ActionProgress {
  phase: "log" | "download";
  /** Latest log line (phase "log"). */
  message?: string;
  /** Download percentage 0–100 (phase "download"). */
  pct?: number;
}

interface ProgressParams {
  id: string;
  phase: "log" | "download";
  message?: string;
  pct?: number;
}

/**
 * Subscribe to the bridge's streaming ``action.progress`` / ``action.done``
 * notifications and expose the latest progress per correlation id (addon id or
 * backup path). An entry is cleared when its ``action.done`` arrives.
 */
export function useActionProgress(): Record<string, ActionProgress> {
  const [map, setMap] = useState<Record<string, ActionProgress>>({});

  useEffect(() => {
    return bridge.onNotify((method, rawParams) => {
      if (method === "action.progress") {
        const p = rawParams as ProgressParams;
        setMap((m) => ({
          ...m,
          [p.id]: { phase: p.phase, message: p.message, pct: p.pct },
        }));
      } else if (method === "action.done") {
        const p = rawParams as { id: string };
        setMap((m) => {
          if (!(p.id in m)) return m;
          const next = { ...m };
          delete next[p.id];
          return next;
        });
      }
    });
  }, []);

  return map;
}

/** Compact one-line label for a progress entry, or null when idle. */
export function progressLabel(p: ActionProgress | undefined): string | null {
  if (!p) return null;
  if (p.phase === "download" && p.pct != null) return `${p.pct}%`;
  return p.message ?? null;
}

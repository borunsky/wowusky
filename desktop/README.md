# wowusky desktop (Electron + React)

The redesigned wowusky UI. An Electron shell renders a React frontend (the
[Claude Design] redesign) and talks to the existing Python core over a
JSON-RPC bridge (`python -m wowusky.bridge`). All addon-management logic stays
in Python; this directory only contains the UI and the thin IPC plumbing.

## Architecture

```
Electron main  (src/main/index.ts)      spawns the Python bridge, owns the
   │  IPC (contextBridge)               window, correlates JSON-RPC calls
Preload        (src/preload/index.ts)   exposes window.wowusky.{call,onNotify,…}
   │
Renderer       (src/renderer)           React UI (the redesign)
   ▲  JSON-RPC over stdin/stdout
Python bridge  (wowusky/bridge)         dispatches to core / orchestrator
```

## Develop

Requires Node 18+ and a working `python3` with wowusky importable from the repo
root (e.g. `pip install -e .`).

```sh
cd desktop
npm install
npm run dev          # launches Electron with HMR
```

`WOWUSKY_PYTHON` overrides the Python binary; `WOWUSKY_REPO_ROOT` overrides the
cwd used to spawn the bridge (defaults to the repo root in dev).

## Scripts

| script            | purpose                                   |
| ----------------- | ----------------------------------------- |
| `npm run dev`     | Electron + Vite dev server (HMR)          |
| `npm run build`   | compile main/preload/renderer to `out/`   |
| `npm run typecheck` | TypeScript only, no emit                |
| `npm run dist`    | build + electron-builder (AppImage/dir)   |

## Status

Phase 0 — scaffold: window chrome stub, Python bridge round-trip
(`app.version`). The full design system and screens land in later phases (see
the v0.9.0/v1.0.0 roadmap in the top-level README).

[Claude Design]: https://claude.ai

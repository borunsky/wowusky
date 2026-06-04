import type { Source } from "./browseData";

export interface InstalledAddon {
  id: string;
  name: string;
  version: string;
  source: Source;
  folders: string[];
  interface: string | null;
  url: string | null;
  glyph: string;
}

export interface InstalledResult {
  profile: string;
  count: number;
  addons_path: string;
  items: InstalledAddon[];
}

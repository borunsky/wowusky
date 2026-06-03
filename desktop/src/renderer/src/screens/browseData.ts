export type Source = "github" | "tukui" | "wowi" | "curse" | "local" | "wowusky";

export interface Addon {
  id: string;
  name: string;
  author: string;
  category: string;
  description: string;
  source: Source;
  glyph: string;
  flavors: string[];
  folders: string[];
  depends: string[];
  installed?: boolean;
}

export interface SearchResult {
  total: number;
  count: number;
  categories: string[];
  items: Addon[];
}

const SRC_LABEL: Record<Source, string> = {
  github: "GitHub",
  tukui: "TukUI",
  wowi: "WoWInterface",
  curse: "CurseForge",
  local: "Local",
  wowusky: "wowusky",
};

export function sourceLabel(s: Source): string {
  return SRC_LABEL[s] ?? s;
}

// Deterministic rarity accent derived from the source, so cards get a stable
// colored edge without the catalog needing a rarity field.
const SOURCE_RARITY: Record<Source, string> = {
  curse: "q",
  github: "i",
  tukui: "a",
  wowi: "b",
  wowusky: "m",
  local: "m",
};

export function rarityFor(a: Addon): string {
  return SOURCE_RARITY[a.source] ?? "i";
}

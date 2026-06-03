export type Source = "github" | "tukui" | "wowi" | "curse" | "local" | "wowusky";
export type Rarity = "i" | "a" | "b" | "m" | "q";

export interface Addon {
  id: string;
  name: string;
  author: string;
  category: string;
  description: string;
  source: Source;
  version: string;
  downloads: string;
  updated: string;
  rarity: Rarity;
  glyph: string;
  installed?: boolean;
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
  return SRC_LABEL[s];
}

/** Placeholder catalog — replaced by live bridge data in a later phase. */
export const MOCK_ADDONS: Addon[] = [
  {
    id: "weakauras",
    name: "WeakAuras",
    author: "WeakAuras Team",
    category: "Combat",
    description: "Powerful, flexible framework to display customizable graphics on your screen.",
    source: "curse",
    version: "5.18.4",
    downloads: "412M",
    updated: "2d ago",
    rarity: "a",
    glyph: "W",
  },
  {
    id: "details",
    name: "Details! Damage Meter",
    author: "Terciob",
    category: "Combat",
    description: "Advanced combat analysis tool with damage, healing and threat meters.",
    source: "curse",
    version: "11.1.5",
    downloads: "248M",
    updated: "5h ago",
    rarity: "i",
    glyph: "D",
    installed: true,
  },
  {
    id: "elvui",
    name: "ElvUI",
    author: "Elv & Team",
    category: "UI Suite",
    description: "A full user interface replacement designed to be a clean and immersive experience.",
    source: "tukui",
    version: "13.78",
    downloads: "190M",
    updated: "1d ago",
    rarity: "m",
    glyph: "E",
  },
  {
    id: "deadly-boss-mods",
    name: "Deadly Boss Mods",
    author: "MysticalOS",
    category: "Raid",
    description: "Boss encounter warnings, timers and automated raid coordination tools.",
    source: "curse",
    version: "11.1.18",
    downloads: "180M",
    updated: "3d ago",
    rarity: "b",
    glyph: "B",
  },
  {
    id: "plater",
    name: "Plater Nameplates",
    author: "Terciob",
    category: "Nameplates",
    description: "Highly customizable nameplate addon with scripting support and modules.",
    source: "curse",
    version: "11.1.9",
    downloads: "96M",
    updated: "6d ago",
    rarity: "i",
    glyph: "P",
  },
  {
    id: "bigwigs",
    name: "BigWigs Bossmods",
    author: "BigWigs Team",
    category: "Raid",
    description: "Modular, lightweight boss encounter addon for raids and dungeons.",
    source: "github",
    version: "11.1.7",
    downloads: "74M",
    updated: "12h ago",
    rarity: "a",
    glyph: "B",
  },
  {
    id: "bartender4",
    name: "Bartender4",
    author: "Nevcairiel",
    category: "Action Bars",
    description: "Full featured action bar replacement mod with extensive customization.",
    source: "wowi",
    version: "4.14.5",
    downloads: "58M",
    updated: "1mo ago",
    rarity: "b",
    glyph: "B",
  },
  {
    id: "raiderio",
    name: "RaiderIO",
    author: "RaiderIO",
    category: "Mythic+",
    description: "See Mythic+ and raid progress scores for players directly in-game.",
    source: "curse",
    version: "11.1.3",
    downloads: "112M",
    updated: "4h ago",
    rarity: "m",
    glyph: "R",
  },
];

export const CATEGORIES = [
  "All",
  "Combat",
  "Raid",
  "UI Suite",
  "Nameplates",
  "Action Bars",
  "Mythic+",
];

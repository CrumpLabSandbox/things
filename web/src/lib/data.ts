// Build-time access to the public data written by `python3 -m pipeline build`.
// Everything here reads data/public/*.json, which only contains the fields
// listed in data/visibility.json, so pages can render whatever they find.
import fs from "node:fs";
import path from "node:path";

export const REPO = process.env.THINGS_REPO ?? path.resolve(process.cwd(), "..");

function readJson<T>(name: string): T {
  return JSON.parse(fs.readFileSync(path.join(REPO, "data", "public", name), "utf8")) as T;
}

export interface Relation { type: string; target: string; note?: string | null; source?: string }
export interface Palette { hex: string; fraction: number }
export interface Artwork {
  id: string;
  catalog: {
    kind?: "work" | "wip";
    title: string;
    series: string;
    series_slug: string;
    medium?: string | null;
    surface?: string | null;
    caption?: string | null;
    date_note?: string | null;
    process_notes?: string | null;
    project?: string;
    step?: number;
    year?: number | null;
    date?: string | null;
    availability?: string | null;
    physical_size_in?: string | null;
    image: { path: string; width: number; height: number; aspect: number; orientation: string };
    page?: { html?: string };
  };
  measured: {
    palette?: Palette[];
    dominant_hues?: string[];
    thumbnail?: string;
    [k: string]: unknown;
  };
  described?: Record<string, unknown> & {
    alt_text?: string;
    description?: string;
    impression?: string;
  };
  relations?: Relation[];
}
export interface Series { slug: string; name: string; years: string; medium: string; count: number; summary: string }
export interface Project {
  id: string; title: string; dates: string; summary: string; source: string; result: string;
  steps: { id: string; caption: string }[];
}
export interface PlaygroundItem { id: string; title: string; image: string; width: number; height: number; date: string | null; prompt: string | null; notes: string | null }
export interface PlaygroundGroup { id: string; source: string | null; description: string | null; notes: string | null; items: PlaygroundItem[] }
export interface Similarity {
  neighbours: Record<string, { tags: [string, number][]; text: [string, number][]; visual: [string, number][] }>;
  layout: Record<string, [number, number]>;
  directions?: Record<string, Record<string, string[]>>;
}

export const artworks: Artwork[] = readJson<Artwork[]>("artworks.json");
export const byId = new Map(artworks.map((a) => [a.id, a]));
export const seriesInfo: Series[] = readJson<{ series: Series[] }>("series.json").series;
export const projects: Project[] = readJson<{ projects: Project[] }>("projects.json").projects;
export const playground: PlaygroundGroup[] = readJson<{ groups: PlaygroundGroup[] }>("playground.json").groups;
export const similarity: Similarity = readJson<Similarity>("similarity.json");
export const vocabulary = readJson<{ facets: Record<string, { tag: string; gloss: string }[]> }>("vocabulary.json");

export const kindOf = (a: Artwork) => a.catalog.kind ?? "work";
export const isWork = (a: Artwork) => kindOf(a) === "work";

const time = (a: Artwork) => Date.parse(a.catalog.date ?? "") || 0;
export const newestFirst = (list: Artwork[]) => [...list].sort((a, b) => time(b) - time(a));
export const oldestFirst = (list: Artwork[]) => [...list].sort((a, b) => time(a) - time(b));

export const works = newestFirst(artworks.filter(isWork));

/** Finished works in a series, oldest first, for prev/next navigation. */
export function inSeries(slug: string): Artwork[] {
  return oldestFirst(artworks.filter((a) => isWork(a) && a.catalog.series_slug === slug));
}

/** Series in display order (from data/series.json), with their works. */
export function seriesList() {
  return seriesInfo.map((s) => ({ ...s, works: newestFirst(inSeries(s.slug)) })).filter((s) => s.works.length);
}

/** Relations pointing at this record from other records. */
export function incoming(id: string): { from: Artwork; rel: Relation }[] {
  const out: { from: Artwork; rel: Relation }[] = [];
  for (const a of artworks) for (const rel of a.relations ?? []) if (rel.target === id) out.push({ from: a, rel });
  return out;
}

/** Projects this record takes part in, as source, step or result. */
export function projectsFor(id: string): Project[] {
  return projects.filter((p) => p.steps.some((s) => s.id === id));
}

/** Public tag facets present on a record, in a fixed display order. */
export const FACET_ORDER = ["characters", "subjects", "themes", "style", "mood", "setting", "composition", "line", "color_words", "elements"];
export const FACET_LABEL: Record<string, string> = { color_words: "color" };
export function facetsOf(a: Artwork): [string, string[]][] {
  const d = a.described ?? {};
  return FACET_ORDER.filter((f) => Array.isArray(d[f]) && (d[f] as string[]).length).map((f) => [f, d[f] as string[]]);
}

export const RELATION_LABEL: Record<string, [string, string]> = {
  // [outgoing wording, incoming wording]
  variation_of: ["variation of", "variations"],
  source_of: ["led to", "came from"],
  same_characters: ["same characters as", "same characters as"],
  same_scene: ["same scene as", "same scene as"],
  series_pair: ["pairs with", "pairs with"],
  revisits: ["revisits", "revisited in"],
  step_toward: ["step toward", "process steps"],
  near_duplicate: ["near duplicate of", "near duplicate of"],
};

export function mediumLine(a: Artwork): string {
  const c = a.catalog;
  const medium = c.medium ? (c.surface ? `${c.medium} on ${c.surface}` : c.medium) : null;
  return [medium, c.physical_size_in ? `${c.physical_size_in} in` : null].filter(Boolean).join(", ");
}

/** URL-safe slug for a tag, e.g. "hooded pod figure" -> "hooded-pod-figure". */
export const slug = (t: string) => t.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");

/** Recurring characters: tags on at least `min` finished works, most frequent first. */
export function characters(min = 4) {
  const glosses = new Map((vocabulary.facets.characters ?? []).map((t) => [t.tag, t.gloss]));
  const by = new Map<string, Artwork[]>();
  for (const a of works) for (const t of ((a.described?.characters as string[]) ?? [])) by.set(t, [...(by.get(t) ?? []), a]);
  return [...by.entries()]
    .filter(([, list]) => list.length >= min)
    .map(([tag, list]) => {
      const ordered = oldestFirst(list);
      const years = ordered.map((a) => a.catalog.year).filter((y): y is number => typeof y === "number");
      return {
        tag, slug: slug(tag), gloss: glosses.get(tag) || "", works: ordered,
        first: years[0], last: years[years.length - 1],
        series: [...new Set(ordered.map((a) => a.catalog.series_slug))],
      };
    })
    .sort((a, b) => b.works.length - a.works.length || a.tag.localeCompare(b.tag));
}

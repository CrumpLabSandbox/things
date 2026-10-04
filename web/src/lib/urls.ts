// URL helpers that respect the configured base path (/things by default).
const BASE = import.meta.env.BASE_URL.endsWith("/") ? import.meta.env.BASE_URL : import.meta.env.BASE_URL + "/";

/** A site path, e.g. href("work/colorlands/modular/") -> /things/work/colorlands/modular/ */
export function href(p = ""): string {
  return BASE + p.replace(/^\/+/, "");
}

/** A repo-relative file path served as a static asset, with each segment encoded. */
export function asset(repoPath: string): string {
  return BASE + repoPath.split("/").map(encodeURIComponent).join("/");
}

export const workUrl = (id: string) => href(`work/${id}/`);
export const seriesUrl = (slug: string) => href(`series/${slug}/`);
export const projectUrl = (id: string) => href(`process/${id}/`);
export const exploreUrl = (facet?: string, tag?: string) =>
  facet && tag ? href(`explore/?${encodeURIComponent(facet)}=${encodeURIComponent(tag)}`) : href("explore/");

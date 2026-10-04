// Map repo image paths to Astro image metadata so pages can emit resized,
// optimised versions at build time instead of the full originals.
import type { ImageMetadata } from "astro";

const files = import.meta.glob<{ default: ImageMetadata }>(
  ["../../../images/**/*.{jpg,jpeg,png,JPG,JPEG,PNG}", "../../../wip/*.{jpg,jpeg,png}", "../../../playground_images/**/*.{jpg,jpeg,png}", "../../../imgs/*.{jpg,jpeg,png}", "../../../blog/**/*.{jpg,jpeg,png}"],
  { eager: true },
);

const byRepoPath = new Map<string, ImageMetadata>();
for (const [key, mod] of Object.entries(files)) byRepoPath.set(key.replace(/^(\.\.\/){3}/, ""), mod.default);

/** Image metadata for a repo-relative path like "images/Colorlands/Modular.jpg". */
export function img(repoPath: string): ImageMetadata {
  const m = byRepoPath.get(repoPath);
  if (!m) throw new Error(`No image found for ${repoPath}`);
  return m;
}

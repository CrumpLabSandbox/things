// Blog posts are Markdown files in src/content/blog/<slug>.md. The slug keeps
// the old Quarto folder name so post URLs stay the same. Drafts are skipped.
import type { MarkdownInstance } from "astro";

export interface PostFrontmatter {
  title: string;
  description: string;
  date: string | Date;
  cover?: string;
  categories?: string[];
  draft?: boolean;
}

const files = import.meta.glob<MarkdownInstance<PostFrontmatter>>("../content/blog/*.md", { eager: true });

export const posts = Object.entries(files)
  .map(([file, mod]) => ({ slug: file.replace(/^.*\/|\.md$/g, ""), ...mod }))
  .filter((p) => !p.frontmatter.draft)
  .sort((a, b) => +new Date(b.frontmatter.date) - +new Date(a.frontmatter.date));

export const fmtDate = (d: string | Date) =>
  new Date(d).toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric", timeZone: "UTC" });

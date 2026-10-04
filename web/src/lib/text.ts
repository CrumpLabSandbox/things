// Turn short plain-text notes (which may contain markdown links, <url> links
// or bare URLs) into safe HTML paragraphs.
const esc = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

export function notesToHtml(text: string | null | undefined): string {
  if (!text) return "";
  return text
    .split(/\n\s*\n/)
    .map((para) => {
      const links: string[] = [];
      const keep = (html: string) => `\u0000${links.push(html) - 1}\u0000`;
      let s = para.trim()
        .replace(/\[([^\]]+)\]\((https?:[^)\s]+)\)/g, (_, t, u) => keep(`<a href="${esc(u)}">${esc(t)}</a>`))
        .replace(/<(https?:[^>\s]+)>/g, (_, u) => keep(`<a href="${esc(u)}">${esc(u.replace(/^https?:\/\//, ""))}</a>`));
      s = esc(s).replace(/(https?:\/\/[^\s<]+)/g, (u) => `<a href="${u}">${u.replace(/^https?:\/\//, "")}</a>`);
      s = s.replace(/\u0000(\d+)\u0000/g, (_, i) => links[Number(i)]).replace(/\n/g, "<br>");
      return `<p>${s}</p>`;
    })
    .join("");
}

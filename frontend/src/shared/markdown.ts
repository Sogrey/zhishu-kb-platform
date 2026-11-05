import MarkdownIt from "markdown-it";

const md = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true,
});

/** 包一层便于横滑与圆角，避免裸 table 撑破气泡。 */
export function renderMarkdown(src: string): string {
  const html = md.render(src || "");
  return html
    .replace(/<table>/g, '<div class="md-table"><table>')
    .replace(/<\/table>/g, "</table></div>");
}

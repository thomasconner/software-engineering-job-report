// Turns an article file (front matter + Markdown + ::chart / ::compare directives) into HTML and a directive list.
import { marked } from 'https://cdn.jsdelivr.net/npm/marked@15.0.12/+esm';

const FRONT_MATTER = /^---\r?\n([\s\S]*?)\r?\n---\r?\n?/;
const DIRECTIVE = /^::(chart|compare)\{(.*)\}\s*$/;
const ATTR = /([\w-]+)="([^"]*)"/g;

function parseFrontMatter(text) {
  const match = text.match(FRONT_MATTER);
  if (!match) return { meta: {}, body: text };
  const meta = {};
  for (const line of match[1].split(/\r?\n/)) {
    const kv = line.match(/^(\w+):\s*(.*)$/);
    if (kv) meta[kv[1]] = kv[2].replace(/^"(.*)"$/, '$1').replaceAll('\\"', '"');
  }
  return { meta, body: text.slice(match[0].length) };
}

export function parseArticle(text) {
  const { meta, body } = parseFrontMatter(text);
  const directives = [];
  // Directives become empty placeholders so Markdown never sees them; charts mount into the placeholders later.
  const md = body.split(/\r?\n/).map((line) => {
    const d = line.trim().match(DIRECTIVE);
    if (!d) return line;
    const attrs = Object.fromEntries([...d[2].matchAll(ATTR)].map((a) => [a[1], a[2]]));
    directives.push({ name: d[1], attrs });
    return `\n<div class="directive" data-directive="${directives.length - 1}"></div>\n`;
  }).join('\n');
  return { meta, directives, html: marked.parse(md) };
}

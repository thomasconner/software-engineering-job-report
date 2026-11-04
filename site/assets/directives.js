// Placing and mounting article directives: which strip becomes the topline, and the mount sequence.
// Kept free of the DOM and of the renderers so it can be tested in node.
import { directiveWidth } from './article.js';
import { loadBreakdown } from './data.js';

const EDITORS_NOTE = /^editor['’]s note\b/i;

/**
 * Is this block an editor's note: a paragraph that is all italic and starts with "Editor's note"?
 * Takes plain facts about the block so the rule is testable without a DOM.
 */
export const isEditorsNote = ({ tag, allItalic, text }) => tag === 'P' && allItalic && EDITORS_NOTE.test(text.trim());

/**
 * Where the topline strip goes. `blocks` are the article body's top-level blocks in order, each
 * {tag, name, error, editorsNote}, where `name` is set for directives. The first ::compare before the first
 * section head moves to the top of the body, under the byline; an opening editor's note stays above it, so a
 * correction is still the first thing a reader sees. Returns {from, to} (move block `from` to just before
 * block `to`), or null when there is nothing to move: no section head, or no working strip before it.
 */
export function toplinePlan(blocks) {
  const head = blocks.findIndex((b) => b.tag === 'H2');
  if (head === -1) return null;
  const from = blocks.slice(0, head).findIndex((b) => b.name === 'compare' && !b.error);
  if (from === -1) return null;
  const to = blocks[0].editorsNote && from !== 0 ? 1 : 0;
  return { from, to };
}

/**
 * Mount one directive. The width is set before anything waits, so a wide chart is laid out at its own width
 * from the start instead of drawing at the text width and then jumping. A breakdown's series are fetched
 * first (data.loadBreakdown); `render` draws, and `onError` shows a failure in place. Resolves to true when
 * the directive drew and false when it failed, so a caller can treat a render-time failure (an unknown metric,
 * say) the same as a parse error.
 */
export async function mountDirective(mount, name, attrs, data, until, { render, fetchJson, onError }) {
  mount.dataset.width = directiveWidth(name, attrs);
  try {
    if (attrs.breakdown) await loadBreakdown(data, attrs.breakdown, fetchJson);
    render(mount, name, attrs, data, until);
    return true;
  } catch (err) {
    onError(mount, err);
    return false;
  }
}

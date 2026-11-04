// Checks where the topline strip goes and how a directive is mounted (site/assets/directives.js).
// Run by tests/test_renderer.py with the path to the module.
import assert from 'node:assert/strict';

const { toplinePlan, isEditorsNote, mountDirective } = await import(process.argv[2]);

const p = { tag: 'P' };
const h2 = { tag: 'H2' };
const strip = { tag: 'DIV', name: 'compare', error: false };
const chart = { tag: 'DIV', name: 'chart', error: false };
const note = { tag: 'P', editorsNote: true };

// The first working strip before the first section head moves to the top.
assert.deepEqual(toplinePlan([p, p, strip, h2, p]), { from: 2, to: 0 });
assert.deepEqual(toplinePlan([strip, p, h2]), { from: 0, to: 0 });
// Only a strip before the first section head counts, and only when the article has a section head.
assert.equal(toplinePlan([p, h2, strip, p]), null);
assert.equal(toplinePlan([p, strip, p]), null);
assert.equal(toplinePlan([p, chart, p, h2]), null);
// A strip whose directive failed to parse stays where it was; a working one after it is used instead.
assert.equal(toplinePlan([p, { ...strip, error: true }, h2]), null);
assert.deepEqual(toplinePlan([p, { ...strip, error: true }, strip, h2]), { from: 2, to: 0 });
// An opening editor's note stays above the strip.
assert.deepEqual(toplinePlan([note, p, strip, h2]), { from: 2, to: 1 });
assert.deepEqual(toplinePlan([note, strip, p, h2]), { from: 1, to: 1 });
// A note further down is not a lead note.
assert.deepEqual(toplinePlan([p, note, strip, h2]), { from: 2, to: 0 });

assert.equal(isEditorsNote({ tag: 'P', allItalic: true, text: "Editor's note, November 4, 2026: we revised…" }), true);
assert.equal(isEditorsNote({ tag: 'P', allItalic: true, text: ' Editor’s note: curly apostrophe' }), true);
assert.equal(isEditorsNote({ tag: 'P', allItalic: false, text: "Editor's note: partly italic" }), false);
assert.equal(isEditorsNote({ tag: 'P', allItalic: true, text: 'An italic lede' }), false);
assert.equal(isEditorsNote({ tag: 'BLOCKQUOTE', allItalic: true, text: "Editor's note" }), false);

// Mounting: the width is set before the breakdown fetch is awaited, then the breakdown loads, then it renders.
const events = [];
let release;
const gate = new Promise((r) => { release = r; });
const data = { breakdowns: { work_mode: { file: 'breakdowns/work_mode.json' } } };
const mount = { dataset: {} };
const done = mountDirective(mount, 'chart', { type: 'line', breakdown: 'work_mode' }, data, '2026-10', {
  fetchJson: async (url) => { events.push(`fetch ${url} width=${mount.dataset.width}`); await gate; return { series: [] }; },
  render: () => events.push(`render series=${Array.isArray(data.breakdowns.work_mode.series)}`),
  onError: (_, err) => events.push(`error ${err.message}`),
});
assert.equal(mount.dataset.width, 'wide');
release();
await done;
assert.deepEqual(events, ['fetch data/breakdowns/work_mode.json width=wide', 'render series=true']);

// A directive without a breakdown never fetches; a failed fetch shows an error in place and keeps the width.
const plain = { dataset: {} };
await mountDirective(plain, 'chart', { type: 'dot', metric: 'x' }, data, '2026-10', {
  fetchJson: () => assert.fail('fetched'), render: () => {}, onError: () => assert.fail('error'),
});
assert.equal(plain.dataset.width, 'column');
const failed = { dataset: {} };
const errors = [];
await mountDirective(failed, 'chart', { type: 'stacked-area', breakdown: 'seniority' }, { breakdowns: { seniority: { file: 'breakdowns/seniority.json' } } }, '2026-10', {
  fetchJson: async () => { throw new Error('offline'); }, render: () => assert.fail('rendered'), onError: (_, err) => errors.push(err.message),
});
assert.deepEqual(errors, ['offline']);
assert.equal(failed.dataset.width, 'wide');

// A strip that parses but fails when drawn (an unknown metric) reports failure, and the topline skips it for a
// working strip after it, as app.renderBody does with the result.
const shown = [];
const broken = { dataset: {} };
const ok = await mountDirective(broken, 'compare', { metrics: 'nope.metric' }, {}, '2026-10', {
  fetchJson: () => assert.fail('fetched'),
  render: () => { throw new Error('Unknown metric "nope.metric"'); },
  onError: (_, err) => shown.push(err.message),
});
assert.equal(ok, false);
assert.deepEqual(shown, ['Unknown metric "nope.metric"']);
assert.equal(broken.dataset.width, 'wide');
const working = await mountDirective({ dataset: {} }, 'compare', { metrics: 'posts.hiring' }, {}, '2026-10', {
  fetchJson: () => assert.fail('fetched'), render: () => {}, onError: () => assert.fail('error'),
});
assert.equal(working, true);
assert.deepEqual(toplinePlan([p, { ...strip, error: !ok }, { ...strip, error: !working }, h2]), { from: 2, to: 0 });
assert.equal(toplinePlan([p, { ...strip, error: !ok }, h2]), null);

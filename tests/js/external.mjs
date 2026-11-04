// Checks the external-benchmark helpers in data.js and the directive checks in article.js.
// Run by tests/test_renderer.py with the paths to both modules.
import assert from 'node:assert/strict';

const data = await import(process.argv[2]);
const { parseArticle } = await import(process.argv[3]);

const months = ['2025-01', '2025-02', '2025-03', '2025-04'];
const external = (overrides = {}) => ({
  label: 'Indeed US software postings', unit: 'index', credit: 'Indeed Hiring Lab', license: 'CC BY 4.0',
  license_url: 'https://creativecommons.org/licenses/by/4.0/', source_url: 'https://github.com/hiring-lab',
  seasonally_adjusted: true,
  series: months.map((month, i) => ({ month, value: 50 + 10 * i, ref_period: `${month}-03`, vintage_date: `${month}-06` })),
  ...overrides,
});
const prepared = (ext, pending = []) => data.prepare({ months, pending, metrics: {}, breakdowns: {}, external: { 'x.US': ext } });

// resolveExternal clips to the issue month and drops pending months.
let s = data.resolveExternal(prepared(external(), ['2025-04']), 'x.US', '2025-04');
assert.deepEqual(s.points.map((p) => p.month), ['2025-01', '2025-02', '2025-03']);
assert.equal(s.external, true);
assert.equal(s.smoothed, false);
assert.equal(s.licenseUrl, 'https://creativecommons.org/licenses/by/4.0/');
s = data.resolveExternal(prepared(external()), 'x.US', '2025-02');
assert.deepEqual(s.points.map((p) => p.month), ['2025-01', '2025-02']);
assert.throws(() => data.resolveExternal(prepared(external()), 'y.US', '2025-04'), data.AuthoringError);

// indexTo rebases to 100 at the base month and refuses a base with no value.
const indexed = data.indexTo(data.resolveExternal(prepared(external()), 'x.US', '2025-04'), '2025-02');
assert.equal(indexed.unit, 'index');
assert.deepEqual(indexed.points.map((p) => +p.value.toFixed(2)), [83.33, 100, 116.67, 133.33]);
assert.equal(indexed.points[0].ref_period, '2025-01-03');
assert.throws(() => data.indexTo(indexed, '2024-12'), data.AuthoringError);

// An unadjusted series is drawn as a 12-month trailing average; months without a full year drop out.
const year = Array.from({ length: 14 }, (_, i) => data.addMonths('2024-01', i));
const seasonal = external({
  seasonally_adjusted: false,
  series: year.map((month, i) => ({ month, value: i % 12 === 11 ? 130 : 100, ref_period: month, vintage_date: month })),
});
const smooth = data.resolveExternal(data.prepare({ months: year, metrics: {}, breakdowns: {}, external: { 'x.US': seasonal } }), 'x.US', '2025-02');
assert.equal(smooth.smoothed, true);
assert.deepEqual(smooth.points.map((p) => p.month), ['2024-12', '2025-01', '2025-02']);
assert.deepEqual(smooth.points.map((p) => p.value), [102.5, 102.5, 102.5]);
assert.deepEqual(data.trailingYear([{ month: '2024-01', value: 1 }]), []);

// Directive checks: external needs base, base must be a month, and one metric only.
const error = (attrs) => parseArticle(`::chart{type="line" title="t" ${attrs}}\n`).directives[0].error?.message ?? null;
assert.equal(error('metric="posts.hiring" external="x.US" base="2022-01"'), null);
assert.match(error('metric="posts.hiring" external="x.US"'), /base/);
assert.match(error('metric="posts.hiring" base="2022-01"'), /base/);
assert.match(error('metric="posts.hiring" external="x.US" base="2022"'), /base/);
assert.match(error('metric="posts.hiring,posts.seeking" external="x.US" base="2022-01"'), /exactly one metric/);
assert.match(parseArticle('::chart{type="bar" title="t" metric="posts.hiring" external="x.US" base="2022-01"}\n').directives[0].error.message, /does not take/);

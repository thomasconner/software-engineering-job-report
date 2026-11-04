// Checks outside series as compare rows and as external-only line charts (data.js + article.js).
// Run by tests/test_renderer.py with the paths to both modules.
import assert from 'node:assert/strict';

const data = await import(process.argv[2]);
const { parseArticle } = await import(process.argv[3]);

const months = Array.from({ length: 61 }, (_, i) => data.addMonths('2021-10', i));
const at = (m, value, extra = {}) => ({ month: m, value, ...extra });
const raw = data.prepare({
  months,
  metrics: {
    'posts.hiring': {
      label: 'Hiring posts', unit: 'count', method: 'count', polarity: 1, sources: ['hiring'],
      series: [
        at('2021-10', 781, { n: 781 }), at('2025-10', 351, { n: 351 }), at('2026-07', 274, { n: 274 }),
        // A 1y fall of 18% sits inside this bar, so the HN row says "about the same".
        at('2026-10', 289, { n: 289, bar: { '3m': 0.342, '1y': 0.338, '5y': 0.329 } }),
      ],
    },
  },
  breakdowns: {},
  external: {
    'indeed_software_postings.US': {
      label: 'Indeed US software development job postings', unit: 'index', publisher: 'Indeed Hiring Lab',
      credit: 'Indeed Hiring Lab, job postings tracker', license: 'CC BY 4.0', source_url: 'https://github.com/hiring-lab/job_postings_tracker',
      seasonally_adjusted: true, smooth_12m: false,
      series: [
        at('2021-10', 177.99, { ref_period: '2021-10-01' }), at('2025-10', 63.57, { ref_period: '2025-10-03' }),
        at('2026-07', 72.51, { ref_period: '2026-06-26' }),
        // The issue's own vintage carries its comparison readings; they differ from the values
        // stored for those earlier issues (63.57, 177.99) because the publisher revised them.
        at('2026-10', 78.33, {
          ref_period: '2026-10-02',
          compare: { '3m': { ref_period: '2026-07-02', value: 72.9 }, '1y': { ref_period: '2025-10-02', value: 64.0 }, '5y': { ref_period: '2021-10-01', value: 175.0 } },
        }),
      ],
    },
    'jolts_openings_information.US': {
      label: 'Job openings, information sector', unit: 'thousands', publisher: 'U.S. Bureau of Labor Statistics',
      credit: 'BLS, JOLTS', license: 'public domain', seasonally_adjusted: false, smooth_12m: true,
      series: months.map((m, i) => at(m, i === 60 ? 128 : 169, {
        ref_period: data.addMonths(m, -2),
        // No same-month 5y reading in this vintage (a skipped release).
        ...(i === 60 ? { compare: { '3m': { ref_period: '2026-05', value: 65 }, '1y': { ref_period: '2025-08', value: 160 } } } : {}),
      })),
    },
    'ces_computer_systems_design.US': {
      label: 'Employment in computer systems design', unit: 'thousands', publisher: 'U.S. Bureau of Labor Statistics',
      credit: 'BLS, CES', license: 'public domain', seasonally_adjusted: true, smooth_12m: false,
      // The newest issue has no value yet.
      series: [at('2026-07', 2374.6, { ref_period: '2026-06' })],
    },
  },
});

// Compare rows mix HN metrics and external:<key> ids, in the order written.
const rows = data.resolveCompareRows(raw, 'external:indeed_software_postings.US, posts.hiring,external:jolts_openings_information.US', '2026-10');
assert.deepEqual(rows.map((r) => r.key), ['indeed_software_postings.US', 'posts.hiring', 'jolts_openings_information.US']);
assert.equal(rows[0].external, true);
assert.equal(rows[2].seasonallyAdjusted, false);
// The strip prints published values: an unadjusted JOLTS row is never smoothed.
assert.equal(rows[2].smoothed, false);
assert.equal(data.valueAt(rows[2], '2026-10'), 128);
assert.throws(() => data.resolveCompareRows(raw, 'external:nope.US', '2026-10'), data.AuthoringError);

const windows = ['3m', '1y', '5y'];
const indeed = data.compareCells(rows[0], '2026-10', windows);
assert.equal(indeed.value, '78.3');
assert.equal(indeed.ref, 'Oct 2, 2026 data');
const [, y1, y5] = indeed.deltas;
// A plain change in percent with no verdict: no "≈", no better/worse word. It uses the
// same-vintage reading (64.0), not the value first published for October 2025 (63.57).
assert.equal(y1.change.text, '+22%');
assert.equal(y1.change.mark, '▲');
assert.equal(y1.change.tone, 'flat');
assert.equal(y1.change.word, '');
assert.equal(y1.was, 'from 64.0, Oct 2, 2025 data');
assert.equal(y5.change.text, '−55%');
assert.notEqual(y5.change.mark, '≈');

const jolts = data.compareCells(rows[2], '2026-10', windows);
assert.equal(jolts.value, '128,000');
assert.equal(jolts.ref, 'Aug 2026 data');
// Unadjusted, and May against August: the 3m cell says "seasonal" rather than a change.
assert.equal(jolts.deltas[0].seasonal, true);
assert.equal(jolts.deltas[0].change, null);
assert.equal(jolts.deltas[0].was, 'from 65,000, May 2026 data');
// Same calendar month a year apart: a plain change.
assert.equal(jolts.deltas[1].change.text, '−20%');
assert.equal(jolts.deltas[1].was, 'from 160,000, Aug 2025 data');
// No same-month reading in this vintage.
assert.equal(jolts.deltas[2].change, null);
assert.equal(jolts.deltas[2].missing, 'No same-month value');

// An outside series with no value for the issue month.
const [ces] = data.resolveCompareRows(raw, 'external:ces_computer_systems_design.US', '2026-10');
const missing = data.compareCells(ces, '2026-10', windows);
assert.equal(missing.value, 'n/a');
assert.equal(missing.ref, null);
assert.ok(missing.deltas.every((d) => d.change === null && d.missing === 'No data'));

// The HN row keeps its noise verdict and has no reference period.
const hn = data.compareCells(rows[1], '2026-10', windows);
assert.equal(hn.ref, null);
assert.equal(hn.deltas[1].change.mark, '≈');
assert.equal(hn.deltas[1].was, 'from 351');

// Compare ids: external:<key> is allowed; an empty id is an authoring error.
const error = (src) => parseArticle(`${src}\n`).directives[0].error?.message ?? null;
assert.equal(error('::compare{title="t" metrics="external:indeed_software_postings.US,posts.hiring"}'), null);
assert.match(error('::compare{title="t" metrics="posts.hiring,external:"}'), /empty id/);
assert.match(error('::compare{title="t" metrics="posts.hiring,,posts.seeking"}'), /empty id/);
assert.equal(error('::compare{title="t" metrics="external: indeed_software_postings.US"}'), null);
assert.equal(data.resolveCompareRows(raw, 'external: indeed_software_postings.US', '2026-10')[0].key, 'indeed_software_postings.US');
assert.match(error('::compare{title="t" metrics="External:indeed_software_postings.US"}'), /lowercase external:/);
assert.match(error('::chart{type="line" title="t" external="a.US,b.US"}'), /one key/);

// An external-only line: no metric, no base, values in the series' own unit.
assert.equal(error('::chart{type="line" title="t" external="indeed_software_postings.US"}'), null);
assert.match(error('::chart{type="line" title="t" external="indeed_software_postings.US" base="2025-10"}'), /drop base/);
assert.match(error('::chart{type="line" title="t"}'), /metric or breakdown/);
assert.match(error('::chart{type="line" title="t" metric="posts.hiring" external="x.US"}'), /needs base/);
assert.match(error('::chart{type="bar" title="t" external="indeed_software_postings.US"}'), /does not take/);

const only = data.resolveChartSeries(raw, { type: 'line', external: 'indeed_software_postings.US' }, '2026-10');
assert.equal(only.length, 1);
assert.equal(only[0].unit, 'index');
assert.deepEqual(only[0].points.map((p) => p.value), [177.99, 63.57, 72.51, 78.33]);
// Charts still draw an unadjusted, smooth_12m series as a 12-month average.
const smooth = data.resolveChartSeries(raw, { type: 'line', external: 'jolts_openings_information.US' }, '2026-10');
assert.equal(smooth[0].smoothed, true);
assert.equal(smooth[0].unit, 'thousands');
assert.equal(+data.valueAt(smooth[0], '2026-10').toFixed(2), +((169 * 11 + 128) / 12).toFixed(2));

// The paired form still indexes both lines to base.
const paired = data.resolveChartSeries(raw, { type: 'line', metric: 'posts.hiring', external: 'indeed_software_postings.US', base: '2025-10' }, '2026-10');
assert.deepEqual(paired.map((s) => s.unit), ['index', 'index']);
assert.equal(data.valueAt(paired[1], '2025-10'), 100);

// from before an outside series' first value is an authoring error.
assert.throws(() => data.resolveChartSeries(raw, { type: 'line', external: 'indeed_software_postings.US', from: '2021-01' }, '2026-10'), /before indeed_software_postings.US starts/);
assert.equal(data.resolveChartSeries(raw, { type: 'line', external: 'indeed_software_postings.US', from: '2021-10' }, '2026-10').length, 1);

// The masthead ribbon: front matter wins; otherwise HN before November 2026, Indeed from then on.
assert.equal(data.ribbonKey({ month: '2026-10' }), 'posts.hiring');
assert.equal(data.ribbonKey({ month: '2026-11' }), 'external:indeed_software_postings.US');
assert.equal(data.ribbonKey({ month: '2026-10', ribbon: 'external:ces_computer_systems_design.US' }), 'external:ces_computer_systems_design.US');

// Units: thousands print as whole numbers and ticks in K or M.
assert.equal(data.makeFormat('thousands')(2355.4), '2,355,400');
assert.equal(data.tickFormat('thousands')(2400), '2.4M');
assert.equal(data.tickFormat('thousands')(150), '150K');
// The source line has no HN clause when no series comes from HN.
assert.equal(data.sourceLine(only), '');
assert.match(data.sourceLine(rows), /Who is hiring\?/);

// layout: float or wide on regular charts; the strip and small multiples are always wide and don't take it.
assert.equal(error('::chart{type="line" metric="posts.hiring" title="t" layout="wide"}'), null);
assert.equal(error('::chart{type="dot" breakdown="industry" title="t" layout="float"}'), null);
assert.match(error('::chart{type="line" metric="posts.hiring" title="t" layout="left"}'), /float or wide/);
assert.match(error('::chart{type="small-multiples" breakdown="stack" title="t" layout="float"}'), /does not take "layout"/);
assert.match(error('::compare{title="t" metrics="posts.hiring" layout="wide"}'), /does not take "layout"/);

// Checks data.js change() against exported bars. Run by tests/test_renderer.py.
import assert from 'node:assert/strict';

const data = await import(process.argv[2]);

function resolve(unit, a, b, bar) {
  const metrics = {
    'x.hiring': {
      label: 'x', unit, method: 'count', polarity: 1, series: [
        { month: '2025-10', value: a, n: 300 },
        { month: '2026-10', value: b, n: 300, bar: { '1y': bar } },
      ],
    },
  };
  const prepared = data.prepare({ months: ['2025-10', '2026-10'], metrics, breakdowns: {} });
  return data.resolveSeries(prepared, { metric: 'x.hiring' }, '2026-10')[0];
}

const verdict = (unit, a, b, bar) => data.change(resolve(unit, a, b, bar), '2025-10', '2026-10').word;

// Relative units use ln(now/then): a 30% fall is ln 0.7 = -0.357, outside a 0.33 bar,
// and a 38% rise is ln 1.38 = 0.322, inside it.
assert.equal(verdict('count', 100, 70, 0.33), 'worse');
assert.equal(verdict('count', 100, 138, 0.33), 'about the same');
assert.equal(verdict('usd', 200000, 220000, 0.099), 'about the same');
assert.equal(verdict('usd', 200000, 222000, 0.099), 'better');
// Shares compare the difference in share units.
assert.equal(verdict('share', 0.2, 0.29, 0.1), 'about the same');
assert.equal(verdict('share', 0.2, 0.31, 0.1), 'better');

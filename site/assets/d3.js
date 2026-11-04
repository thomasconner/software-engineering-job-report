// d3 ships as one pinned UMD bundle (vendor/d3-7.9.0.min.js). Importing it for its side effect sets
// globalThis.d3, which avoids the request waterfall of d3's per-package ES modules on a CDN.
import './vendor/d3-7.9.0.min.js';

export default globalThis.d3;

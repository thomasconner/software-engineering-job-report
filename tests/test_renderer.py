import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_change_uses_the_exported_bar():
    subprocess.run(
        ["node", ROOT / "tests/js/change.mjs", ROOT / "site/assets/data.js"],
        check=True,
    )


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_external_benchmark_helpers():
    subprocess.run(
        [
            "node",
            ROOT / "tests/js/external.mjs",
            ROOT / "site/assets/data.js",
            ROOT / "site/assets/article.js",
        ],
        check=True,
    )


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_outside_series_in_compare_and_external_only_lines():
    subprocess.run(
        [
            "node",
            ROOT / "tests/js/outside.mjs",
            ROOT / "site/assets/data.js",
            ROOT / "site/assets/article.js",
        ],
        check=True,
    )


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_topline_placement_and_directive_mounting():
    subprocess.run(
        ["node", ROOT / "tests/js/directives.mjs", ROOT / "site/assets/directives.js"],
        check=True,
    )

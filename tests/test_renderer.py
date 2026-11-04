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

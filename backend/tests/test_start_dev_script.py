from pathlib import Path

import pytest


def test_start_dev_fails_fast_instead_of_silently_skipping_backend() -> None:
    script_path = Path(__file__).resolve().parents[2] / "start-dev.ps1"
    if not script_path.exists():
        pytest.skip("start-dev.ps1 is a local ignored helper script")

    script = script_path.read_text(encoding="utf-8")

    assert "function Assert-PortAvailable" in script
    assert "Backend start skipped" not in script

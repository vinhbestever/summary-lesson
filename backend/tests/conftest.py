from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(autouse=True)
def isolate_feedback_cache_dir(tmp_path, monkeypatch):
    monkeypatch.setenv('FEEDBACK_CACHE_DIR', str(tmp_path / 'feedback_cache'))

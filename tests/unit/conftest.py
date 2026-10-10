import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


@pytest.fixture(autouse=True)
def _block_real_anki(monkeypatch):
    """모킹하지 않은 AnkiConnect 호출이 실제 Anki로 나가지 않게 막는다."""
    from integrations import anki_connect

    def _refuse(*args, **kwargs):
        raise AssertionError("unit test attempted a real AnkiConnect HTTP call")

    monkeypatch.setattr(anki_connect._SESSION, "post", _refuse)

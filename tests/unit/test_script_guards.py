"""이미 실행된 일괄 승격 스크립트는 --yes 없이 아무것도 하면 안 된다.

주의: 스크립트를 subprocess로 실행하지 않는다 (conftest의 Anki 차단이 적용되지 않아
2026-10-10에 실제 노트 37개가 재승격됐다). 같은 프로세스에서 main(argv)를 부르고,
promote_chunk는 호출되면 실패하는 가짜로 바꾼다.
"""
import importlib

import pytest

from backend.services.corpus_service import CorpusService


@pytest.mark.parametrize("module", ["scripts.execute_batch_2_promotion", "scripts.execute_batch_20_promotion"])
def test_promotion_script_does_nothing_without_yes(module, monkeypatch, capsys):
    def must_not_run(req):
        raise AssertionError("promote_chunk called without --yes")

    monkeypatch.setattr(CorpusService, "promote_chunk", staticmethod(must_not_run))
    mod = importlib.import_module(module)
    assert mod.main([]) == 1
    assert "--yes" in capsys.readouterr().out

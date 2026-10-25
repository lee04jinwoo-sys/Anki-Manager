"""카드 뒷면 연결 표시: 맥 터널 주소(8011)로 묻고, 중국어 문장 템플릿에는 표시 블록을 한 번만 넣는다."""
from core import card_templates as ct
from core import link_manager
from integrations.anki_connect import AnkiConnector

ZH_BACK = """<script>(function(){})();</script>
<div class="title">
  {{뜻}}
</div>

<hr>

<div class="title zh-sentence" lang="zh-Hans">
  {{문장}} {{소리}}
  <div class="pinyin" lang="zh-Latn">{{한어병음}}</div>
</div>

<div class="deck">{{Deck}}</div>"""


def test_english_sentence_back_asks_the_mac_tunnel_not_8001():
    from scripts.update_sentence_highlight import SENTENCE_BACK_TEMPLATE
    assert "127.0.0.1:8001" not in SENTENCE_BACK_TEMPLATE
    assert "http://127.0.0.1:8011/api/links/badge/sentence?text=" in SENTENCE_BACK_TEMPLATE


def test_zh_badge_wraps_sentence_and_adds_block_with_zh_lookup():
    out = ct.inject_zh_sentence_badge(ZH_BACK)
    assert out.count('<span id="alm-zh-sentence-text">{{문장}}</span>') == 1
    assert "http://127.0.0.1:8011/api/links/badge/sentence?lang=zh&text=" in out
    assert "function zhHighlight" in out
    for kept in ("{{소리}}", "{{한어병음}}", "{{뜻}}", "{{Deck}}", "<hr>"):
        assert kept in out


def test_zh_badge_is_idempotent_and_removable():
    once = ct.inject_zh_sentence_badge(ZH_BACK)
    assert ct.inject_zh_sentence_badge(once) == once
    assert ct.remove_zh_sentence_badge(once) == ZH_BACK


def test_apply_updates_every_chinese_sentence_card(monkeypatch):
    calls = []

    def invoke(cls, action, **params):
        calls.append((action, params))
        if action == "modelTemplates":
            return {"카드 1": {"Front": "F1", "Back": ZH_BACK}, "카드 2": {"Front": "F2", "Back": ZH_BACK}}
        return None

    monkeypatch.setattr(AnkiConnector, "invoke", classmethod(invoke))
    ct.apply_zh_sentence_badge()
    update = [p for a, p in calls if a == "updateModelTemplates"]
    assert len(update) == 1
    model = update[0]["model"]
    assert model["name"] == "Chinese Sentence"
    assert {k: v["Front"] for k, v in model["templates"].items()} == {"카드 1": "F1", "카드 2": "F2"}
    assert all("alm-zh-sentence-text" in v["Back"] for v in model["templates"].values())


def test_template_backup_includes_chinese_sentence(monkeypatch, tmp_path):
    monkeypatch.setattr(link_manager, "BACKUP_DIR", tmp_path)
    seen = []
    monkeypatch.setattr(AnkiConnector, "invoke", classmethod(lambda cls, action, **p: seen.append(p.get("modelName")) or {}))
    link_manager.backup_templates()
    assert "Chinese Sentence" in seen


def test_retarget_changes_only_the_badge_address():
    back = 'x <script>fetch("http://127.0.0.1:8001/api/links/badge/sentence?text=" + t)</script> 127.0.0.1:8001 elsewhere'
    out = ct.retarget_badge_url(back)
    assert out == 'x <script>fetch("http://127.0.0.1:8011/api/links/badge/sentence?text=" + t)</script> 127.0.0.1:8001 elsewhere'
    assert ct.retarget_badge_url(out) == out


def test_apply_english_retarget_touches_only_cards_that_use_the_badge(monkeypatch):
    old = 'fetch("http://127.0.0.1:8001/api/links/badge/sentence?text=" + t)'
    models = {
        "English Sentence": {"Card 1": {"Front": "F", "Back": old}},
        "English Grammar": {"Card 1": {"Front": "G1", "Back": "plain"}, "Card 3": {"Front": "G3", "Back": old}},
    }
    updates = []

    def invoke(cls, action, **p):
        if action == "modelTemplates":
            return models[p["modelName"]]
        if action == "updateModelTemplates":
            updates.append(p["model"])

    monkeypatch.setattr(AnkiConnector, "invoke", classmethod(invoke))
    ct.apply_english_badge_url()
    by_name = {m["name"]: m["templates"] for m in updates}
    assert set(by_name) == {"English Sentence", "English Grammar"}
    assert by_name["English Grammar"]["Card 1"]["Back"] == "plain"
    assert "127.0.0.1:8011" in by_name["English Grammar"]["Card 3"]["Back"]
    assert "127.0.0.1:8011" in by_name["English Sentence"]["Card 1"]["Back"]

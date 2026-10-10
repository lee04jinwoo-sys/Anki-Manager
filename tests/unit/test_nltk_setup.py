"""setup_nltk: zip으로만 설치된 코퍼스(wordnet.zip)도 설치된 것으로 보고 다시 다운로드하지 않는다."""
import nltk

from utils import pos_automator


def test_zip_only_corpora_do_not_trigger_download(monkeypatch):
    installed = {
        "tokenizers/punkt", "tokenizers/punkt_tab",
        "taggers/averaged_perceptron_tagger", "taggers/averaged_perceptron_tagger_eng",
        "corpora/wordnet.zip", "corpora/omw-1.4.zip",
    }

    def find(name, *a, **k):
        if name in installed:
            return name
        raise LookupError(name)

    downloads = []
    monkeypatch.setattr(nltk.data, "find", find)
    monkeypatch.setattr(nltk, "download", lambda pkg, *a, **k: downloads.append(pkg))
    pos_automator.setup_nltk()
    assert downloads == []


def test_missing_resource_is_downloaded(monkeypatch):
    def find(name, *a, **k):
        if name.startswith("corpora/wordnet"):
            raise LookupError(name)
        return name

    downloads = []
    monkeypatch.setattr(nltk.data, "find", find)
    monkeypatch.setattr(nltk, "download", lambda pkg, *a, **k: downloads.append(pkg))
    pos_automator.setup_nltk()
    assert downloads == ["wordnet"]

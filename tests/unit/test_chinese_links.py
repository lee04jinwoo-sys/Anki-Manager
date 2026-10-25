"""
Unit tests for multi-language (Chinese / English) link management.
"""

import pytest
from fastapi.testclient import TestClient
from server import app
from core.link_manager import LinkManager

client = TestClient(app)

def test_chinese_link_stats():
    """Verify Chinese link stats retrieval via LinkManager and API."""
    stats = LinkManager.get_stats(lang="zh")
    assert "total_vocab" in stats
    assert "total_links" in stats
    assert "unlinked_vocab" in stats
    assert "leech_count" in stats
    assert stats["total_vocab"] >= 690

    # API Endpoint check
    resp = client.get("/api/links/stats?lang=zh")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_vocab"] == stats["total_vocab"]

def test_chinese_vocab_list():
    """Verify Chinese vocabulary list pagination and filtering."""
    resp = client.get("/api/links/vocab?lang=zh&limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert len(data["items"]) <= 10
    if data["items"]:
        item = data["items"][0]
        assert "word" in item
        assert "meaning" in item
        assert "link_count" in item

def test_english_stats_isolation():
    """Verify that English and Chinese stats remain completely isolated."""
    en_stats = LinkManager.get_stats(lang="en")
    zh_stats = LinkManager.get_stats(lang="zh")
    assert en_stats["total_vocab"] != zh_stats["total_vocab"]
    assert en_stats["total_vocab"] >= 8000
    assert zh_stats["total_vocab"] < 1000

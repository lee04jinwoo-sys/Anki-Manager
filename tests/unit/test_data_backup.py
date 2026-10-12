"""서버 data/ 일일 스냅샷: SQLite는 백업 API로, 바뀌지 않은 파일은 전날 스냅샷에 하드링크, 오래된 스냅샷 정리."""
import datetime
import os
import sqlite3

import pytest

from utils import data_backup as db


@pytest.fixture
def layout(tmp_path):
    data = tmp_path / "data"
    (data / "backups" / "promote").mkdir(parents=True)
    (data / "logs").mkdir()
    con = sqlite3.connect(data / "links.db")
    con.execute("create table t (x)")
    con.executemany("insert into t values (?)", [(i,) for i in range(100)])
    con.commit()
    con.close()
    (data / "settings.json").write_text('{"a": 1}')
    (data / "backups" / "promote" / "n1.json").write_text("{}")
    (data / "big_static.txt").write_text("x" * 10_000)
    (data / "links.db-wal").write_text("stale wal")       # 스냅샷에는 넣지 않는다
    (data / "logs" / "noise.log").write_text("log")       # 로그는 넣지 않는다
    return data, tmp_path / "snapshots"


D1 = datetime.date(2026, 10, 12)


def test_snapshot_copies_files_and_consistent_sqlite(layout):
    data, root = layout
    snap = db.snapshot(data, root, D1)

    assert snap == root / "2026-10-12"
    con = sqlite3.connect(snap / "links.db")
    assert con.execute("select count(*) from t").fetchone()[0] == 100
    con.close()
    assert (snap / "settings.json").read_text() == '{"a": 1}'
    assert (snap / "backups" / "promote" / "n1.json").exists()
    assert not (snap / "links.db-wal").exists()
    assert not (snap / "logs").exists()


def test_sqlite_copy_includes_uncommitted_wal_content(layout):
    """WAL 모드에서 아직 체크포인트 안 된 행도 백업 API는 담는다 (파일 복사는 놓친다)."""
    data, root = layout
    (data / "links.db-wal").unlink()
    con = sqlite3.connect(data / "links.db")
    con.execute("pragma journal_mode=wal")
    con.execute("insert into t values (999)")
    con.commit()                      # 연결을 열어 둔 채 (체크포인트 전)
    try:
        snap = db.snapshot(data, root, D1)
        c2 = sqlite3.connect(snap / "links.db")
        assert c2.execute("select count(*) from t where x = 999").fetchone()[0] == 1
        c2.close()
    finally:
        con.close()


def test_unchanged_files_are_hardlinked_to_previous_snapshot(layout):
    data, root = layout
    s1 = db.snapshot(data, root, D1)
    (data / "settings.json").write_text('{"a": 2}')
    s2 = db.snapshot(data, root, D1 + datetime.timedelta(days=1))

    assert os.stat(s2 / "big_static.txt").st_ino == os.stat(s1 / "big_static.txt").st_ino
    assert os.stat(s2 / "settings.json").st_ino != os.stat(s1 / "settings.json").st_ino
    assert (s1 / "settings.json").read_text() == '{"a": 1}'   # 이전 스냅샷은 그대로
    assert (s2 / "settings.json").read_text() == '{"a": 2}'


def test_rerun_same_day_replaces_snapshot(layout):
    data, root = layout
    db.snapshot(data, root, D1)
    (data / "settings.json").write_text('{"a": 3}')
    snap = db.snapshot(data, root, D1)
    assert (snap / "settings.json").read_text() == '{"a": 3}'
    assert sorted(p.name for p in root.iterdir()) == ["2026-10-12"]


def test_prune_keeps_recent_and_ignores_foreign_dirs(layout):
    data, root = layout
    for i in range(20):
        db.snapshot(data, root, D1 + datetime.timedelta(days=i))
    (root / "manual-keep").mkdir()

    db.prune(root, keep=14)

    names = sorted(p.name for p in root.iterdir())
    assert "manual-keep" in names
    dated = [n for n in names if n != "manual-keep"]
    assert len(dated) == 14
    assert dated[0] == (D1 + datetime.timedelta(days=6)).isoformat()


def test_missing_data_dir_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        db.snapshot(tmp_path / "nope", tmp_path / "snapshots", D1)


def test_cli_args_pick_data_dir_root_and_keep(layout, monkeypatch):
    """가계부 등 다른 앱의 data/도 같은 코드로 백업한다 (2026-10-12)."""
    data, root = layout
    monkeypatch.setattr(db, "_notify_failure", lambda text: None)
    for i in range(3):
        monkeypatch.setattr(db, "_today", lambda i=i: D1 + datetime.timedelta(days=i))
        db.main(["--data", str(data), "--root", str(root), "--keep", "2"])
    assert sorted(p.name for p in root.iterdir()) == ["2026-10-13", "2026-10-14"]

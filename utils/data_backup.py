"""서버 data/ 일일 스냅샷.

- SQLite 파일은 sqlite3 백업 API로 복사한다 (사용 중이어도 일관된 사본, WAL 내용 포함).
- 그 밖의 파일은 전날 스냅샷과 크기·수정 시각이 같으면 하드링크, 아니면 복사한다.
- logs/, -wal/-shm/-journal, .DS_Store는 넣지 않는다.
- 날짜 이름(YYYY-MM-DD) 폴더만 보관 개수로 정리하고, 다른 폴더는 건드리지 않는다.
서버 디스크 안의 백업이라 디스크 고장에는 대비하지 못한다 (코드 버그·실수로 DB가 망가지는 경우 대비).

실행 (systemd 타이머): .venv/bin/python -m utils.data_backup
"""
from __future__ import annotations

import datetime
import logging
import os
import re
import shutil
import sqlite3
from pathlib import Path

logger = logging.getLogger("data_backup")

PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_DIR / "data"
BACKUP_ROOT = Path.home() / "backups" / "anki-manager"
KEEP = 14

_DATED = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SKIP_DIRS = {"logs", "__pycache__"}
_SKIP_SUFFIXES = ("-wal", "-shm", "-journal")
_SKIP_NAMES = {".DS_Store"}
_SQLITE_HEADER = b"SQLite format 3\x00"


def _is_sqlite(path):
    try:
        with open(path, "rb") as f:
            return f.read(16) == _SQLITE_HEADER
    except OSError:
        return False


def _previous_snapshot(root, day):
    if not root.exists():
        return None
    earlier = sorted(p for p in root.iterdir() if p.is_dir() and _DATED.match(p.name) and p.name < day.isoformat())
    return earlier[-1] if earlier else None


def _copy_sqlite(src, dst):
    s = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
    d = sqlite3.connect(dst)
    try:
        s.backup(d)
    finally:
        d.close()
        s.close()


def snapshot(data_dir, root, day):
    data_dir, root = Path(data_dir), Path(root)
    if not data_dir.is_dir():
        raise FileNotFoundError(data_dir)
    root.mkdir(parents=True, exist_ok=True)
    prev = _previous_snapshot(root, day)
    final = root / day.isoformat()
    tmp = root / f".tmp-{day.isoformat()}"
    if tmp.exists():
        shutil.rmtree(tmp)

    for dirpath, dirnames, filenames in os.walk(data_dir):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        rel_dir = Path(dirpath).relative_to(data_dir)
        (tmp / rel_dir).mkdir(parents=True, exist_ok=True)
        for name in filenames:
            if name in _SKIP_NAMES or name.endswith(_SKIP_SUFFIXES):
                continue
            src, rel = Path(dirpath) / name, rel_dir / name
            dst = tmp / rel
            if _is_sqlite(src):
                _copy_sqlite(src, dst)
                continue
            old = prev / rel if prev else None
            st = src.stat()
            if old and old.is_file():
                ost = old.stat()
                # 나노초 단위로 비교한다 (초 단위면 같은 크기로 1초 안에 바뀐 파일을 놓친다)
                if ost.st_size == st.st_size and ost.st_mtime_ns == st.st_mtime_ns:
                    os.link(old, dst)
                    continue
            shutil.copy2(src, dst)

    if final.exists():
        shutil.rmtree(final)
    tmp.rename(final)
    return final


def prune(root, keep=KEEP):
    root = Path(root)
    dated = sorted(p for p in root.iterdir() if p.is_dir() and _DATED.match(p.name))
    for old in dated[:-keep] if len(dated) > keep else []:
        shutil.rmtree(old)
        logger.info("오래된 스냅샷 삭제: %s", old.name)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    from integrations import anki_sync
    try:
        snap = snapshot(DATA_DIR, BACKUP_ROOT, datetime.date.today())
        prune(BACKUP_ROOT, KEEP)
        logger.info("스냅샷 완료: %s", snap)
    except Exception as e:
        logger.exception("data/ 백업 실패")
        try:
            anki_sync.telegram_notifier()(f"⚠️ Anki Manager data/ 백업 실패: {type(e).__name__}: {str(e)[:200]}")
        except Exception as ne:
            logger.warning("백업 실패 알림 전송 실패: %s", ne)
        raise


if __name__ == "__main__":
    main()

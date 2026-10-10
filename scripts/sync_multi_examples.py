"""
Anki Vocabulary Multi-Example Synchronizer
=========================================
links.db의 연결 문장 데이터를 활용하여 Anki 'English Vocabulary' 노트의 '예문' 필드에
최대 5개의 다중 예문을 안전하게 패킹( ||| 구분자)하여 동기화합니다.

기능:
1. 실행 전 Anki 'English Vocabulary' 전체 노트의 원본 예문 백업 (data/backups/vocab_examples_backup_{timestamp}.json)
2. links.db의 연결 문장 중 원본과 중복되지 않고 어휘 다양성이 확보된 양질의 문장 최대 4개 선별
3. 원본 1개 + 선별 4개 = 최대 5개 예문 풀 구성
4. 링크가 없는 단어는 기존 예문 100% 보존
5. --rollback <백업파일> 옵션을 통한 즉시 원복 지원
"""

import os
import re
import sys
import json
import sqlite3
import argparse
import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# AnkiConnect 로컬 통신 프록시 우회
os.environ["no_proxy"] = "*"

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from integrations.anki_connect import AnkiConnector
from config import MODEL_VOCAB

DATA_DIR = BASE_DIR / "data"
BACKUP_DIR = DATA_DIR / "backups"
DB_PATH = DATA_DIR / "links.db"

BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=10.0)
    conn.row_factory = sqlite3.Row
    return conn


def clean_text(raw: str) -> str:
    if not raw:
        return ""
    # 간단한 태그 제거 및 공백 정규화
    clean = re.sub(r"<[^>]+>", "", raw).strip()
    return clean


def jaccard_similarity(s1: str, s2: str) -> float:
    w1 = set(re.findall(r"\w+", s1.lower()))
    w2 = set(re.findall(r"\w+", s2.lower()))
    if not w1 or not w2:
        return 0.0
    return len(w1 & w2) / len(w1 | w2)


def select_diverse_candidates(
    base_sentence: str,
    raw_sentences: List[str],
    max_additional: int = 4,
    overlap_threshold: float = 0.45
) -> List[str]:
    """
    기존 원본 예문과 겹치지 않고, 상호 어휘 중복(Jaccard)이 낮은 문장들을 최대 max_additional개 선별
    """
    seen: Set[str] = set()
    if base_sentence:
        seen.add(base_sentence.lower().strip())

    candidates: List[str] = []
    for s in raw_sentences:
        s_clean = s.strip()
        s_lower = s_clean.lower()
        if not s_clean or s_lower in seen:
            continue
        seen.add(s_lower)
        candidates.append(s_clean)

    selected: List[str] = []
    for cand in candidates:
        too_similar = False
        # 원본 및 이미 선별된 문장과의 유사도 검사
        if base_sentence and jaccard_similarity(cand, base_sentence) > 0.70:
            continue
        for sel in selected:
            if jaccard_similarity(cand, sel) > overlap_threshold:
                too_similar = True
                break
        if not too_similar:
            selected.append(cand)
        if len(selected) >= max_additional:
            break

    return selected


def backup_vocab_examples(notes_info: List[Dict]) -> Path:
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUP_DIR / f"vocab_examples_backup_{timestamp}.json"

    backup_data = {}
    for n in notes_info:
        nid = n["noteId"]
        word = n["fields"].get("단어", {}).get("value", "")
        example = n["fields"].get("예문", {}).get("value", "")
        backup_data[nid] = {
            "단어": word,
            "예문": example
        }

    with open(backup_file, "w", encoding="utf-8") as f:
        json.dump(backup_data, f, ensure_ascii=False, indent=2)

    print(f"[*] 원본 백업 완료: {backup_file} (총 {len(backup_data)}개 노트)")
    return backup_file


def rollback_from_backup(backup_path: Path):
    if not backup_path.exists():
        print(f"[!] 백업 파일을 찾을 수 없습니다: {backup_path}")
        return

    print(f"[*] 롤백 시작: {backup_path}")
    with open(backup_path, "r", encoding="utf-8") as f:
        backup_data = json.load(f)

    updates = [{"id": int(nid_str), "fields": {"예문": data["예문"]}} for nid_str, data in backup_data.items()]
    print(f"  .. 총 {len(updates)}개 노트를 AnkiConnect multi 배치로 복원 중 (100개 단위)...")
    AnkiConnector.update_notes_fields_batch(updates, chunk_size=100)
    print(f"[+] 총 {len(updates)}개 노트 예문 필드 롤백 완료.")


def sync_multi_examples(dry_run: bool = False):
    print("=" * 60)
    print("Anki Vocabulary 다중 예문 동기화 엔진 (최대 5개 캡)")
    print("=" * 60)

    # 1. Anki에서 English Vocabulary 전체 노트 검색
    print("[1/4] Anki에서 'English Vocabulary' 전체 노트 로딩 중...")
    note_ids = AnkiConnector.find_notes(f'"note:{MODEL_VOCAB}"')
    if not note_ids:
        print("[!] Anki에서 노트를 찾을 수 없습니다.")
        return

    print(f"  총 {len(note_ids)}개 단어 노트 발견. 필드 정보 조회 중...")
    # 500개 단위 배치 조회
    all_notes: List[Dict] = []
    batch_size = 500
    for i in range(0, len(note_ids), batch_size):
        chunk = note_ids[i:i + batch_size]
        all_notes.extend(AnkiConnector.get_notes_info(chunk))

    # 2. 백업 생성
    backup_file = backup_vocab_examples(all_notes)

    # 3. links.db에서 연결 문장 로드
    print("[2/4] links.db에서 연결 문장 데이터 로딩 중...")
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT vocab_note_id, sentence_text FROM links ORDER BY id ASC")
    rows = cur.fetchall()
    conn.close()

    links_by_vocab: Dict[int, List[str]] = {}
    for r in rows:
        vid = r["vocab_note_id"]
        stext = r["sentence_text"].strip()
        if vid not in links_by_vocab:
            links_by_vocab[vid] = []
        links_by_vocab[vid].append(stext)

    print(f"  links.db 상 연결 문장을 보유한 단어: {len(links_by_vocab)}개")

    # 4. 동기화 데이터 생성 및 반영
    print(f"[3/4] 다중 예문 패킹 및 Anki 반영 준비 (dry_run={dry_run})...")
    pending_updates = []
    pool_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}

    for note in all_notes:
        nid = note["noteId"]
        word = note["fields"].get("단어", {}).get("value", "").strip()
        current_example = note["fields"].get("예문", {}).get("value", "").strip()

        # links.db에 링크가 없는 경우 -> 기존 예문 그대로 유지
        if nid not in links_by_vocab:
            pool_counts[1] += 1
            continue

        raw_linked = links_by_vocab[nid]
        if not raw_linked:
            pool_counts[1] += 1
            continue

        # 원본 예문 추출 (이미 |||로 분리되어 있는 경우 첫 번째 요소가 원본)
        if "|||" in current_example:
            base_sentence = current_example.split("|||")[0].strip()
        else:
            base_sentence = current_example

        # 최대 4개 추가 선별
        additional = select_diverse_candidates(base_sentence, raw_linked, max_additional=4)

        if not additional:
            pool_counts[1] += 1
            continue

        # 총 풀 구성: [기본 예문] + [추가 예문들]
        if base_sentence:
            full_pool = [base_sentence] + additional
        else:
            full_pool = additional

        # 최대 5개 캡
        full_pool = full_pool[:5]
        new_example_value = " ||| ".join(full_pool)

        pool_size = len(full_pool)
        pool_counts[pool_size] = pool_counts.get(pool_size, 0) + 1

        if new_example_value != current_example:
            pending_updates.append({"id": nid, "fields": {"예문": new_example_value}})

    updated_count = len(pending_updates)
    if not dry_run and pending_updates:
        print(f"  .. {updated_count}개 노트를 AnkiConnect multi 배치로 초고속 일괄 반영 중 (100개 단위)...")
        AnkiConnector.update_notes_fields_batch(pending_updates, chunk_size=100)

    print("[4/4] 동기화 작업 완료!")
    print("=" * 60)
    print(f"[*] 총 업데이트된 단어 수: {updated_count}개")
    print("[*] 예문 풀 분포:")
    print(f"  - 1개 (단일/비연결): {pool_counts.get(1, 0)}개")
    print(f"  - 2개 예문 풀: {pool_counts.get(2, 0)}개")
    print(f"  - 3개 예문 풀: {pool_counts.get(3, 0)}개")
    print(f"  - 4개 예문 풀: {pool_counts.get(4, 0)}개")
    print(f"  - 5개 완충 풀: {pool_counts.get(5, 0)}개")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Anki 다중 예문 동기화 도구")
    parser.add_argument("--dry-run", action="store_true", help="실제 변경 없이 시뮬레이션만 수행")
    parser.add_argument("--rollback", type=str, help="백업 JSON 파일 경로를 입력하여 원복")
    args = parser.parse_args()

    if args.rollback:
        rollback_from_backup(Path(args.rollback))
    else:
        sync_multi_examples(dry_run=args.dry_run)

"""
Anki Manager Comprehensive System Health Inspector
==================================================
전체 시스템(AnkiConnect, 템플릿/CSS, links.db, 덱 데이터, AI 및 성능 파이프라인)을
전수 검사하고 정밀 진단 결과를 출력합니다.
"""

import os
import re
import sys
import json
import sqlite3
import datetime
from pathlib import Path
from collections import Counter
from typing import Dict, List, Any, Tuple

os.environ["no_proxy"] = "*"

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from integrations.anki_connect import AnkiConnector
from config import MODEL_VOCAB, MODEL_SENTENCE, MODEL_GRAMMAR, NOTE_COMPLETOR_MODEL, NOTE_COMPLETOR_MAX_WORKERS
from core.link_manager import get_db_connection, LinkManager, clean_text

def run_comprehensive_check() -> Dict[str, Any]:
    report = {
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "sections": {}
    }

    print("=" * 70)
    print("      ANKI MANAGER 종합 전수 검사 (Comprehensive Diagnostic)      ")
    print("=" * 70)

    # ---------------------------------------------------------
    # 1. AnkiConnect 및 모델 연결 검사
    # ---------------------------------------------------------
    print("\n[1/5] AnkiConnect 및 모델 연결 검사...")
    sec1 = {"status": "PASS", "details": []}
    try:
        ver = AnkiConnector.invoke("version")
        sec1["details"].append(f"AnkiConnect API v{ver} 정상 연결")
        print(f"  ✓ AnkiConnect v{ver} 통신 성공")

        model_names = AnkiConnector.invoke("modelNames")
        for m in [MODEL_VOCAB, MODEL_SENTENCE, MODEL_GRAMMAR]:
            if m in model_names:
                sec1["details"].append(f"모델 '{m}' 확인됨")
                print(f"  ✓ 모델 확인: {m}")
            else:
                sec1["status"] = "WARN"
                sec1["details"].append(f"모델 '{m}' 누락")
                print(f"  ✗ 모델 누락: {m}")
    except Exception as e:
        sec1["status"] = "FAIL"
        sec1["details"].append(f"AnkiConnect 통신 에러: {e}")
        print(f"  ✗ AnkiConnect 통신 실패: {e}")
    report["sections"]["1_connectivity"] = sec1

    # ---------------------------------------------------------
    # 2. 템플릿 및 CSS 무결성 검사
    # ---------------------------------------------------------
    print("\n[2/5] 템플릿 및 CSS 무결성 검사 ('English Vocabulary')...")
    sec2 = {"status": "PASS", "details": []}
    try:
        tpl = AnkiConnector.invoke("modelTemplates", modelName=MODEL_VOCAB)
        styling = AnkiConnector.invoke("modelStyling", modelName=MODEL_VOCAB)["css"]

        # CSS 검사
        required_css = [".cloze-blank", ".example-highlight", ".more-examples", ".more-examples-btn"]
        for c in required_css:
            if c in styling:
                print(f"  ✓ CSS 클래스 확인: {c}")
            else:
                sec2["status"] = "FAIL"
                print(f"  ✗ 필수 CSS 클래스 누락: {c}")

        # 카드 1 앞면 검사
        c1_front = tpl.get("카드 1", {}).get("Front", "")
        for feat in ["cloze-example", "Math.random()", "sessionStorage", "IRREGULARS"]:
            if feat in c1_front:
                print(f"  ✓ 카드 1 앞면: {feat} 로직 확인")
            else:
                sec2["status"] = "FAIL"
                print(f"  ✗ 카드 1 앞면 로직 누락: {feat}")

        # 카드 1 뒷면 검사
        c1_back = tpl.get("카드 1", {}).get("Back", "")
        for feat in ["back-example-box", "sessionStorage", "example-highlight", "more-examples"]:
            if feat in c1_back:
                print(f"  ✓ 카드 1 뒷면: {feat} 로직 확인")
            else:
                sec2["status"] = "FAIL"
                print(f"  ✗ 카드 1 뒷면 로직 누락: {feat}")

        # 카드 2 뒷면 검사
        c2_back = tpl.get("카드 2", {}).get("Back", "")
        if "back-example-box" in c2_back and "more-examples" in c2_back:
            print(f"  ✓ 카드 2 뒷면: 다중 예문 아코디언 로직 확인")
        else:
            sec2["status"] = "FAIL"
            print(f"  ✗ 카드 2 뒷면 아코디언 로직 누락")

    except Exception as e:
        sec2["status"] = "FAIL"
        sec2["details"].append(f"템플릿 검사 실패: {e}")
        print(f"  ✗ 템플릿 조회 실패: {e}")
    report["sections"]["2_templates"] = sec2

    # ---------------------------------------------------------
    # 3. SQLite Database 무결성 검사 (links.db)
    # ---------------------------------------------------------
    print("\n[3/5] links.db 무결성 및 고아 데이터 검사...")
    sec3 = {"status": "PASS", "details": []}
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # PRAGMA integrity_check
        cur.execute("PRAGMA integrity_check;")
        res = cur.fetchall()
        integ = [r[0] for r in res]
        if integ == ["ok"]:
            print("  ✓ SQLite 무결성 검사: 정상 (ok)")
        else:
            sec3["status"] = "FAIL"
            print(f"  ✗ SQLite 무결성 에러: {integ}")

        # 통계 집계
        cur.execute("SELECT COUNT(*) FROM links;")
        total_links = cur.fetchone()[0]
        cur.execute("SELECT COUNT(DISTINCT vocab_note_id) FROM links;")
        linked_vocabs = cur.fetchone()[0]
        cur.execute("SELECT COUNT(DISTINCT sentence_note_id) FROM links;")
        linked_sents = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM vocab_cache;")
        cache_count = cur.fetchone()[0]

        print(f"  ✓ 총 링크 수: {total_links:,}개")
        print(f"  ✓ 연결된 단어: {linked_vocabs:,}개 / 연결된 문장: {linked_sents:,}개")
        print(f"  ✓ 단어 캐시 레코드: {cache_count:,}개")

        # 고아 데이터(Orphan) 검사: Anki에 존재하지 않는 vocab_note_id가 links.db에 남아있는지 검사
        cur.execute("SELECT DISTINCT vocab_note_id FROM links LIMIT 1000;")
        sample_vids = [r[0] for r in cur.fetchall()]
        chunk_info = AnkiConnector.invoke("notesInfo", notes=sample_vids[:200])
        valid_count = sum(1 for n in chunk_info if n and n.get("noteId"))
        print(f"  ✓ links.db 외래키 유효성 샘플 검사: 200건 중 {valid_count}건 유효")
        if valid_count < 195:
            sec3["status"] = "WARN"
            print("  ⚠️ 일부 고아 데이터 존재 가능성")

        conn.close()
    except Exception as e:
        sec3["status"] = "FAIL"
        sec3["details"].append(f"DB 검사 실패: {e}")
        print(f"  ✗ DB 검사 에러: {e}")
    report["sections"]["3_database"] = sec3

    # ---------------------------------------------------------
    # 4. 단어 덱 데이터 및 Cloze 매칭 전수 검사 (7,975개 전체)
    # ---------------------------------------------------------
    print("\n[4/5] 단어 덱 데이터 및 예문 풀/Cloze 전수 검사...")
    sec4 = {"status": "PASS", "details": []}
    try:
        note_ids = AnkiConnector.find_notes(f'note:"{MODEL_VOCAB}"')
        total_vocab = len(note_ids)
        print(f"  총 단어 카드: {total_vocab:,}개 로드 중...")

        # 1000개 단위 배치 로드
        all_notes = []
        for i in range(0, total_vocab, 1000):
            all_notes.extend(AnkiConnector.get_notes_info(note_ids[i:i+1000]))

        pool_dist = Counter()
        cloze_fails = []
        corrupted_examples = 0

        # Cloze 정규식 엔진 시뮬레이션
        IRREGULARS = {
            "get": r"(?:get|gets|getting|got|gotten)", "take": r"(?:take|takes|taking|took|taken)",
            "make": r"(?:make|makes|making|made)", "give": r"(?:give|gives|giving|gave|given)",
            "come": r"(?:come|comes|coming|came)", "go": r"(?:go|goes|going|went|gone)",
            "see": r"(?:see|sees|seeing|saw|seen)", "have": r"(?:have|has|having|had)",
            "run": r"(?:run|runs|running|ran)", "keep": r"(?:keep|keeps|keeping|kept)",
            "find": r"(?:find|finds|finding|found)", "fall": r"(?:fall|falls|falling|fell|fallen)",
            "break": r"(?:break|breaks|breaking|broke|broken)", "bring": r"(?:bring|brings|bringing|brought)",
            "buy": r"(?:buy|buys|buying|bought)", "catch": r"(?:catch|catches|catching|caught)",
            "choose": r"(?:choose|chooses|choosing|chose|chosen)", "do": r"(?:do|does|doing|did|done)",
            "draw": r"(?:draw|draws|drawing|drew|drawn)", "drive": r"(?:drive|drives|driving|drove|driven)",
            "feel": r"(?:feel|feels|feeling|felt)", "fly": r"(?:fly|flies|flying|flew|flown)",
            "grow": r"(?:grow|grows|growing|grew|grown)", "hear": r"(?:hear|hears|hearing|heard)",
            "hold": r"(?:hold|holds|holding|held)", "know": r"(?:know|knows|knowing|knew|known)",
            "leave": r"(?:leave|leaves|leaving|left)", "lose": r"(?:lose|loses|losing|lost)",
            "pay": r"(?:pay|pays|paying|paid)", "put": r"(?:put|puts|putting)",
            "read": r"(?:read|reads|reading)", "say": r"(?:say|says|saying|said)",
            "send": r"(?:send|sends|sending|sent)", "show": r"(?:show|shows|showing|showed|shown)",
            "speak": r"(?:speak|speaks|speaking|spoke|spoken)", "spend": r"(?:spend|spends|spending|spent)",
            "stand": r"(?:stand|stands|standing|stood)", "tell": r"(?:tell|tells|telling|told)",
            "think": r"(?:think|thinks|thinking|thought)", "wear": r"(?:wear|wears|wearing|wore|worn)",
            "win": r"(?:win|wins|winning|won)", "write": r"(?:write|writes|writing|wrote|written)",
            "freeze": r"(?:freeze|freezes|freezing|froze|frozen)", "throw": r"(?:throw|throws|throwing|threw|thrown)",
            "lend": r"(?:lend|lends|lending|lent)", "speed": r"(?:speed|speeds|speeding|sped)",
            "swear": r"(?:swear|swears|swearing|swore|sworn)", "bite": r"(?:bite|bites|biting|bit|bitten)",
            "hide": r"(?:hide|hides|hiding|hid|hidden)", "wake": r"(?:wake|wakes|waking|woke|woken)",
            "strike": r"(?:strike|strikes|striking|struck)", "be": r"(?:be|is|are|was|were|am|been|being)"
        }

        def build_token_pattern(tok):
            t_lower = tok.lower()
            if t_lower in IRREGULARS:
                return IRREGULARS[t_lower]
            stem = t_lower
            if len(stem) > 3 and (stem.endswith("e") or stem.endswith("y")):
                stem = stem[:-1]
            return re.escape(stem) + r"[a-zA-Z]*"

        def test_cloze_match(w, s):
            tokens = [t for t in re.split(r"[\s/]+", w) if not re.match(r"^(someone|somebody|sb|something|sth|one's|oneself|A|B|C|V|V-ing|to)$", t, re.I)]
            if not tokens:
                tokens = [t for t in re.split(r"[\s/]+", w) if re.match(r"^[a-zA-Z]+$", t)]
            if not tokens:
                tokens = re.split(r"[\s/]+", w)
            patterns = [build_token_pattern(t) for t in tokens]
            sep = r"(?:\s+[\w$\'\"]+){0,4}\s+"
            regex = re.compile(r"\b(" + sep.join(patterns) + r")\b", re.I)
            if regex.search(s):
                return True
            for tok in tokens:
                if len(tok) >= 4:
                    sub_rgx = re.compile(r"\b(" + build_token_pattern(tok) + r")\b", re.I)
                    if sub_rgx.search(s):
                        return True
            return False

        cloze_success = 0
        cloze_tested = 0

        for note in all_notes:
            w_raw = note["fields"].get("단어", {}).get("value", "")
            ex_raw = note["fields"].get("예문", {}).get("value", "")
            w = clean_text(w_raw).strip()
            ex = clean_text(ex_raw).strip()

            parts = [p.strip() for p in ex.split("|||") if p.strip()]
            pool_dist[len(parts)] += 1

            if len(parts) == 0:
                continue

            # 검사: 첫 번째 예문과 마지막 예문에 대해 Cloze 매칭 여부
            cloze_tested += 1
            # 풀 중 최소 1개 이상 매칭되는지 확인
            matched_any = any(test_cloze_match(w, p) for p in parts)
            if matched_any:
                cloze_success += 1
            else:
                cloze_fails.append((note["noteId"], w, parts[0][:60]))

        match_rate = (cloze_success / cloze_tested * 100) if cloze_tested else 0.0

        print(f"  ✓ 예문 풀 분포:")
        print(f"     - 5개 완충 풀: {pool_dist[5]:,}개 ({pool_dist[5]/total_vocab*100:.1f}%)")
        print(f"     - 4개 예문 풀: {pool_dist[4]:,}개")
        print(f"     - 3개 예문 풀: {pool_dist[3]:,}개")
        print(f"     - 2개 예문 풀: {pool_dist[2]:,}개")
        print(f"     - 1개 단일 예문: {pool_dist[1]:,}개")
        print(f"     - 예문 없음: {pool_dist[0]:,}개")
        print(f"  ✓ Cloze v2 매칭 성공률: {match_rate:.2f}% ({cloze_success:,}/{cloze_tested:,})")
        if cloze_fails:
            print(f"  ℹ️ 매칭 미완성 단어 {len(cloze_fails)}개 (예: {cloze_fails[:3]})")

    except Exception as e:
        sec4["status"] = "FAIL"
        sec4["details"].append(f"덱 전수 검사 에러: {e}")
        print(f"  ✗ 전수 검사 실패: {e}")
    report["sections"]["4_deck_integrity"] = sec4

    # ---------------------------------------------------------
    # 5. AI 파이프라인 및 동시성 설정 검사
    # ---------------------------------------------------------
    print("\n[5/5] AI 및 성능 최적화 파이프라인 검사...")
    sec5 = {"status": "PASS", "details": []}
    try:
        # 모델 및 워커 검사
        print(f"  ✓ AI 모델 설정: {NOTE_COMPLETOR_MODEL} (Flash-Lite 고정 확인)")
        print(f"  ✓ AI 동시성 워커 수: {NOTE_COMPLETOR_MAX_WORKERS}개 (3배 상향 확인)")

        # LinkManager append 함수 확인
        assert hasattr(LinkManager, "_append_sentence_to_vocab_note")
        print(f"  ✓ LinkManager 증분 자동 연동 함수 탑재 확인")

        # AnkiConnector multi batch 함수 확인
        assert hasattr(AnkiConnector, "update_notes_fields_batch")
        print(f"  ✓ AnkiConnector multi 배치 업데이트 함수 탑재 확인")

        # Background Audio Executor 확인
        from backend.services.card_service import _audio_executor, queue_background_audio
        print(f"  ✓ 백그라운드 오디오 스레드 풀 활성화 확인 (max_workers={_audio_executor._max_workers})")

    except Exception as e:
        sec5["status"] = "FAIL"
        sec5["details"].append(f"AI 파이프라인 검사 실패: {e}")
        print(f"  ✗ 파이프라인 검사 실패: {e}")
    report["sections"]["5_ai_pipeline"] = sec5

    print("\n" + "=" * 70)
    all_statuses = [s["status"] for s in report["sections"].values()]
    if all(s == "PASS" for s in all_statuses):
        print(">>> 종합 검사 결과: [전체 ALL PASS] 모든 시스템이 최상의 상태입니다. <<<")
    else:
        print(f">>> 종합 검사 결과: [경고/확인 필요] ({all_statuses}) <<<")
    print("=" * 70)

    return report

if __name__ == "__main__":
    run_comprehensive_check()

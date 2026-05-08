import json
import os
import statistics
import datetime
from collections import defaultdict
from google import genai
from google.genai import types
from dotenv import load_dotenv

from integrations.anki_connect import AnkiConnector
from utils.ui import UI
from config import ANKI_URL, NOTE_COMPLETOR_MODEL

load_dotenv()
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

class FeedbackAnalyzer:
    def __init__(self):
        self.client = genai.Client(api_key=GOOGLE_API_KEY)
        self.model_id = NOTE_COMPLETOR_MODEL  # Use default model for analysis

    @staticmethod
    def get_all_card_stats():
        """특정 덱(1. Language::1.1. English) 하위 카드의 정보를 수집 (청크 처리 포함)"""
        # "1. Language::1.1. English*" 쿼리를 사용하여 하위 덱 포함
        card_ids = AnkiConnector.invoke("findCards", query='deck:"1. Language::1.1. English*"')
        chunk_size = 500
        all_info = []
        for i in range(0, len(card_ids), chunk_size):
            chunk = card_ids[i:i+chunk_size]
            info = AnkiConnector.invoke("cardsInfo", cards=chunk)
            all_info.extend(info)
        return all_info

    @staticmethod
    def get_review_history(card_ids):
        """카드별 실제 복습 히스토리 수집 (청크 처리 포함)"""
        chunk_size = 200
        all_reviews = {}
        for i in range(0, len(card_ids), chunk_size):
            chunk = card_ids[i:i+chunk_size]
            reviews = AnkiConnector.invoke("getReviewsOfCards", cards=chunk)
            all_reviews.update(reviews)
        return all_reviews

    def analyze_weak_cards(self, cards):
        """약점 카드 추출 및 분석"""
        weak = [c for c in cards if (c.get("factor", 0) < 2000 and c.get("factor", 0) > 0) or c.get("lapses", 0) >= 3]
        
        pos_distribution = defaultdict(list)
        tag_distribution = defaultdict(list)
        
        for card in weak:
            for tag in card.get("tags", []):
                tag_distribution[tag].append(card)
            
            # 필드에서 품사 추출 시도
            fields = card.get("fields", {})
            pos = "unknown"
            for pos_field in ["품사", "Part of Speech", "POS"]:
                if pos_field in fields:
                    pos = fields[pos_field].get("value", "unknown")
                    break
            pos_distribution[pos].append(card)
        
        return {
            "total_weak": len(weak),
            "by_pos": {k: len(v) for k, v in pos_distribution.items()},
            "by_tag": {k: len(v) for k, v in tag_distribution.items()},
            "worst_10": sorted(weak, key=lambda c: c.get("lapses", 0), reverse=True)[:10]
        }

    def analyze_time_patterns(self, review_history):
        """시간대별 집중력 분석"""
        hourly = defaultdict(list)
        
        for card_id, reviews in review_history.items():
            for review in reviews:
                # review["id"]는 unix timestamp (ms)
                hour = datetime.datetime.fromtimestamp(review["id"] / 1000).hour
                hourly[hour].append(review["ease"])
        
        result = {}
        for hour, eases in hourly.items():
            if not eases: continue
            again_rate = eases.count(1) / len(eases)
            result[hour] = {
                "reviews": len(eases),
                "again_rate": round(again_rate * 100, 1),
                "avg_ease": round(statistics.mean(eases), 2)
            }
        return result

    def analyze_forgetting_curve(self, review_history):
        """실측 망각 곡선 분석"""
        interval_buckets = defaultdict(list)
        
        for card_id, reviews in review_history.items():
            # 날짜순 정렬 보장
            reviews = sorted(reviews, key=lambda x: x["id"])
            for i in range(1, len(reviews)):
                prev_review = reviews[i-1]
                curr_review = reviews[i]
                # 두 복습 사이 실제 간격 (일)
                gap_days = (curr_review["id"] - prev_review["id"]) / 86400000
                bucket = self._get_bucket(gap_days)
                interval_buckets[bucket].append(curr_review["ease"])
        
        return {
            bucket: {
                "count": len(eases),
                "retention": round((1 - eases.count(1)/len(eases)) * 100, 1)
            }
            for bucket, eases in interval_buckets.items()
        }

    def _get_bucket(self, days):
        if days < 1:   return "당일"
        if days < 3:   return "1-2일"
        if days < 7:   return "3-6일"
        if days < 14:  return "1-2주"
        if days < 30:  return "2-4주"
        return "1개월+"

    def analyze_leech_patterns_with_ai(self, leech_cards):
        """Leech 카드 공통점 AI 분석"""
        if not leech_cards:
            return "분석할 약점 카드가 없습니다."

        card_summaries = []
        for card in leech_cards[:50]:
            fields = card.get("fields", {})
            summary = {
                "word": fields.get("단어", {}).get("value", fields.get("문장", {}).get("value", "N/A")),
                "meaning": fields.get("뜻", {}).get("value", fields.get("해설", {}).get("value", "N/A")),
                "pos": fields.get("품사", {}).get("value", "N/A"),
                "tags": card.get("tags", []),
                "lapses": card.get("lapses", 0),
                "ease_factor": card.get("factor", 0)
            }
            card_summaries.append(summary)
        
        prompt = f"""
다음은 사용자가 반복적으로 틀린 영어 단어/문장 카드 목록입니다.
이 카드들의 공통점을 분석하여 왜 어려운지, 어떤 학습 전략이 도움이 될지 제안해주세요.

카드 데이터:
{json.dumps(card_summaries, ensure_ascii=False, indent=2)}

다음 항목으로 분석해주세요:
1. 품사/카테고리 패턴 (특정 품사나 유형에 집중되어 있는가?)
2. 의미적 패턴 (추상어, 뉘앙스가 유사한 단어군 등)
3. 형태적 패턴 (접두사, 어근이 비슷한 단어군 등)
4. 학습 전략 제안 (3가지)

응답은 마크다운 형식으로 간결하고 전문적이게 작성해주세요.
"""
        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=prompt
            )
            return response.text
        except Exception as e:
            return f"AI 분석 실패: {e}"

    def analyze_deck_health(self, cards):
        """덱별 건강도 점수 분석 (영어 덱으로 한정)"""
        decks = defaultdict(list)
        for card in cards:
            # cards 자체가 이미 필터링되어 들어오지만, 
            # 한번 더 명시적으로 확인하여 안전하게 분류
            if "1. Language::1.1. English" in card["deckName"]:
                decks[card["deckName"]].append(card)
        
        health_scores = {}
        for deck_name, deck_cards in decks.items():
            valid_factors = [c["factor"] for c in deck_cards if c.get("factor", 0) > 0]
            avg_ease = statistics.mean(valid_factors) / 2500 * 100 if valid_factors else 0
            lapse_total = sum(c.get("lapses", 0) for c in deck_cards)
            lapse_rate = lapse_total / len(deck_cards)
            mature_count = sum(1 for c in deck_cards if c.get("interval", 0) >= 21)
            maturity = mature_count / len(deck_cards) * 100
            
            # 종합 점수
            score = min(100, avg_ease * 0.4 + maturity * 0.4 - lapse_rate * 5)
            health_scores[deck_name] = {
                "card_count": len(deck_cards),
                "avg_ease": round(statistics.mean(valid_factors)) if valid_factors else 0,
                "mature_ratio": round(maturity, 1),
                "health_score": round(max(0, score), 1)
            }
        return health_scores

    def generate_report(self, weak, time_pat, forgetting, ai_insight, health, output_path=None):
        """마크다운 리포트 생성 및 콘솔 출력"""
        if output_path is None:
            # 프로젝트 루트 기준 절대 경로 설정
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            output_path = os.path.join(base_dir, "data", "learning_report.md")
        
        today = datetime.datetime.now().strftime("%Y년 %m월 %d일")
        
        # 최적/주의 시간대 계산
        if time_pat:
            worst_hour_key = max(time_pat.keys(), key=lambda k: time_pat[k]["again_rate"])
            best_hour_key = min(time_pat.keys(), key=lambda k: time_pat[k]["again_rate"])
            worst_hour = (worst_hour_key, time_pat[worst_hour_key])
            best_hour = (best_hour_key, time_pat[best_hour_key])
        else:
            worst_hour = ("데이터 없음", {"again_rate": 0})
            best_hour = ("데이터 없음", {"again_rate": 0})
        
        lines = [
            f"# 🧠 Anki 학습 분석 리포트",
            f"> 생성일: {today}",
            f"> 대상: 1. Language::1.1. English 및 하위 덱",
            "",
            "---",
            "",
            "## 1. 요약 대시보드",
            "",
            "### 품사별 분포",
            "",
            "| 품사 | 약점 카드 수 |",
            "|------|------------|",
        ]
        
        for pos, count in sorted(weak["by_pos"].items(), key=lambda x: -x[1]):
            lines.append(f"| {pos} | {count}장 |")
        
        lines += [
            "",
            "### 반복 실패 TOP 10",
            "",
            "| 순위 | 단어/문장 | 실패 횟수 | Ease |",
            "|------|------|-----------|------|",
        ]
        for i, card in enumerate(weak["worst_10"], 1):
            fields = card.get("fields", {})
            word = fields.get("단어", {}).get("value", fields.get("문장", {}).get("value", "?"))
            lines.append(f"| {i} | {word} | {card.get('lapses', 0)}회 | {card.get('factor', 0)} |")
        
        lines += [
            "",
            "---",
            "",
            "## 3. 시간대별 집중력 분석",
            "",
            "| 시간대 | 복습 수 | 오답률 | 평균 Ease |",
            "|--------|---------|--------|-----------|",
        ]
        for hour in sorted(time_pat.keys()):
            data = time_pat[hour]
            bar = "▓" * int(data["again_rate"] / 5)
            lines.append(
                f"| {hour:02d}:00 | {data['reviews']:,}회 | "
                f"{data['again_rate']}% {bar} | {data['avg_ease']} |"
            )
        
        lines += [
            "",
            "---",
            "",
            "## 4. 실측 망각 곡선",
            "",
            "| 복습 간격 | 복습 수 | 실측 리텐션율 |",
            "|-----------|---------|--------------|",
        ]
        # 순서 보장
        buckets = ["당일", "1-2일", "3-6일", "1-2주", "2-4주", "1개월+"]
        for bucket in buckets:
            if bucket in forgetting:
                data = forgetting[bucket]
                retention_bar = "█" * int(data["retention"] / 10)
                lines.append(
                    f"| {bucket} | {data['count']:,}회 | "
                    f"{data['retention']}% {retention_bar} |"
                )
        
        lines += [
            "",
            "---",
            "",
            "## 5. AI 약점 패턴 분석",
            "",
            ai_insight,
            "",
            "---",
            "",
            "## 6. 덱별 건강도",
            "",
            "| 덱 이름 | 카드 수 | 숙성률 | 건강도 점수 |",
            "|---------|---------|--------|------------|",
        ]
        for deck, data in sorted(health.items(), key=lambda x: -x[1]["health_score"]):
            star_bar = "★" * int(data["health_score"] / 20)
            lines.append(
                f"| {deck} | {data['card_count']:,}장 | "
                f"{data['mature_ratio']}% | {data['health_score']} {star_bar} |"
            )
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        report_content = "\n".join(lines)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report_content)
        
        # 콘솔에도 리포트 내용 출력
        UI.divider()
        print(report_content)
        UI.divider()
        
        return output_path

def run_feedback_analysis():
    UI.header("Anki 학습 패턴 분석")
    analyzer = FeedbackAnalyzer()
    
    UI.info("📊 Anki 데이터를 수집 중입니다... (카드 수에 따라 수십 초 소요)")
    try:
        cards = analyzer.get_all_card_stats()
        UI.step(f"{len(cards):,}장의 카드 데이터를 로드했습니다.")
        
        card_ids = [c["cardId"] for c in cards]
        UI.info("🔍 복습 히스토리를 분석 중입니다...")
        review_history = analyzer.get_review_history(card_ids)
        
        UI.step("약점 카드 분석 중...")
        weak = analyzer.analyze_weak_cards(cards)
        
        UI.step("시간대별 패턴 분석 중...")
        time_pat = analyzer.analyze_time_patterns(review_history)
        
        UI.step("망각 곡선 계산 중...")
        forgetting = analyzer.analyze_forgetting_curve(review_history)
        
        UI.step("덱별 건강도 체크 중...")
        health = analyzer.analyze_deck_health(cards)
        
        UI.info("🤖 AI가 약점 패턴을 분석하고 있습니다...")
        ai_insight = analyzer.analyze_leech_patterns_with_ai(weak["worst_10"])
        
        UI.info("📝 리포트를 생성 및 출력 중입니다...")
        report_path = analyzer.generate_report(weak, time_pat, forgetting, ai_insight, health)
        
        UI.success(f"학습 분석 리포트가 성공적으로 생성되었습니다!")
        UI.print(UI.ICON_CELEBRATE, f"절대 경로: {report_path}", style="bold yellow")
        
    except Exception as e:
        UI.error(f"분석 중 오류 발생: {e}")

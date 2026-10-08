import json
import os
from typing import List, Dict, Any, Optional
from utils.ui import UI
from utils.cli_selector import InteractiveSelector

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOPICS_FILE = os.path.join(BASE_DIR, "data", "knowledge_topics.json")

class TopicManager:
    """
    Knowledge 카드의 대주제, 소주제 목록 및 덱 매핑을 관리하는 클래스.
    """

    @classmethod
    def load_topics(cls) -> List[Dict[str, Any]]:
        if not os.path.exists(TOPICS_FILE):
            return []
        try:
            with open(TOPICS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ 토픽 파일 로드 실패: {e}")
            return []

    @classmethod
    def save_topics(cls, topics: List[Dict[str, Any]]) -> bool:
        try:
            os.makedirs(os.path.dirname(TOPICS_FILE), exist_ok=True)
            with open(TOPICS_FILE, "w", encoding="utf-8") as f:
                json.dump(topics, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"❌ 토픽 파일 저장 실패: {e}")
            return False

    @classmethod
    def get_categories_prompt_guide(cls) -> str:
        """
        Gemini 프롬프트에 주입할 사용자 정의 카테고리 가이드라인 문자열을 생성합니다.
        """
        topics = cls.load_topics()
        if not topics:
            return ""

        guide_lines = ["\n[사용자 정의 공식 카테고리 분류 체계 (이 중 가장 적절한 것을 선택하십시오)]"]
        for t in topics:
            major = t.get("major", "")
            minors = ", ".join(t.get("minors", []))
            guide_lines.append(f"- {major}: [{minors}]")
        guide_lines.append("※ 텍스트 내용이 위 분류에 없다면 새로운 대주제/소주제를 적절히 명명하여 분류하십시오.\n")
        return "\n".join(guide_lines)

    @classmethod
    def get_target_deck_for_major(cls, major_name: str, default_deck: str = "Knowledge") -> str:
        """
        대주제명에 매핑된 목표 덱 이름을 반환합니다.
        """
        topics = cls.load_topics()
        for t in topics:
            if t.get("major", "").strip() == major_name.strip():
                return t.get("target_deck", default_deck)
        return default_deck

    @classmethod
    def menu_manage_topics(cls):
        """
        CLI 인터랙티브 카테고리 관리 메뉴
        """
        while True:
            UI.clear()
            UI.subheader("🏛️ Knowledge 카테고리 & 덱 매핑 관리")

            topics = cls.load_topics()

            # 현재 카테고리 목록 표시
            columns = ["대주제", "소주제 목록", "저장 덱"]
            rows = []
            for t in topics:
                rows.append([
                    t.get("major", ""),
                    ", ".join(t.get("minors", [])),
                    t.get("target_deck", "Knowledge")
                ])
            UI.table("등록된 지식 카테고리", columns, rows)

            options = [
                ("1", "1. 새 대주제 추가"),
                ("2", "2. 소주제 추가/수정"),
                ("3", "3. 대주제별 저장 덱 변경 (서브덱 분기 설정)"),
                ("4", "4. 대주제 삭제"),
                ("b", "b. 돌아가기")
            ]

            choice_text = InteractiveSelector.select_one(
                [opt[1] for opt in options],
                title="작업을 선택하세요"
            )

            if not choice_text or "돌아가기" in choice_text:
                break

            choice = next(opt[0] for opt in options if opt[1] == choice_text)

            if choice == "1":
                new_major = UI.ask("추가할 대주제 이름을 입력하세요 (예: 심리학, 종교, 인공지능)").strip()
                if new_major:
                    minors_raw = UI.ask("포함할 소주제들을 쉼표(,)로 구분하여 입력하세요 (예: 인지심리, 발달심리)").strip()
                    minors = [m.strip() for m in minors_raw.split(",") if m.strip()]
                    deck = UI.ask("저장할 Anki 덱 이름을 입력하세요", default="Knowledge").strip()
                    
                    topics.append({
                        "major": new_major,
                        "minors": minors,
                        "target_deck": deck or "Knowledge"
                    })
                    cls.save_topics(topics)
                    UI.success(f"대주제 '{new_major}' 추가 완료!")
                    UI.ask("계속하려면 Enter를 누르세요", default="")

            elif choice == "2":
                majors = [t["major"] for t in topics]
                selected_major = InteractiveSelector.select_one(majors, title="소주제를 편집할 대주제를 선택하세요")
                if selected_major:
                    target_topic = next((t for t in topics if t["major"] == selected_major), None)
                    if target_topic:
                        UI.info(f"현재 '{selected_major}'의 소주제: {', '.join(target_topic.get('minors', []))}")
                        new_minors_raw = UI.ask("새로운 소주제 목록을 쉼표(,)로 입력하세요 (덮어쓰기)").strip()
                        if new_minors_raw:
                            target_topic["minors"] = [m.strip() for m in new_minors_raw.split(",") if m.strip()]
                            cls.save_topics(topics)
                            UI.success(f"소주제 목록 업데이트 완료!")
                            UI.ask("계속하려면 Enter를 누르세요", default="")

            elif choice == "3":
                majors = [t["major"] for t in topics]
                selected_major = InteractiveSelector.select_one(majors, title="저장 덱을 변경할 대주제를 선택하세요")
                if selected_major:
                    target_topic = next((t for t in topics if t["major"] == selected_major), None)
                    if target_topic:
                        current_deck = target_topic.get("target_deck", "Knowledge")
                        new_deck = UI.ask(f"'{selected_major}' 카드가 저장될 덱 이름", default=current_deck).strip()
                        if new_deck:
                            target_topic["target_deck"] = new_deck
                            cls.save_topics(topics)
                            UI.success(f"'{selected_major}' ➔ 덱 '{new_deck}' 설정 완료!")
                            UI.ask("계속하려면 Enter를 누르세요", default="")

            elif choice == "4":
                majors = [t["major"] for t in topics]
                selected_major = InteractiveSelector.select_one(majors, title="삭제할 대주제를 선택하세요")
                if selected_major:
                    topics = [t for t in topics if t["major"] != selected_major]
                    cls.save_topics(topics)
                    UI.success(f"대주제 '{selected_major}' 삭제 완료!")
                    UI.ask("계속하려면 Enter를 누르세요", default="")

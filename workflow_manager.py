# Anki/Anki Manager/workflow_manager.py
import argparse
import sys
from tqdm import tqdm

from youtube_extractor import extract_content
from sentence_selector import run_sentence_selection
from vocabulary_selector import run_vocabulary_selection 
from note_completor import run_note_completion
from audio_adder import AnkiTTSFiller
from organizor import run_organizer
from Inspector import inspect_items
from config import WORKFLOW_STEPS

def main(url):
    print("🚀 Anki 자동화 워크플로우 시작...")
    
    # 함수를 이름으로 매핑
    func_map = {
        "extract_content": extract_content,
        "run_sentence_selection": run_sentence_selection,
        "run_vocabulary_selection": run_vocabulary_selection,
        "run_note_completion": run_note_completion,
        "AnkiTTSFiller.run_audio_addition": AnkiTTSFiller.run_audio_addition,
        "run_organizer": run_organizer,
    }

    # config에서 가져온 WORKFLOW_STEPS에 함수 매핑
    # 이 부분은 현재의 구조에서는 직접적으로 사용되지 않지만,
    # 향후 func 이름을 config에서 직접 받아 사용할 경우를 대비해 개념적으로 보여줍니다.
    # 지금은 기존 로직을 유지하면서 points만 config에서 가져오도록 수정합니다.

    total_points = sum(step["points"] for step in WORKFLOW_STEPS.values())

    results = {}
    with tqdm(total=total_points, desc="전체 진행률", bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]") as pbar:
        
        # 1. 콘텐츠 추출
        pbar.set_description("콘텐츠 추출 중...")
        extracted_data = extract_content(url, pbar=pbar, step_points=WORKFLOW_STEPS["콘텐츠 추출"]["points"])
        if not extracted_data:
            pbar.write("❌ 콘텐츠 추출 실패. 워크플로우를 종료합니다.")
            return
        results['extracted_data'] = extracted_data

        # 2. 문장 선별
        pbar.set_description("문장 선별 중...")
        selected_sentences = run_sentence_selection(extracted_data, pbar=pbar, step_points=WORKFLOW_STEPS["문장 선별"]["points"])
        if selected_sentences is None:
            pbar.write("❌ 문장 선별 실패. 워크플로우를 종료합니다.")
            return
        results['selected_sentences'] = selected_sentences

        # 3. 어휘 선별
        pbar.set_description("어휘 선별 중...")
        selected_vocab = run_vocabulary_selection(extracted_data, pbar=pbar, step_points=WORKFLOW_STEPS["어휘 선별"]["points"])
        if selected_vocab is None:
            pbar.write("❌ 어휘 선별 실패. 워크플로우를 종료합니다.")
            return
        results['selected_vocab'] = selected_vocab

        def custom_inspector(enriched_data):
            pbar.clear()
            print("\n\n=== 🔎 데이터 최종 검수 (Inspector) ===")
            
            # 문장 검수
            if enriched_data and 'sentences' in enriched_data:
                print("\n[문장 검수]")
                def format_sentence(item):
                    return f"문장: {item.get('문장', '')} \n    해석: {item.get('해설', '')}"
                enriched_data['sentences'] = inspect_items(enriched_data['sentences'], display_func=format_sentence)
                
            # 어휘 검수
            if enriched_data and 'vocab' in enriched_data:
                print("\n[어휘 검수]")
                def format_vocab(item):
                    return f"단어: {item.get('단어', '')} \n    뜻: {item.get('뜻', '')} \n    설명: {item.get('설명', '')}"
                enriched_data['vocab'] = inspect_items(enriched_data['vocab'], display_func=format_vocab)

            print("=== 검수 완료 ===\n")
            pbar.refresh()
            return enriched_data

        # 4. 노트 추가
        pbar.set_description("노트 추가 (뜻 생성 및 검수 포함) 중...")
        if not run_note_completion(selected_sentences, selected_vocab, pbar=pbar, step_points=WORKFLOW_STEPS["노트 추가"]["points"], inspector_func=custom_inspector):
            pbar.write("❌ 노트 추가 실패. 워크플로우를 종료합니다.")
            return

        # 5. 음성 추가
        pbar.set_description("음성 추가 중...")
        if not AnkiTTSFiller.run_audio_addition(pbar=pbar, step_points=WORKFLOW_STEPS["음성 추가"]["points"]):
            pbar.write("❌ 음성 파일 추가 실패. 워크플로우를 종료합니다.")
            return

        # 6. 카드 정리
        pbar.set_description("카드 정리 중...")
        if not run_organizer(pbar=pbar, step_points=WORKFLOW_STEPS["카드 정리"]["points"]):
            pbar.write("❌ 카드 정리 실패. 워크플로우를 종료합니다.")
            return

    print("\n🎉 Anki 자동화 워크플로우가 성공적으로 완료되었습니다!")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        url_input = sys.argv[1]
    else:
        url_input = input("처리할 YouTube URL을 입력하세요: ").strip()

    if not url_input:
        print("URL이 입력되지 않았습니다. 프로그램을 종료합니다.")
    else:
        main(url_input)

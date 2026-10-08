import sys
import os
import re

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from integrations.anki_connect import AnkiConnector
from core.completer import run_note_completion
from config import MODEL_VOCAB

def main():
    print("🔢 총 65개 어휘 (대표 숫자/분수/소수 + 전공 고급 수학 수식) 카드 추가 스크립트 시작...")
    
    # 1. 대상 어휘 목록 정의 (대표 표현 31개 + 전공 고급 수학 표현 34개)
    vocab_raw_list = [
        # --- 분수 (Fractions) ---
        {"단어": "one half (1/2)", "뜻": "2분의 1"},
        {"단어": "one third (1/3)", "뜻": "3분의 1"},
        {"단어": "two thirds (2/3)", "뜻": "3분의 2"},
        {"단어": "a quarter (1/4)", "뜻": "4분의 1"},
        {"단어": "three quarters (3/4)", "뜻": "4분의 3"},
        {"단어": "five and a half (5 1/2)", "뜻": "5와 2분의 1"},
        {"단어": "one hundredth (1/100)", "뜻": "100분의 1"},
        
        # --- 소수 (Decimals) ---
        {"단어": "zero point five (0.5)", "뜻": "0.5"},
        {"단어": "three point one four (3.14)", "뜻": "3.14 (파이값)"},
        {"단어": "zero point zero five (0.05)", "뜻": "0.05"},
        {"단어": "two point three four five (2.345)", "뜻": "2.345"},
        
        # --- 큰 숫자 및 단위 (Large Numbers) ---
        {"단어": "one thousand two hundred thirty-four (1,234)", "뜻": "1,234"},
        {"단어": "ten thousand (10,000)", "뜻": "만 (10,000)"},
        {"단어": "one hundred thousand (100,000)", "뜻": "십만 (100,000)"},
        {"단어": "one million (1,000,000)", "뜻": "백만 (1,000,000)"},
        {"단어": "ten million (10,000,000)", "뜻": "천만 (10,000,000)"},
        {"단어": "one billion (1,000,000,000)", "뜻": "십억 (1,000,000,000)"},
        {"단어": "one trillion (1,000,000,000,000)", "뜻": "일조 (1,000,000,000,000)"},
        
        # --- 연도 및 기호/반복 표현 (Years & Sequence Reading) ---
        {"단어": "nineteen ninety-eight (1998)", "뜻": "1998년"},
        {"단어": "two thousand eight (2008)", "뜻": "2008년"},
        {"단어": "twenty twenty-four (2024)", "뜻": "2024년"},
        {"단어": "double seven (77)", "뜻": "반복되는 두 자리 숫자 (77)"},
        {"단어": "triple eight (888)", "뜻": "반복되는 세 자리 숫자 (888)"},
        {"단어": "forty-two (42)", "뜻": "사십이 (42)"},
        
        # --- 특수 수 표현 및 스포츠 점수 (Special Units & Sports Scores) ---
        {"단어": "a dozen (12)", "뜻": "다스 (12개)"},
        {"단어": "a baker's dozen (13)", "뜻": "베이커스 더즌 (덤을 포함한 13개)"},
        {"단어": "one grand ($1,000)", "뜻": "1,000달러"},
        {"단어": "love (0 in tennis)", "뜻": "러브 (테니스의 0점)"},
        {"단어": "nil (0 in soccer)", "뜻": "닐 (축구 등의 0점)"},
        {"단어": "two-all (2-2)", "뜻": "투 올 (스포츠 2대 2 동점)"},
        {"단어": "deuce (40-40 in tennis)", "뜻": "듀스 (테니스의 40대 40 동점)"},
        
        # --- KAIST 전공 수학 및 기호 독법 (Advanced Math & Notations) ---
        {"단어": "one to two (1:2)", "뜻": "1 대 2 (비율 읽기)"},
        {"단어": "two squared (2²)", "뜻": "2의 제곱"},
        {"단어": "two cubed (2³)", "뜻": "2의 세제곱"},
        {"단어": "two to the power of n (2^n)", "뜻": "2의 n승"},
        {"단어": "the derivative of y with respect to x (dy/dx)", "뜻": "y를 x에 대해 미분한 것"},
        {"단어": "the partial of z with respect to x (∂z/∂x)", "뜻": "z를 x에 대해 편미분한 것"},
        {"단어": "the integral of f(x) from a to b", "뜻": "a부터 b까지 f(x)의 정적분"},
        {"단어": "the limit of f(x) as x approaches infinity", "뜻": "x가 무한대로 갈 때 f(x)의 극한"},
        {"단어": "the sum from i equals one to n of a_i", "뜻": "i가 1부터 n까지 a_i의 합"},
        {"단어": "log base two of x (log₂x)", "뜻": "밑이 2인 로그 x"},
        {"단어": "natural log of x (ln x)", "뜻": "x의 자연로그"},
        {"단어": "the absolute value of x (|x|)", "뜻": "x의 절대값"},
        {"단어": "x prime (x')", "뜻": "x 프라임"},
        {"단어": "x bar (x̄)", "뜻": "x 바 (통계학 표본 평균)"},
        {"단어": "x hat (x̂)", "뜻": "x 햇 (추정치 / 단위 벡터)"},
        {"단어": "dot product", "뜻": "벡터의 내적 (dot 곱)"},
        {"단어": "cross product", "뜻": "벡터의 외적 (cross 곱)"},
        {"단어": "transpose of matrix A (A^T)", "뜻": "행렬 A의 전치행렬"},
        {"단어": "gradient of f (∇f)", "뜻": "f의 그래디언트 (기울기 벡터)"},
        {"단어": "converges to zero", "뜻": "0으로 수렴하다"},
        {"단어": "diverges to infinity", "뜻": "무한대로 발산하다"},
        {"단어": "eigenvalue and eigenvector", "뜻": "고유값과 고유벡터"},
        {"단어": "ordinary differential equation (ODE)", "뜻": "상미분방정식"},
        
        # --- 과학/공학 수치 및 근사치 처리 (Scientific & CS Readings) ---
        {"단어": "three times ten to the eighth (3 × 10⁸)", "뜻": "과학적 표기법 (3 곱하기 10의 8승)"},
        {"단어": "orders of magnitude", "뜻": "자릿수 차이 (크기 정도)"},
        {"단어": "round to two decimal places", "뜻": "소수 둘째 자리 반올림"},
        {"단어": "to three significant figures", "뜻": "유효숫자 3자리"},
        {"단어": "ten choose three", "뜻": "조합 (10개 중 3개 선택)"},
        {"단어": "five mod two", "뜻": "나머지 연산 (5를 2로 나눈 나머지)"},
        {"단어": "base sixteen", "뜻": "16진법"},
        {"단어": "one to ten inclusive", "뜻": "1부터 10까지 포함하여"},
        {"단어": "fifty basis points (50 bps)", "뜻": "0.5% (금리/통계 50 베이시스 포인트)"},
        {"단어": "indeterminate form", "뜻": "극한 부정형 (0/0 등)"},
        {"단어": "to the nearest tenth", "뜻": "소수 첫째 자리 반올림"}
    ]
    
    # 2. 로컬 Anki 중복 카드 필터링
    print("🔍 내 안키 단어장 로드 및 중복 필터링 중...")
    try:
        existing_vocab = AnkiConnector.get_existing_vocab_words(MODEL_VOCAB)
        existing_set = {w.lower().strip() for w in existing_vocab}
        print(f"   - 기존 안키 내 단어 수: {len(existing_vocab)}개")
    except Exception as e:
        print(f"❌ Anki 연결 실패. 안키가 켜져 있는지 확인하세요: {e}")
        return

    new_words = []
    for item in vocab_raw_list:
        word = item["단어"].strip()
        # 괄호 제거 후 기존 단어와 매칭 검사
        clean_word = re.sub(r'\s*\(.*?\)', '', word).strip()
        if not clean_word:
            clean_word = word
            
        if clean_word.lower() not in existing_set:
            new_words.append({
                "단어": word,
                "뜻": item["뜻"]
            })
            
    print(f"   - 중복 필터링 완료: 신규 미등록 단어 {len(new_words)}개 / 전체 {len(vocab_raw_list)}개")
    
    if not new_words:
        print("⚠️ 안키에 추가할 새로운 단어가 없습니다. 이미 모두 등록되어 있습니다.")
        return

    # 3. AI 보강 및 안키 저장 진행
    print("🧠 Gemini AI 연동을 통해 뜻, 품사, 예문, 뉘앙스 해설 자동 완성 및 저장 중...")
    sentences_data = {"sentences": []}
    vocab_data = {"vocab": new_words}
    
    success, added_s, added_v = run_note_completion(sentences_data, vocab_data)
    
    if success:
        print(f"🎉 성공적으로 {len(added_v)}개의 카드가 보강되어 안키에 저장되었습니다!")
        
        # 4. 후속 자동화 작업 실행
        print("🎵 후속 자동화 작업 시작...")
        try:
            from integrations.audio import AnkiTTSFiller
            from utils.organizer import run_organizer
            from utils.cluster import run_clustering
            
            print("   - 오디오 (TTS) 파일 생성 및 주입 중...")
            AnkiTTSFiller.run_audio_addition()
            
            print("   - 카드 자동 정리 (덱 이동)...")
            run_organizer()
            
            print("   - AI 유의어 맵 업데이트...")
            run_clustering()
            
            print("✨ 모든 후속 자동화 작업이 성공적으로 완료되었습니다!")
        except Exception as e:
            print(f"⚠️ 후속 작업 중 일부 실패: {e}")
    else:
        print("❌ AI 보강 및 저장 단계 실패")

if __name__ == "__main__":
    main()

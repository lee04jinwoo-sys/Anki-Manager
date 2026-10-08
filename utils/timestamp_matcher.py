import re

def normalize_text(text):
    if not text:
        return ""
    # 소문자 변환, 알파벳/숫자/공백만 남김
    cleaned = re.sub(r'[^a-z0-9\s]', ' ', text.lower())
    # 공백 정규화
    return " ".join(cleaned.split())

def find_best_timestamp(target_text, segments):
    if not segments:
        return 0.0
        
    norm_target = normalize_text(target_text)
    if not norm_target:
        return 0.0
        
    # 1. 누적 문자열 생성 및 세그먼트 매핑 테이블 구축
    norm_segments = []
    full_transcript = ""
    char_map = [] # 각 문자가 어떤 세그먼트 인덱스에 속하는지 기록
    
    for idx, seg in enumerate(segments):
        norm_seg = normalize_text(seg.get("text", ""))
        norm_segments.append(norm_seg)
        
        if norm_seg:
            start_pos = len(full_transcript)
            if full_transcript:
                full_transcript += " "
                char_map.append(idx) # 공백 문자 매핑
            
            full_transcript += norm_seg
            # 각 문자에 대해 세그먼트 인덱스 기록
            char_map.extend([idx] * len(norm_seg))

    # 1-1. 전체 자막 누적 문자열에서 정확한 Substring 찾기
    match_index = full_transcript.find(norm_target)
    if match_index != -1:
        # 매칭 시작 문자 위치의 세그먼트 조회
        seg_idx = char_map[match_index]
        return float(segments[seg_idx].get("start", 0.0))

    # 2. fallback 1: 문장의 앞 3단어(혹은 단어가 적으면 전체 단어)로 다시 검색
    target_words = norm_target.split()
    if not target_words:
        return 0.0
        
    prefix_length = min(3, len(target_words))
    prefix_target = " ".join(target_words[:prefix_length])
    match_index = full_transcript.find(prefix_target)
    if match_index != -1:
        seg_idx = char_map[match_index]
        return float(segments[seg_idx].get("start", 0.0))

    # 3. fallback 2: 슬라이딩 윈도우 단어 오버랩 매칭
    # 문장의 단어 집합과 가장 중복이 많이 일어나는 세그먼트 윈도우 탐색
    target_word_set = set(target_words)
    best_overlap = 0
    best_seg_idx = 0
    
    # 세그먼트별로 단어 집합 미리 계산
    seg_word_sets = [set(seg_txt.split()) for seg_txt in norm_segments]
    
    # 윈도우 크기는 일반적으로 문장의 단어 수 대비 1.5배~2배 범위의 세그먼트들
    window_size = max(1, min(5, len(segments)))
    
    for i in range(len(segments) - window_size + 1):
        # 윈도우 내 세그먼트들의 단어를 모두 합침
        combined_words = set()
        for j in range(window_size):
            combined_words.update(seg_word_sets[i + j])
            
        overlap = len(target_word_set & combined_words)
        if overlap > best_overlap:
            best_overlap = overlap
            best_seg_idx = i
            
    if best_overlap > 0:
        return float(segments[best_seg_idx].get("start", 0.0))
        
    # 매칭 실패 시 첫 번째 세그먼트의 시작 시점 리턴
    return float(segments[0].get("start", 0.0))

import os
from config import OBSIDIAN_VAULT_PATH, OBSIDIAN_INBOX_FILE

class ObsidianManager:
    def __init__(self):
        self.file_path = os.path.join(OBSIDIAN_VAULT_PATH, OBSIDIAN_INBOX_FILE)
        self.raw_content = ""

    def fetch_inbox_content(self):
        try:
            if not os.path.exists(self.file_path):
                # 파일이 없으면 생성해둠
                with open(self.file_path, 'w', encoding='utf-8') as f:
                    f.write("## Sentences\n\n## Vocab\n")
                return None

            with open(self.file_path, 'r', encoding='utf-8') as f:
                self.raw_content = f.read()
        except PermissionError:
            print(f"\n❌ [권한 에러] Obsidian 파일에 접근할 수 없습니다.")
            print(f"📍 경로: {self.file_path}")
            print(f"💡 해결: [시스템 설정 > 개인정보 보호 및 보안 > 전체 디스크 접근 권한]에서 터미널(Terminal) 앱을 허용해 주세요.\n")
            return {"vocab": [], "sentences": []}
        except Exception as e:
            print(f"❌ Obsidian 로드 중 오류 발생: {e}")
            return {"vocab": [], "sentences": []}

        vocab_list = []
        sentence_list = []
        mode = None

        for line in self.raw_content.split('\n'):
            line = line.strip()
            if not line: continue
            
            # 섹션 체크
            lower_line = line.lower()
            if '## sentence' in lower_line:
                mode = 'sentence'
                continue
            elif '## vocab' in lower_line or '## word' in lower_line:
                mode = 'vocab'
                continue
            
            # 데이터 추출 (불렛 포인트 제거)
            clean_text = line.lstrip('- ').lstrip('* ').strip()
            if clean_text:
                if mode == 'sentence':
                    sentence_list.append(clean_text)
                elif mode == 'vocab':
                    vocab_list.append(clean_text)

        return {"vocab": vocab_list, "sentences": sentence_list}

    def remove_processed_items(self, processed_sentences, processed_vocab):
        """처리 완료된 항목만 파일에서 삭제"""
        if not os.path.exists(self.file_path):
            return

        import re
        def normalize(text):
            # 영문자/숫자만 남기고 소문자로 변환하여 비교 (AI에 의한 미세한 형식 변경 대응)
            return re.sub(r'[^a-zA-Z0-9]', '', text).lower()

        proc_s_norm = [normalize(s) for s in processed_sentences]
        proc_v_norm = [normalize(v) for v in processed_vocab]

        with open(self.file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        new_lines = []
        mode = None
        for line in lines:
            stripped = line.strip()
            if not stripped:
                new_lines.append(line)
                continue

            lower_line = stripped.lower()
            if '## sentence' in lower_line:
                mode = 'sentence'
                new_lines.append(line)
                continue
            elif '## vocab' in lower_line or '## word' in lower_line:
                mode = 'vocab'
                new_lines.append(line)
                continue

            clean_text = stripped.lstrip('- ').lstrip('* ').strip()
            if not clean_text:
                new_lines.append(line)
                continue

            norm_text = normalize(clean_text)
            if mode == 'sentence' and norm_text in proc_s_norm:
                continue
            elif mode == 'vocab' and norm_text in proc_v_norm:
                continue

            new_lines.append(line)

        with open(self.file_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)

    def clear_processed_content(self):
        """처리 완료 후 파일을 초기화하거나 내용을 비움"""
        with open(self.file_path, 'w', encoding='utf-8') as f:
            f.write("## Sentences\n\n## Vocab\n")

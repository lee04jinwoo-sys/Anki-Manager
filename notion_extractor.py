import os
import requests
import json
import re
from dotenv import load_dotenv

load_dotenv()

# ================= [Notion 설정] =================
NOTION_TOKEN = os.environ.get("NOTION_API_TOKEN")
NOTION_PAGE_ID = os.environ.get("NOTION_PAGE_ID")
# ===============================================

class NotionManager:
    def __init__(self):
        self.blocks_to_delete = []

    def fetch_page_content(self, page_id):
        print(f"📝 노션 데이터 가져오는 중: {page_id}")
        headers = {"Authorization": f"Bearer {NOTION_TOKEN}", "Notion-Version": "2022-06-28"}
        url = f"https://api.notion.com/v1/blocks/{page_id}/children"
        
        vocab_list = []
        sentence_list = []
        current_mode = None
        self.blocks_to_delete = []  # 실행 시 초기화

        has_more = True
        next_cursor = None

        try:
            while has_more:
                params = {"start_cursor": next_cursor} if next_cursor else {}
                response = requests.get(url, headers=headers, params=params).json()
                blocks = response.get('results', [])

                for b in blocks:
                    b_type = b.get('type')
                    content = b.get(b_type, {})
                    
                    if isinstance(content, dict) and 'rich_text' in content:
                        text_chunks = [t.get('plain_text', '') for t in content.get('rich_text', [])]
                        if text_chunks:
                            line = "".join(text_chunks).strip()
                            if not line:
                                continue
                            
                            lower_line = line.lower()
                            if 'english' in lower_line and 'word' in lower_line:
                                current_mode = 'vocab'
                                continue
                            elif 'english' in lower_line and 'sentence' in lower_line:
                                current_mode = 'sentence'
                                continue
                            
                            if current_mode == 'vocab':
                                vocab_list.append(line)
                                self.blocks_to_delete.append(b['id']) # 단어 블록 ID 저장
                            elif current_mode == 'sentence':
                                sentence_list.append(line)
                                self.blocks_to_delete.append(b['id']) # 문장 블록 ID 저장
                
                has_more = response.get('has_more', False)
                next_cursor = response.get('next_cursor')

            result_text = ""
            if vocab_list: result_text += "[단어 추출 대상]\n" + "\n".join(vocab_list) + "\n\n"
            if sentence_list: result_text += "[문장 추출 대상]\n" + "\n".join(sentence_list)

            return result_text.strip()
            
        except Exception as e:
            print(f"❌ 노션 오류: {e}")
            return None

    def delete_processed_blocks(self):
        if not self.blocks_to_delete:
            return
        print("🗑️ 노션에서 안키로 이동 완료된 텍스트 삭제 중...")
        headers = {"Authorization": f"Bearer {NOTION_TOKEN}", "Notion-Version": "2022-06-28"}
        deleted_count = 0
        for block_id in self.blocks_to_delete:
            try:
                res = requests.delete(f"https://api.notion.com/v1/blocks/{block_id}", headers=headers)
                if res.status_code == 200:
                    deleted_count += 1
            except Exception as e:
                print(f"❌ 블록 삭제 실패 ({block_id}): {e}")
        print(f"✔️ 노션 텍스트 {deleted_count}줄 삭제 완료.")

def main():
    print("=== Anki Notion Extractor ===")
    
    notion_manager = NotionManager()
    content = notion_manager.fetch_page_content(NOTION_PAGE_ID)
    
    if content:
        print("✅ 노션 데이터 추출 성공!")
        print(content)
        # 단독 실행 시에는 단순히 출력만 하고, 실제 Anki 연동은 gui_app이나 workflow_manager를 통해 이루어집니다.
    else:
        print("❌ 노션에서 데이터를 가져오지 못했습니다.")

if __name__ == "__main__":
    main()

import os
import json
from google import genai
from google.genai import types
from utils.ui import UI
from dotenv import load_dotenv

load_dotenv()
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

class DraftManager:
    @staticmethod
    def get_draft_path(file_path="data/inbox.md"):
        # 현재 파일(draft_manager.py) 위치 기준으로 프로젝트 루트의 data 폴더 경로 생성
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base_dir, file_path)

    @staticmethod
    def save_to_draft(sentences, file_path="data/inbox.md"):
        """Save sentences to a markdown file for manual selection."""
        abs_path = DraftManager.get_draft_path(file_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write("# YouTube Subtitle Draft\n")
            f.write("<!-- 请在此文件中仅保留你想学习的句子和单词，删除其余部分。 -->\n")
            f.write("<!-- 保存完成后，请在终端按 Enter 键。 -->\n\n")
            for s in sentences:
                f.write(f"{s}\n")
        return abs_path

    @staticmethod
    def read_draft(file_path="data/inbox.md"):
        """Read the edited draft file and return non-empty lines."""
        abs_path = DraftManager.get_draft_path(file_path)
        if not os.path.exists(abs_path):
            return []
        with open(abs_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        # Filter comments and headers
        content = [l.strip() for l in lines if l.strip() and not l.strip().startswith("#") and not l.strip().startswith("<!--")]
        return content

    @staticmethod
    def classify_selections(items, model_id, temperature):
        """Use AI to classify items into sentences and extract key vocabulary."""
        if not items:
            return {"sentences": [], "vocab": []}
        
        client = genai.Client(api_key=GOOGLE_API_KEY)
        prompt = f"""
        您是一位专业的英语教师。请从用户选择的英语句子列表中执行以下两项操作：
        
        1. 句子清洗：校正每个句子的首字母大写及标点符号，并放入 'sentences' 列表中。
        2. 核心词汇提取及释义：从每个句子中提取具有学习价值的核心单词或习语（包括短语动词、惯用语），并添加中文意思（'뜻'），放入 'vocab' 列表中。
        
        [数据列表]:
        {items}
        
        [输出格式]:
        {{
            "sentences": ["I'll get right on it", "It was a meticulous process"],
            "vocab": [{"단어": "get right on it", "뜻": "立即着手处理某事"}]
        }}
        """
        try:
            response = client.models.generate_content(
                model=model_id,
                contents=[prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=temperature
                )
            )
            return json.loads(response.text)
        except Exception as e:
            UI.error(f"分类过程中出错: {e}")
            # Fallback: simple length-based heuristic
            sentences = [i for i in items if len(i.split()) > 2]
            vocab = [i for i in items if len(i.split()) <= 2]
            return {"sentences": sentences, "vocab": vocab}

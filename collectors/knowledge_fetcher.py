import os
import re
import urllib.request
from typing import Optional, Dict, Any, List
from bs4 import BeautifulSoup
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter

class KnowledgeFetcher:
    """
    유튜브 URL, 웹페이지 URL, 로컬 파일 경로, 또는 원문 텍스트를 받아
    순수 텍스트와 메타데이터(출처, 제목 등)를 추출하는 수집기.
    """

    @staticmethod
    def extract_youtube_video_id(url: str) -> Optional[str]:
        match = re.search(r"(?:v=|\/|youtu\.be\/)([0-9A-Za-z_-]{11})", url)
        return match.group(1) if match else None

    @classmethod
    def fetch_youtube_transcript(cls, video_id: str) -> Optional[Dict[str, Any]]:
        """
        YouTube 동영상에서 한국어/영어 자막을 추출합니다.
        """
        try:
            transcript_list = YouTubeTranscriptApi().list(video_id)
            transcript = None
            
            # 1. 한국어 또는 영어 수동/자동 자막 탐색
            for lang in ['ko', 'en', 'ko-KR', 'en-US']:
                try:
                    transcript = transcript_list.find_transcript([lang])
                    if transcript:
                        break
                except Exception:
                    continue

            # 2. 그래도 없으면 사용 가능한 첫 번째 자막
            if not transcript:
                for t in transcript_list:
                    transcript = t
                    break

            if not transcript:
                return None

            fetched = transcript.fetch()
            
            def get_text(s):
                if isinstance(s, dict):
                    return s.get('text', '')
                return getattr(s, 'text', '')

            raw_texts = [get_text(s) for s in fetched]
            full_text = " ".join([t.replace('\n', ' ').strip() for t in raw_texts if t.strip()])

            if not full_text:
                return None

            return {
                "source_type": "youtube",
                "source": f"https://www.youtube.com/watch?v={video_id}",
                "content": full_text,
                "video_id": video_id
            }
        except Exception as e:
            print(f"⚠️ YouTube 자막 추출 실패 (video_id: {video_id}): {e}")
            return None

    @classmethod
    def fetch_web_article(cls, url: str) -> Optional[Dict[str, Any]]:
        """
        일반 웹페이지 URL(뉴스, 블로그, 위키 등)에서 본문 텍스트를 추출합니다.
        """
        try:
            req = urllib.request.Request(
                url,
                headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                html = response.read().decode('utf-8', errors='ignore')

            soup = BeautifulSoup(html, 'html.parser')

            # 제목 추출
            title = soup.title.string.strip() if soup.title and soup.title.string else url

            # 불필요한 태그 제거
            for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'noscript', 'svg', 'form']):
                tag.decompose()

            # 본문 후보 영역 탐색 (article, main, post-content 등)
            main_content = (
                soup.find('article') or 
                soup.find('main') or 
                soup.find(class_=re.compile(r'(content|post|article|body|entry)', re.I)) or 
                soup.body
            )

            if not main_content:
                return None

            # 텍스트 추출 및 정제
            text = main_content.get_text(separator='\n\n')
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            clean_text = '\n\n'.join(lines)

            if len(clean_text) < 100:
                return None

            return {
                "source_type": "web",
                "source": title,
                "url": url,
                "content": clean_text
            }
        except Exception as e:
            print(f"⚠️ 웹페이지 본문 추출 실패 ({url}): {e}")
            return None

    @classmethod
    def fetch_from_input(cls, input_str: str) -> Optional[Dict[str, Any]]:
        """
        입력된 문자열을 판별하여 (유튜브 URL / 웹 URL / 로컬 파일 / 직접 텍스트) 적절한 방식으로 본문을 추출합니다.
        """
        input_str = input_str.strip()
        if not input_str:
            return None

        # 1. YouTube URL 판별
        if "youtube.com" in input_str or "youtu.be" in input_str:
            video_id = cls.extract_youtube_video_id(input_str)
            if video_id:
                res = cls.fetch_youtube_transcript(video_id)
                if res:
                    return res

        # 2. 일반 웹페이지 URL 판별
        if input_str.startswith("http://") or input_str.startswith("https://"):
            res = cls.fetch_web_article(input_str)
            if res:
                return res

        # 3. 로컬 파일 경로 판별
        if os.path.exists(input_str) and os.path.isfile(input_str):
            try:
                with open(input_str, 'r', encoding='utf-8') as f:
                    content = f.read()
                return {
                    "source_type": "file",
                    "source": os.path.basename(input_str),
                    "content": content
                }
            except Exception as e:
                print(f"⚠️ 파일 읽기 실패: {e}")

        # 4. 직접 입력된 긴 텍스트
        return {
            "source_type": "direct_text",
            "source": "직접 입력 텍스트",
            "content": input_str
        }

    @staticmethod
    def chunk_by_paragraphs(text: str, target_chunk_size: int = 1500) -> List[str]:
        """
        문단(\\n\\n) 기준으로 텍스트를 분할하되, 작은 문단은 병합하여
        약 target_chunk_size(글자수 기준 약 1000~2000자) 단위의 의미 청크 리스트를 반환합니다.
        """
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        chunks = []
        current_chunk = []
        current_len = 0

        for p in paragraphs:
            p_len = len(p)
            if current_len + p_len > target_chunk_size and current_chunk:
                chunks.append('\n\n'.join(current_chunk))
                current_chunk = [p]
                current_len = p_len
            else:
                current_chunk.append(p)
                current_len += p_len

        if current_chunk:
            chunks.append('\n\n'.join(current_chunk))

        return chunks if chunks else [text]

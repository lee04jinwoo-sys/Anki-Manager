import requests
import re
import json
from bs4 import BeautifulSoup
from youtube_transcript_api import YouTubeTranscriptApi
from config import CANDIDATES_FILE, YOUTUBE_SCRAPER_USER_AGENT

def _print(pbar, *args, **kwargs):
    if pbar:
        pbar.write(" ".join(map(str, args)), **kwargs)
    else:
        print(*args, **kwargs)

def split_sentences(text):
    # 문장 단위 분리
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sentences if s.strip()]


class ContentFetcher:

    @staticmethod
    def fetch_youtube(v_id, pbar=None):
        _print(pbar, f"🎬 유튜브 자막 가져오는 중: {v_id}")

        try:
            ytt_api = YouTubeTranscriptApi()
            transcript_list = ytt_api.list(v_id)

            try:
                transcript = transcript_list.find_manually_created_transcript(['en'])
            except Exception:
                transcript = transcript_list.find_generated_transcript(['en'])

            fetched_transcript = transcript.fetch()

            text_parts = []

            for snippet in fetched_transcript.snippets:
                clean_text = snippet.text.replace('\n', ' ').strip()
                if clean_text:
                    text_parts.append(clean_text)

            full_text = " ".join(text_parts)

            sentences = split_sentences(full_text)

            return {"en_sentences": sentences}

        except Exception as e:
            _print(pbar, f"❌ 유튜브 자막 오류: {e}")
            return None

    @staticmethod
    def fetch_website(url, pbar=None):
        _print(pbar, f"🌐 웹사이트 추출 중: {url}")

        try:
            res = requests.get(url, headers={'User-Agent': YOUTUBE_SCRAPER_USER_AGENT})
            res.raise_for_status()

            soup = BeautifulSoup(res.text, 'html.parser')

            for s in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
                s.decompose()

            main_content = soup.find('main') or soup.find('article') or soup.find('body')

            if main_content:
                text = "\n".join(
                    p.get_text() for p in main_content.find_all('p', recursive=True)
                )
            else:
                text = soup.get_text(separator='\n', strip=True)

            text = re.sub(r'\n+', ' ', text).strip()

            sentences = split_sentences(text)

            return sentences

        except Exception as e:
            _print(pbar, f"❌ 웹사이트 오류: {e}")
            return None


def extract_content(url, pbar=None, step_points=0):
    """
    URL에서 콘텐츠를 추출합니다.

    :param url: YouTube 또는 웹사이트 URL
    :param pbar: tqdm progress bar instance
    :param step_points: 워크플로우에서 할당된 진행률 포인트
    :return: 추출된 콘텐츠 딕셔너리 또는 None
    """
    content = None
    source_type = "website"

    if 'youtube.com' in url or 'youtu.be' in url:
        v_id_match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})", url)
        if v_id_match:
            content = ContentFetcher.fetch_youtube(v_id_match.group(1), pbar=pbar)
            source_type = "youtube"
    elif url:
        content = ContentFetcher.fetch_website(url, pbar=pbar)

    if pbar and step_points > 0:
        pbar.update(step_points)

    if content:
        return {
            "source": url,
            "type": source_type,
            "sentences": content
        }
    return None


def main():

    print("=== Content Extractor ===")

    user_input = input("링크(YouTube/Website)를 입력하세요: ").strip()

    extracted_data = extract_content(user_input)

    if extracted_data:

        try:
            with open(CANDIDATES_FILE, 'w', encoding='utf-8') as f:
                json.dump(
                    extracted_data,
                    f,
                    ensure_ascii=False,
                    indent=2
                )

            print(f"💾 문장 단위로 '{CANDIDATES_FILE}'에 저장 완료")

        except IOError as e:
            print(f"❌ 파일 저장 실패: {e}")

    else:
        print("❌ 데이터를 가져오지 못했습니다.")


if __name__ == "__main__":
    main()

import re
import html
from youtube_transcript_api import YouTubeTranscriptApi
from config import YOUTUBE_SCRAPER_USER_AGENT

def split_sentences(text):
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sentences if s.strip()]

class YouTubeFetcher:
    @staticmethod
    def fetch_transcript(v_id, pbar=None):
        try:
            transcript_list = YouTubeTranscriptApi().list(v_id)
            try:
                transcript = transcript_list.find_manually_created_transcript(['en'])
            except:
                transcript = transcript_list.find_generated_transcript(['en'])
            
            fetched = transcript.fetch()
            
            def get_text(s):
                if isinstance(s, dict):
                    return s.get('text', '')
                return getattr(s, 'text', '')

            # HTML 엔티티 제거 및 줄바꿈 정리
            text = " ".join([html.unescape(get_text(s)).replace('\n', ' ').strip() for s in fetched])
            
            def get_start(s):
                if isinstance(s, dict):
                    return s.get('start', 0.0)
                return getattr(s, 'start', 0.0)

            def get_duration(s):
                if isinstance(s, dict):
                    return s.get('duration', 0.0)
                return getattr(s, 'duration', 0.0)

            clean_segments = []
            for s in fetched:
                clean_segments.append({
                    "text": html.unescape(get_text(s)).replace('\n', ' ').strip(),
                    "start": get_start(s),
                    "duration": get_duration(s)
                })
                
            return {
                "sentences": split_sentences(text),
                "segments": clean_segments
            }
        except Exception as e:
            if pbar: pbar.write(f"❌ 유튜브 자막 오류: {e}")
            return None

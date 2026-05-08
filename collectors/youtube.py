import re
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

            text = " ".join([get_text(s).replace('\n', ' ').strip() for s in fetched])
            return split_sentences(text)
        except Exception as e:
            if pbar: pbar.write(f"❌ 유튜브 자막 오류: {e}")
            return None

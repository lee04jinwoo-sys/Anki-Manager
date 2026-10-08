import json
import os
import csv
import random
import requests
import re
from integrations.anki_connect import AnkiConnector
from utils.cli_selector import InteractiveSelector
from utils.ui import UI
from core.completer import run_note_completion
from config import MODEL_VOCAB, MODEL_SENTENCE

# GitHub API Headers
HEADERS = {
    "User-Agent": "AnkiManagerCLI/1.0",
    "Accept": "application/vnd.github.v3+json"
}

# Friends MELD dataset cache
FRIENDS_CSV_URL = "https://raw.githubusercontent.com/declare-lab/MELD/master/data/MELD/train_sent_emo.csv"
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
FRIENDS_CACHE_FILE = os.path.join(CACHE_DIR, "friends_script.csv")

def ensure_friends_script():
    """Downloads and caches the Friends MELD transcript CSV if not already present"""
    if os.path.exists(FRIENDS_CACHE_FILE):
        return True
    os.makedirs(CACHE_DIR, exist_ok=True)
    UI.info("📡 Friends 대본 데이터셋 최초 다운로드 중 (약 1.8MB, 1회만 수행)...")
    try:
        response = requests.get(FRIENDS_CSV_URL, headers={"User-Agent": "AnkiManagerCLI/1.0"}, timeout=20)
        response.raise_for_status()
        with open(FRIENDS_CACHE_FILE, "wb") as f:
            f.write(response.content)
        UI.success("✅ Friends 대본 캐시 완료!")
        return True
    except Exception as e:
        UI.error(f"Friends 대본 다운로드 실패: {e}")
        return False

def load_friends_episodes():
    """Returns dict: season -> episode -> list of {speaker, text}"""
    if not ensure_friends_script():
        return None
    script_data = {}
    try:
        with open(FRIENDS_CACHE_FILE, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    season = int(row.get("Season", 0))
                    episode = int(row.get("Episode", 0))
                except ValueError:
                    continue
                utterance = row.get("Utterance", "").strip()
                speaker = row.get("Speaker", "").strip()
                if not utterance or season == 0 or episode == 0:
                    continue
                script_data.setdefault(season, {}).setdefault(episode, []).append(
                    {"speaker": speaker, "text": utterance}
                )
        return script_data
    except Exception as e:
        UI.error(f"Friends 대본 로드 오류: {e}")
        return None

MODERN_FAMILY_CACHE_FILE = os.path.join(CACHE_DIR, "modern_family_s1.json")

def ensure_modern_family_cache():
    """Scrapes and caches Modern Family Season 1 scripts if not already cached"""
    if os.path.exists(MODERN_FAMILY_CACHE_FILE):
        try:
            with open(MODERN_FAMILY_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            UI.error(f"Modern Family 캐시 파일 로드 오류, 재스크래핑을 시도합니다: {e}")

    os.makedirs(CACHE_DIR, exist_ok=True)
    script_data = {"1": {}}  # Season 1. Note: keys must be string to match json.load back compatibility
    
    UI.info("📡 Modern Family 시즌 1 대본 스크래핑 시작 (최초 1회만 수행)...")
    
    import html
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }
    
    # Season 1 has 24 episodes. We skip s01e01, so we scrape s01e02 to s01e24.
    for ep in range(2, 25):
        ep_str = f"s01e{ep:02d}"
        url = f"https://www.springfieldspringfield.co.uk/view_episode_scripts.php?tv-show=modern-family&episode={ep_str}"
        UI.info(f"  - 에피소드 {ep}/24 가져오는 중... ({ep_str})")
        
        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            html_content = response.text
            
            # Extract content of scrolling-script-container
            match = re.search(r'<div class="scrolling-script-container"\s*>(.*?)</div>', html_content, re.DOTALL)
            if not match:
                UI.error(f"  ⚠️ {ep_str} 대본 컨테이너를 찾을 수 없습니다. (URL: {url})")
                continue
                
            div_content = match.group(1)
            # Replace <br> tags with newlines
            div_content = re.sub(r'<br\s*/?>', '\n', div_content, flags=re.IGNORECASE)
            # Remove any other HTML tags
            div_content = re.sub(r'<[^<]+?>', '', div_content)
            # Unescape HTML entities
            div_content = html.unescape(div_content)
            
            sentences = []
            for line in div_content.split('\n'):
                line = line.strip()
                if not line:
                    continue
                # Split by sentence markers (. ! ?)
                raw_sents = re.split(r'(?<=[.!?])\s+', line)
                for s in raw_sents:
                    s = s.strip()
                    # Remove leading dashes/hyphens
                    s = re.sub(r'^[-–—\s]+', '', s)
                    s = s.strip()
                    if s:
                        sentences.append(s)
            
            script_data["1"][str(ep)] = sentences
            
        except Exception as e:
            UI.error(f"  ❌ 에피소드 {ep_str} 가져오기 실패: {e}")
            continue
            
    try:
        with open(MODERN_FAMILY_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(script_data, f, ensure_ascii=False, indent=2)
        UI.success("✅ Modern Family 시즌 1 대본 로컬 캐싱 완료!")
    except Exception as e:
        UI.error(f"Modern Family 캐시 파일 저장 실패: {e}")
        
    return script_data

def load_modern_family_sentences():
    """Loads cached sentences, filters them (5-12 words), and returns structured dict"""
    script_data = ensure_modern_family_cache()
    if not script_data:
        return None
        
    filtered_data = {1: {}}
    
    # We will filter in-memory to keep only 5-12 word sentences
    season_keys = list(script_data.keys())
    for s_key in season_keys:
        try:
            s_num = int(s_key)
        except ValueError:
            continue
        if s_num != 1:
            continue
            
        episodes_dict = script_data[s_key]
        for ep_key, sentences in episodes_dict.items():
            try:
                ep_num = int(ep_key)
            except ValueError:
                continue
                
            filtered_sents = []
            for s in sentences:
                words = s.split()
                if 5 <= len(words) <= 12:
                    filtered_sents.append(s)
            filtered_data[1][ep_num] = filtered_sents
            
    return filtered_data

def search_github_repos(query):
    """Searches GitHub for repositories containing vocabulary lists"""
    # Enforce search scope by appending 'vocabulary' keywords
    search_query = f"{query} vocabulary wordlist"
    url = f"https://api.github.com/search/repositories?q={search_query}&sort=stars&order=desc&per_page=10"
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code == 403:
            raise Exception("GitHub API rate limit exceeded. Please try again later.")
        response.raise_for_status()
        data = response.json()
        
        items = data.get("items", [])
        results = []
        for item in items:
            results.append({
                "name": item["full_name"],
                "stars": item["stargazers_count"],
                "description": item.get("description") or "설명 없음",
                "owner": item["owner"]["login"],
                "repo": item["name"]
            })
        return results
    except Exception as e:
        UI.error(f"GitHub 검색 오류: {e}")
        return None

def get_repo_contents(owner, repo, path=""):
    """Fetches files and directories in the repository path"""
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code == 403:
            raise Exception("GitHub API rate limit exceeded.")
        response.raise_for_status()
        items = response.json()
        
        # Ensure it's a list (contents can be a single file dict if path points to a file)
        if not isinstance(items, list):
            return [items]
            
        results = []
        for item in items:
            ext = os.path.splitext(item["name"])[1].lower()
            is_valid_file = item["type"] == "file" and ext in [".json", ".csv", ".txt"]
            is_dir = item["type"] == "dir"
            
            if is_valid_file or is_dir:
                results.append({
                    "name": item["name"],
                    "path": item["path"],
                    "type": item["type"],
                    "download_url": item.get("download_url")
                })
        # Sort directories first, then files
        return sorted(results, key=lambda x: (x["type"] != "dir", x["name"]))
    except Exception as e:
        UI.error(f"저장소 탐색 오류: {e}")
        return None

def download_file_content(download_url):
    """Downloads raw content of a file"""
    try:
        response = requests.get(download_url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        return response.content
    except Exception as e:
        UI.error(f"파일 다운로드 실패: {e}")
        return None

def smart_parse_json(data):
    """Dynamically parses English vocabulary lists from JSON data"""
    # Case 1: Simple list of strings -> ["apple", "banana"]
    if isinstance(data, list):
        if not data:
            return []
        first = data[0]
        if isinstance(first, str):
            return [{"word": item.strip(), "meaning": ""} for item in data if item.strip()]
            
        # Case 2: List of dictionaries -> [{"word": "abate", "meaning": "..."}, ...]
        if isinstance(first, dict):
            # Scan keys to find best candidates for word and meaning
            keys = list(first.keys())
            word_key = next((k for k in keys if k.lower() in ["word", "vocab", "term", "name", "단어"]), None)
            meaning_key = next((k for k in keys if k.lower() in ["meaning", "definition", "translation", "뜻", "explain", "desc"]), None)
            
            if not word_key:
                # Fallback to first string key
                word_key = next((k for k in keys if isinstance(first[k], str)), None)
            
            if not word_key:
                return []
                
            results = []
            for item in data:
                word = str(item.get(word_key, "")).strip()
                meaning = str(item.get(meaning_key, "")) if meaning_key else ""
                # Strip HTML if any
                word = re.sub('<[^<]+?>', '', word)
                meaning = re.sub('<[^<]+?>', '', meaning)
                if word:
                    results.append({"word": word, "meaning": meaning})
            return results

    # Case 3: Dictionary containing a sub-list or nested objects
    elif isinstance(data, dict):
        # Look for common list-holding keys (e.g. "words", "vocab", "data")
        for k, v in data.items():
            if isinstance(v, list) and v:
                parsed = smart_parse_json(v)
                if parsed:
                    return parsed
                    
        # Case 4: Key-value dictionary where keys are words, values are meanings
        # e.g., {"abate": "lessen", "aberrant": "abnormal"}
        first_val = next(iter(data.values()), None)
        if isinstance(first_val, str):
            return [{"word": k.strip(), "meaning": str(v).strip()} for k, v in data.items() if k.strip()]
            
        # Case 5: Nested dictionary like in Oxford 5000: {"0": {"word": "a", ...}}
        if isinstance(first_val, dict):
            keys = list(first_val.keys())
            word_key = next((k for k in keys if k.lower() in ["word", "vocab", "term", "name", "단어"]), None)
            meaning_key = next((k for k in keys if k.lower() in ["meaning", "definition", "translation", "뜻", "explain", "desc"]), None)
            if word_key:
                results = []
                for k, v in data.items():
                    word = str(v.get(word_key, "")).strip()
                    meaning = str(v.get(meaning_key, "")) if meaning_key else ""
                    if word:
                        results.append({"word": word, "meaning": meaning})
                return results
                
    return []

def parse_vocab_file(content_bytes, filename):
    """Decides file type and runs the corresponding parser"""
    ext = os.path.splitext(filename)[1].lower()
    
    # Try decoding
    try:
        content_str = content_bytes.decode('utf-8')
    except:
        try:
            content_str = content_bytes.decode('cp949')
        except Exception as e:
            UI.error(f"인코딩 오류 (파일을 읽을 수 없음): {e}")
            return []

    # 1. JSON Parser
    if ext == ".json":
        try:
            # Clean trailing commas which are common in non-strict JSON files on GitHub
            cleaned_str = re.sub(r',\s*(?=[}\]])', '', content_str)
            data = json.loads(cleaned_str)
            return smart_parse_json(data)
        except Exception as e:
            # Fallback to original string if regex cleaning somehow fails
            try:
                data = json.loads(content_str)
                return smart_parse_json(data)
            except Exception as original_err:
                UI.error(f"JSON 파싱 실패: {original_err}")
                return []

    # 2. CSV Parser
    elif ext == ".csv":
        try:
            lines = content_str.splitlines()
            reader = csv.reader(lines)
            rows = [row for row in reader if row]
            if not rows:
                return []
                
            # If there's a header, let user pick the word column
            header = rows[0]
            UI.subheader("CSV 단어 열(Column) 선택")
            display_headers = [f"열 {idx + 1}: {col[:20]}" for idx, col in enumerate(header)]
            
            word_col_choice = InteractiveSelector.select_one(
                display_headers, 
                title="영단어(Word)가 있는 열을 선택하세요"
            )
            if not word_col_choice:
                return []
            word_idx = display_headers.index(word_col_choice)
            
            # Optionally select meaning column
            display_headers_with_none = ["선택 안 함 (AI가 뜻 자동 완성)"] + display_headers
            meaning_col_choice = InteractiveSelector.select_one(
                display_headers_with_none,
                title="한글 뜻(Meaning)이 있는 열을 선택하세요"
            )
            meaning_idx = -1
            if meaning_col_choice and "선택 안 함" not in meaning_col_choice:
                meaning_idx = display_headers_with_none.index(meaning_col_choice) - 1
                
            results = []
            # Skip header if first row looks like header
            start_row = 1 if len(rows) > 1 else 0
            for row in rows[start_row:]:
                if len(row) > word_idx:
                    word = row[word_idx].strip()
                    meaning = row[meaning_idx].strip() if (meaning_idx >= 0 and len(row) > meaning_idx) else ""
                    if word:
                        results.append({"word": word, "meaning": meaning})
            return results
        except Exception as e:
            UI.error(f"CSV 파싱 실패: {e}")
            return []

    # 3. TXT Parser
    elif ext == ".txt":
        results = []
        for line in content_str.splitlines():
            line = line.strip()
            # Ignore empty lines and comments
            if not line or line.startswith("#") or line.startswith("//"):
                continue
            # Handle possible line format: "word : meaning" or just "word"
            if ":" in line:
                parts = line.split(":", 1)
                results.append({"word": parts[0].strip(), "meaning": parts[1].strip()})
            elif "\t" in line:
                parts = line.split("\t", 1)
                results.append({"word": parts[0].strip(), "meaning": parts[1].strip()})
            else:
                results.append({"word": line, "meaning": ""})
        return results

    return []

def _run_post_processing():
    """Shared post-processing: TTS audio, deck organizer, synonym clustering"""
    UI.info("🔊 누락된 오디오(TTS) 생성 및 추가 중...")
    try:
        from integrations.audio import AnkiTTSFiller
        AnkiTTSFiller.run_audio_addition()
    except Exception as e:
        UI.error(f"오디오 추가 오류: {e}")

    UI.info("📁 카드를 알맞은 덱으로 자동 정리 중...")
    try:
        from utils.organizer import run_organizer
        run_organizer()
    except Exception as e:
        UI.error(f"덱 정리 오류: {e}")

    UI.info("🔗 AI 유의어 맵 업데이트 및 클러스터링 중...")
    try:
        from utils.cluster import run_clustering
        run_clustering()
    except Exception as e:
        UI.error(f"유의어 업데이트 오류: {e}")

    UI.success("✨ 모든 후속 자동화 정리가 완료되었습니다!")


def run_vocab_importer_flow(preset_mode=False, preset_key=None):
    """Unified GitHub + Friends + Modern Family importer flow"""
    UI.clear()
    UI.header("깃허브 실시간 어휘집 탐색 및 가져오기")

    # ── Presets ──────────────────────────────────────────────
    PRESETS = [
        {
            "key": "gre",
            "label": "⭐ GRE 단어장 (Magoosh - 빠른 단어 테스트 추천)",
            "type": "github_file",
            "download_url": "https://raw.githubusercontent.com/vatsalsaglani/gre-vocab/master/words_meanings.json",
            "filename": "words_meanings.json",
        },
        {
            "key": "friends",
            "label": "🎬 Friends 미드 대본 (시즌/에피소드 선택 - 생생한 일상 영어)",
            "type": "friends_csv",
        },
        {
            "key": "modern_family",
            "label": "🎬 Modern Family 시즌 1 (s01e01 제외 - 실용적인 일상 대사)",
            "type": "modern_family_scraping",
        },
    ]

    # ── Step 1: 가져오기 방식 선택 ──────────────────────────
    target_file = None   # for github_file mode
    raw_sentences = None # for friends_csv / sentence mode

    use_preset = preset_mode  # True when called from CLI `--source github`

    if not use_preset:
        method_options = (
            [f"{p['label']}" for p in PRESETS]
            + ["🔍 깃허브 실시간 검색 및 브라우징"]
        )
        method_choice = InteractiveSelector.select_one(
            method_options,
            title="가져오기 방식을 선택하세요"
        )
        if not method_choice:
            return

        preset_labels = [p["label"] for p in PRESETS]
        if method_choice in preset_labels:
            preset = PRESETS[preset_labels.index(method_choice)]
            use_preset = True
        else:
            preset = None

    else:
        # CLI preset_mode
        if preset_key:
            preset = next((p for p in PRESETS if p["key"] == preset_key), PRESETS[0])
        else:
            preset = PRESETS[0]

    # ── Step 2: 소스별 데이터 획득 ───────────────────────────
    if use_preset and preset:
        if preset["type"] == "github_file":
            UI.info(f"🚀 프리셋: {preset['label']}")
            target_file = {
                "name": preset["filename"],
                "download_url": preset["download_url"],
            }

        elif preset["type"] == "friends_csv":
            UI.info("🎬 Friends 대본 데이터셋 로드 중...")
            with UI.wait("Friends 대본 로드 중..."):
                script_data = load_friends_episodes()
            if not script_data:
                UI.ask("계속하려면 Enter를 누르세요", default="")
                return

            # Season selection
            seasons = sorted(script_data.keys())
            season_choice = InteractiveSelector.select_one(
                [f"시즌 {s}" for s in seasons],
                title="Friends 시즌을 선택하세요"
            )
            if not season_choice:
                return
            season = seasons[[f"시즌 {s}" for s in seasons].index(season_choice)]

            # Episode selection
            episodes = sorted(script_data[season].keys())
            episode_choice = InteractiveSelector.select_one(
                [f"에피소드 {e}" for e in episodes],
                title=f"시즌 {season}의 에피소드를 선택하세요"
            )
            if not episode_choice:
                return
            episode = episodes[[f"에피소드 {e}" for e in episodes].index(episode_choice)]

            utterances = script_data[season][episode]
            UI.success(f"시즌 {season} 에피소드 {episode} — 총 {len(utterances)}개 대사 로드 완료")
            raw_sentences = utterances  # list of {speaker, text}

        elif preset["type"] == "modern_family_scraping":
            import glob
            import os
            import re
            
            mf_dir = "/Users/leejinwoo/Downloads/모던 패밀리 시즌1"
            if not os.path.isdir(mf_dir):
                UI.error(f"디렉토리를 찾을 수 없습니다: {mf_dir}")
                UI.ask("계속하려면 Enter를 누르세요", default="")
                return
            
            # Find original .smi files (exclude .en.smi)
            smi_files = sorted([f for f in glob.glob(os.path.join(mf_dir, "*.smi")) if not f.endswith(".en.smi")])
            if not smi_files:
                UI.error(f"해당 폴더에 SMI 파일이 없습니다: {mf_dir}")
                UI.ask("계속하려면 Enter를 누르세요", default="")
                return
            
            episode_options = [os.path.basename(f) for f in smi_files]
            episode_choice = InteractiveSelector.select_one(
                episode_options,
                title="Modern Family 에피소드 자막 파일을 선택하세요"
            )
            if not episode_choice:
                return
            
            selected_file = os.path.join(mf_dir, episode_choice)
            UI.info(f"🎬 '{episode_choice}' 파싱 중...")
            
            with open(selected_file, "r", encoding="cp949", errors="ignore") as f:
                content = f.read()
            
            # Parse ENCC from SMI
            sync_blocks = re.split(r'(?i)<sync\s+start=\d+>', content)
            utterances = []
            for block in sync_blocks:
                if re.search(r'(?i)<p\s+class=encc>', block):
                    text = re.sub(r'(?i).*?<p\s+class=encc>', '', block, count=1, flags=re.DOTALL)
                    text = re.sub(r'<[^>]+>', '', text)
                    text = text.strip()
                    if text and text != '&nbsp;':
                        utterances.append(text)
            
            if not utterances:
                UI.error("선택한 자막에서 영어 대사(ENCC)를 찾지 못했습니다.")
                UI.ask("계속하려면 Enter를 누르세요", default="")
                return
                
            UI.success(f"'{episode_choice}' — 총 {len(utterances)}개 영어 대사 추출 완료")
            
            # Extract Episode/Season info from filename if possible
            match = re.search(r'S(\d{2})E(\d{2})', episode_choice, re.IGNORECASE)
            tag_name = f"S{match.group(1)}E{match.group(2)}" if match else "ModernFamily"
            
            raw_sentences = [
                {"speaker": tag_name, "text": sent}
                for sent in utterances
            ]

    else:
        # ── GitHub live search ──
        query = UI.ask("🔍 검색어 입력 (예: TOEFL, GRE, Modern Family)").strip()
        if not query:
            return

        with UI.wait("GitHub 검색 중..."):
            repos = search_github_repos(query)
        if not repos:
            UI.error("검색 결과가 없습니다.")
            UI.ask("계속하려면 Enter를 누르세요", default="")
            return

        repo_options = [
            f"{r['name']} [dim](★{r['stars']}) - {r['description'][:40]}[/]"
            for r in repos
        ]
        selected_repo_text = InteractiveSelector.select_one(
            repo_options, title="저장소(Repository)를 선택하세요"
        )
        if not selected_repo_text:
            return
        selected_repo = repos[repo_options.index(selected_repo_text)]

        current_path = ""
        while True:
            with UI.wait(f"'{selected_repo['name']}' 파일 목록 로드 중..."):
                items = get_repo_contents(selected_repo["owner"], selected_repo["repo"], current_path)
            if not items:
                UI.error("저장소 내용을 불러올 수 없습니다.")
                UI.ask("계속하려면 Enter를 누르세요", default="")
                return

            options_map = []
            if current_path:
                options_map.append(("..", "📁 [이전 폴더로]"))
            for item in items:
                prefix = "📁" if item["type"] == "dir" else "📄"
                options_map.append((item, f"{prefix} {item['name']}"))
            options_map.append(("cancel", "❌ 작업 취소 및 나가기"))

            choice_text = InteractiveSelector.select_one(
                [opt[1] for opt in options_map],
                title=f"'{selected_repo['name']}/{current_path}' 파일 선택"
            )
            if not choice_text or "작업 취소" in choice_text:
                return

            selected_item = options_map[[opt[1] for opt in options_map].index(choice_text)][0]
            if selected_item == "..":
                parts = current_path.rstrip("/").split("/")
                current_path = "/".join(parts[:-1]) if len(parts) > 1 else ""
            elif selected_item["type"] == "dir":
                current_path = selected_item["path"]
            else:
                target_file = selected_item
                break

    # ── Step 3: 카드 타입 선택 ───────────────────────────────
    card_type_options = [
        ("vocab",    "📖 단어 카드 — 텍스트 속 단어를 추출하여 Vocabulary 카드로 등록"),
        ("sentence", "💬 문장 카드 — 대사/문장 자체를 Sentence 카드로 등록"),
    ]
    card_type_choice = InteractiveSelector.select_one(
        [opt[1] for opt in card_type_options],
        title="어떤 유형의 안키 카드를 만드시겠습니까?"
    )
    if not card_type_choice:
        return
    card_type = next(opt[0] for opt in card_type_options if opt[1] == card_type_choice)

    # ── Step 4: 데이터 소스를 공통 포맷으로 변환 ─────────────
    # parsed_items: list of {text} for sentence mode, or {word, meaning} for vocab mode
    if target_file:
        with UI.wait(f"'{target_file['name']}' 다운로드 및 분석 중..."):
            file_bytes = download_file_content(target_file["download_url"])
            if not file_bytes:
                UI.ask("계속하려면 Enter를 누르세요", default="")
                return

        if card_type == "vocab":
            parsed_items = parse_vocab_file(file_bytes, target_file["name"])
        else:
            # For sentence mode: treat each non-empty line as a sentence
            try:
                content_str = file_bytes.decode("utf-8", errors="ignore")
            except Exception:
                content_str = ""
            parsed_items = [
                {"text": line.strip(), "speaker": ""}
                for line in content_str.splitlines()
                if line.strip() and len(line.strip()) > 20
            ]

    elif raw_sentences:
        if card_type == "vocab":
            # Extract words from utterances
            word_pattern = re.compile(r"\b[a-zA-Z]{4,15}\b")
            word_map = {}
            for ut in raw_sentences:
                for w in word_pattern.findall(ut["text"]):
                    w_lower = w.lower()
                    if w_lower not in word_map:
                        word_map[w_lower] = {"word": w_lower, "meaning": ""}
            parsed_items = list(word_map.values())
        else:
            parsed_items = raw_sentences  # list of {speaker, text}
    else:
        UI.error("데이터 소스를 확인할 수 없습니다.")
        UI.ask("계속하려면 Enter를 누르세요", default="")
        return

    if not parsed_items:
        UI.error("항목을 파싱하지 못했습니다.")
        UI.ask("계속하려면 Enter를 누르세요", default="")
        return

    # ── Step 5: 중복 필터링 ───────────────────────────────────
    with UI.wait("내 안키 덱 로드 및 중복 필터링 중..."):
        try:
            if card_type == "vocab":
                existing = AnkiConnector.get_existing_vocab_words(MODEL_VOCAB)
                existing_set = {w.lower().strip() for w in existing}
                new_items = []
                for item in parsed_items:
                    word = re.sub("<[^<]+?>", "", item.get("word", "")).strip()
                    if word and word.lower() not in existing_set:
                        item["word"] = word
                        new_items.append(item)
            else:
                existing_sentences = AnkiConnector.get_existing_vocab_words(MODEL_SENTENCE)
                existing_set = {s.lower().strip() for s in existing_sentences}
                new_items = [
                    item for item in parsed_items
                    if item.get("text", "").lower().strip() not in existing_set
                ]
        except Exception as e:
            UI.error(f"Anki 연결 실패: {e}")
            UI.ask("계속하려면 Enter를 누르세요", default="")
            return

    total = len(parsed_items)
    dup_count = total - len(new_items)
    UI.success("중복 필터링 완료!")
    UI.print(f"  - 전체 항목: {total}개")
    UI.print(f"  - 기존 안키에 있는 항목: {dup_count}개 (자동 제외)")
    UI.print(f"  - 신규 항목: {len(new_items)}개", style="bold green")

    if not new_items:
        UI.info("새로 가져올 수 있는 항목이 없습니다.")
        UI.ask("계속하려면 Enter를 누르세요", default="")
        return

    # ── Step 6: 가져올 개수 선택 ─────────────────────────────
    label = "단어" if card_type == "vocab" else "문장"
    
    if preset and preset.get("type") == "modern_family_scraping":
        import_count = len(new_items)
    else:
        count_str = UI.ask(
            f"❓ 이 중 몇 개의 {label}을 가져오시겠습니까? (기본값: 30, 최대: {len(new_items)})"
        ).strip()
        try:
            import_count = int(count_str) if count_str else 30
        except Exception:
            import_count = 30
            
    import_count = max(1, min(import_count, len(new_items)))
    sampled = new_items[:import_count]

    # ── Step 7: 최종 검수 ─────────────────────────────────────
    if card_type == "vocab":
        display = [
            f"{w['word']}" + (f" : {w['meaning']}" if w.get("meaning") else "")
            for w in sampled
        ]
    else:
        display = [
            f"[{item.get('speaker', '')}] {item['text'][:60]}..."
            if len(item["text"]) > 60
            else f"[{item.get('speaker', '')}] {item['text']}"
            for item in sampled
        ]

    selector = InteractiveSelector(
        display,
        title=f"최종 {label} 선택 (가져올 항목을 체크하세요)",
        help_text="SPACE: 토글 | A: 전체선택 | N: 선택해제 | C: 확정 | Q: 취소"
    )
    selected_indices = selector.run_indices()

    if not selected_indices:
        UI.info("작업이 취소되었습니다.")
        UI.ask("계속하려면 Enter를 누르세요", default="")
        return

    final_items = [sampled[idx] for idx in selected_indices]
    UI.info(f"선택된 {len(final_items)}개 {label} 보강 및 안키 추가 시작...")

    # ── Step 8: NoteCompleter 연동 ────────────────────────────
    if card_type == "vocab":
        sentences_data = {"sentences": []}
        vocab_data = {
            "vocab": [{"단어": item["word"], "뜻": item.get("meaning", "")} for item in final_items]
        }
    else:
        sentences_data = {
            "sentences": [item["text"] for item in final_items]
        }
        vocab_data = {"vocab": []}

    success, added_s, added_v = run_note_completion(sentences_data, vocab_data)

    if success:
        added_count = len(added_v) if card_type == "vocab" else len(added_s)
        UI.success(f"🎉 총 {added_count}개의 카드가 성공적으로 보강 및 추가되었습니다!")
        _run_post_processing()
    else:
        UI.error("보강 작업 중 오류가 발생했습니다.")

    UI.ask("계속하려면 Enter를 누르세요", default="")




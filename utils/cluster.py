import json
import os
import re
import time
import random
import numpy as np
from google import genai
from google.genai import types
from sklearn.preprocessing import normalize
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

from config import MODEL_VOCAB, USER_CONFIG_PATH
from integrations.anki_connect import AnkiConnector
from utils.synonym_sync import run_synonym_sync

# --- Verified Configuration ---
EMBEDDING_MODEL = "models/gemini-embedding-001"
CACHE_FILE = os.path.join(os.path.dirname(USER_CONFIG_PATH), 'embeddings_cache_v3.json')
CW_THRESHOLD = 0.90
WEIGHT_WORD = 0.5
WEIGHT_MEANING = 0.5

class SynonymClusterer:
    def __init__(self, pbar=None):
        self.client = genai.Client(api_key=GOOGLE_API_KEY)
        self.pbar = pbar
        self.cache = self._load_cache()

    def _load_cache(self):
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except: return {}
        return {}

    def _save_cache(self):
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.cache, f, ensure_ascii=False, indent=2)

    def _get_embeddings_batch(self, texts):
        try:
            response = self.client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=texts,
                config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT", output_dimensionality=768)
            )
            return [e.values for e in response.embeddings]
        except Exception as e:
            print(f"⚠️ API 요청 에러: {e}")
            return [None] * len(texts)

    def _get_vectors_for_data(self, data_list, type_key):
        texts_to_embed = list(set([item[type_key] for item in data_list if item[type_key] and item[type_key] not in self.cache]))
        
        if texts_to_embed:
            print(f"🧠 {type_key} 벡터 변환 중 ({len(texts_to_embed)}개)...")
            batch_size = 50 
            for i in tqdm(range(0, len(texts_to_embed), batch_size)):
                batch = texts_to_embed[i:i+batch_size]
                embeddings = self._get_embeddings_batch(batch)
                if embeddings:
                    for text, vector in zip(batch, embeddings):
                        if vector: self.cache[text] = vector
                if i % 200 == 0: self._save_cache()
                time.sleep(0.1)
            self._save_cache()
        
        vectors = []
        zero_vector = [0.0] * 768
        for item in data_list:
            v = self.cache.get(item[type_key])
            vectors.append(v if v and len(v) == 768 else zero_vector)
        return np.array(vectors, dtype=np.float32)

    def _run_chinese_whispers(self, vectors, threshold=CW_THRESHOLD, iterations=15):
        """Graphs-based clustering for high-quality synonym grouping."""
        num_nodes = len(vectors)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        v_norm = vectors / norms
        
        # Dot product for cosine similarity
        sim_matrix = np.dot(v_norm, v_norm.T)
        labels = list(range(num_nodes))
        
        for it in range(iterations):
            order = list(range(num_nodes))
            random.shuffle(order)
            changes = 0
            for i in order:
                neighbors = np.where(sim_matrix[i] > threshold)[0]
                if len(neighbors) == 0: continue
                
                weights = {}
                for j in neighbors:
                    if i == j: continue
                    l = labels[j]
                    weights[l] = weights.get(l, 0) + sim_matrix[i, j]
                
                if not weights: continue
                max_label = max(weights, key=weights.get)
                if labels[i] != max_label:
                    labels[i] = max_label
                    changes += 1
            if changes == 0: break
        return np.array(labels)

    def process_all_vocab(self):
        print(f"🔍 Anki에서 '{MODEL_VOCAB}' 데이터를 가져오는 중...")
        note_ids = AnkiConnector.find_notes(query=f'"note:{MODEL_VOCAB}"')
        if not note_ids: return []
        notes_info = AnkiConnector.get_notes_info(note_ids)
        
        normal_data, idiom_data = [], []
        for note in notes_info:
            word = re.sub('<[^<]+?>', '', note['fields']['단어']['value']).strip()
            meaning = re.sub('<[^<]+?>', '', note['fields']['뜻']['value']).strip()
            pos = re.sub('<[^<]+?>', '', note['fields'].get('품사', {}).get('value', '')).lower().strip()
            pos_tags = [p.strip() for p in re.split(r'[,/]', pos) if p.strip()]
            
            item = {"id": note['noteId'], "word": word, "meaning": meaning, "pos": pos_tags}
            if " " in word: idiom_data.append(item)
            else: normal_data.append(item)

        final_clusters = []
        for label, data in [("일반 단어", normal_data), ("이디엄", idiom_data)]:
            if not data: continue
            print(f"\n📦 {label} 클러스터링 시작 ({len(data)}개)")
            v_word = normalize(self._get_vectors_for_data(data, "word")) * WEIGHT_WORD
            v_mean = normalize(self._get_vectors_for_data(data, "meaning")) * WEIGHT_MEANING
            combined = np.concatenate([v_word, v_mean], axis=1)
            
            labels = self._run_chinese_whispers(combined)
            final_clusters.extend(self._post_process_labels(data, labels))
        return final_clusters

    def _post_process_labels(self, data, labels):
        clusters = {}
        for i, label in enumerate(labels):
            if label not in clusters: clusters[label] = []
            clusters[label].append(data[i])
        
        refined = []
        for members in clusters.values():
            if len(members) < 2: continue
            sub_groups = self._split_by_pos(members)
            for sg in sub_groups:
                if len(sg) >= 2:
                    refined.append([{**m, "similarity": "N/A"} for m in sg])
        return refined

    def _split_by_pos(self, members):
        remaining = list(members)
        sub_groups = []
        while remaining:
            curr = [remaining.pop(0)]
            changed = True
            while changed:
                changed = False
                for i in range(len(remaining)-1, -1, -1):
                    if any(set(remaining[i]['pos']) & set(m['pos']) for m in curr):
                        curr.append(remaining.pop(i))
                        changed = True
            sub_groups.append(curr)
        return sub_groups

    def generate_report(self, clusters, filename='synonym_clusters.md'):
        report_path = os.path.join(os.path.dirname(USER_CONFIG_PATH), filename)
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(f"# Anki Synonym Clusters Report (CW)\n\n")
            f.write(f"Generated at: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total groups: {len(clusters)}\n\n")
            for i, group in enumerate(clusters):
                f.write(f"### Group {i+1}\n")
                for item in group:
                    f.write(f"- **{item['word']}**: {item['meaning']} ({', '.join(item['pos'])})\n")
                f.write("\n")
        return report_path

def run_clustering(pbar=None, step_points=0):
    clusterer = SynonymClusterer(pbar=pbar)
    raw_clusters = clusterer.process_all_vocab()
    if not raw_clusters:
        if pbar and step_points > 0: pbar.update(step_points)
        else: print("ℹ️ 유의어 그룹을 찾지 못했습니다.")
        return
    
    report_path = clusterer.generate_report(raw_clusters)
    if pbar: pbar.write(f"✅ 클러스터링 완료! 보고서: {report_path}")
    else: print(f"✅ 클러스터링 완료! 보고서: {report_path}")
    
    if pbar: pbar.set_description("Syncing Synonyms to Anki...")
    run_synonym_sync(clusters=raw_clusters)
    
    if pbar and step_points > 0:
        pbar.update(step_points)

if __name__ == "__main__":
    run_clustering()

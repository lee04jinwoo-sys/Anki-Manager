import json
import os
import re
import time
import numpy as np
import umap
from google import genai
from google.genai import types
from sklearn.cluster import HDBSCAN
from sklearn.preprocessing import normalize
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

from config import MODEL_VOCAB, USER_CONFIG_PATH
from integrations.anki_connect import AnkiConnector
from utils.synonym_sync import run_synonym_sync

# Embedding model
EMBEDDING_MODEL = "text-embedding-004"
CACHE_FILE = os.path.join(os.path.dirname(USER_CONFIG_PATH), 'embeddings_cache_v2.json')

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
        """Fetches embeddings for a batch of texts. Returns a list of vectors."""
        try:
            # Batch embedding call
            response = self.client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=texts,
                config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT", output_dimensionality=768)
            )
            
            embeddings = [e.values for e in response.embeddings]
            
            # If the response doesn't match the request size, fall back to individual calls for this batch
            if len(embeddings) != len(texts):
                print(f"⚠️ 배치 응답 불일치 ({len(embeddings)}/{len(texts)}). 개별 요청으로 전환합니다...")
                return self._get_embeddings_individual(texts)
                
            return embeddings
        except Exception as e:
            print(f"⚠️ 배치 요청 에러: {e}. 개별 요청으로 전환합니다...")
            return self._get_embeddings_individual(texts)

    def _get_embeddings_individual(self, texts):
        """Fall back to processing one by one if batch fails."""
        results = []
        for t in texts:
            try:
                response = self.client.models.embed_content(
                    model=EMBEDDING_MODEL,
                    contents=t,
                    config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT", output_dimensionality=768)
                )
                if hasattr(response, 'embeddings') and response.embeddings:
                    results.append(response.embeddings[0].values)
                elif hasattr(response, 'embedding') and response.embedding:
                    results.append(response.embedding.values)
                else:
                    results.append(None)
            except Exception as e:
                print(f"❌ 개별 벡터 변환 실패 ('{t[:10]}...'): {e}")
                results.append(None)
            time.sleep(0.05)
        return results

    def _get_vectors_for_data(self, data_list, type_key):
        """Fetches and caches embeddings for a list of strings."""
        texts_to_embed = list(set([item[type_key] for item in data_list if item[type_key] and item[type_key] not in self.cache]))
        
        if texts_to_embed:
            print(f"🧠 {type_key} 벡터 변환 중 ({len(texts_to_embed)}개)...")
            batch_size = 50 
            for i in tqdm(range(0, len(texts_to_embed), batch_size)):
                batch = texts_to_embed[i:i+batch_size]
                embeddings = self._get_embeddings_batch(batch)
                
                if embeddings:
                    for text, vector in zip(batch, embeddings):
                        if vector:
                            self.cache[text] = vector
                
                if i % 200 == 0: self._save_cache()
                time.sleep(0.1)
            self._save_cache()
        
        vectors = []
        zero_vector = [0.0] * 768
        missing_count = 0
        
        for item in data_list:
            v = self.cache.get(item[type_key])
            if v is None or len(v) != 768:
                vectors.append(zero_vector)
                missing_count += 1
            else:
                vectors.append(v)
        
        if missing_count > 0:
            print(f"⚠️ {type_key}: {missing_count}/{len(data_list)}개의 항목에 대한 벡터가 없어 0으로 대체되었습니다.")
            
        return np.array(vectors, dtype=np.float32)

    def process_all_vocab(self):
        print(f"🔍 Anki에서 '{MODEL_VOCAB}' 노트를 가져오는 중...")
        note_ids = AnkiConnector.find_notes(query=f'"note:{MODEL_VOCAB}"')
        if not note_ids: return []
        notes_info = AnkiConnector.get_notes_info(note_ids)
        
        normal_data = []
        idiom_data = []

        for note in notes_info:
            word = re.sub('<[^<]+?>', '', note['fields']['단어']['value']).strip()
            meaning = re.sub('<[^<]+?>', '', note['fields']['뜻']['value']).strip()
            pos = re.sub('<[^<]+?>', '', note['fields'].get('품사', {}).get('value', '')).lower().strip()
            pos_tags = [p.strip() for p in re.split(r'[,/]', pos) if p.strip()]
            
            item = {
                "id": note['noteId'],
                "word": word,
                "meaning": meaning,
                "pos": pos_tags
            }
            
            if " " in word:
                idiom_data.append(item)
            else:
                normal_data.append(item)

        final_clusters = []

        # 1. Normal Word Clustering (Weighted Concat)
        if normal_data:
            print(f"\n📦 일반 단어 클러스터링 시작 ({len(normal_data)}개)")
            word_vectors = self._get_vectors_for_data(normal_data, "word")
            meaning_vectors = self._get_vectors_for_data(normal_data, "meaning")
            
            # Normalize and Weight
            word_vectors = normalize(word_vectors) * 0.4
            meaning_vectors = normalize(meaning_vectors) * 0.6
            combined_vectors = np.concatenate([word_vectors, meaning_vectors], axis=1)
            
            labels = self._run_clustering_pipeline(combined_vectors)
            final_clusters.extend(self._post_process_labels(normal_data, labels))

        # 2. Idiom Clustering (Meaning Only)
        if idiom_data:
            print(f"\n📦 이디엄 클러스터링 시작 ({len(idiom_data)}개)")
            meaning_vectors = self._get_vectors_for_data(idiom_data, "meaning")
            combined_vectors = normalize(meaning_vectors)
            
            labels = self._run_clustering_pipeline(combined_vectors)
            final_clusters.extend(self._post_process_labels(idiom_data, labels))

        return final_clusters

    def _run_clustering_pipeline(self, vectors):
        # 1. Dimensionality Reduction with UMAP
        print(f"📉 UMAP 차원 축소 중 (50차원)...")
        reducer = umap.UMAP(n_components=50, metric='cosine', random_state=42)
        reduced_vectors = reducer.fit_transform(vectors)

        # 2. Clustering with HDBSCAN
        print(f"🧬 HDBSCAN 클러스터링 실행 중...")
        clusterer = HDBSCAN(min_cluster_size=2, min_samples=5, metric='cosine')
        labels = clusterer.fit_predict(reduced_vectors)
        
        unique_labels = set(labels)
        if -1 in unique_labels: unique_labels.remove(-1)
        
        if unique_labels:
            counts = [np.sum(labels == l) for l in unique_labels]
            max_size = max(counts)
            print(f"📊 클러스터 분석: 총 {len(unique_labels)}개 그룹 발견 (최대 크기: {max_size})")
        else:
            print(f"📊 클러스터 분석: 그룹이 발견되지 않았습니다.")
            
        return labels

    def _post_process_labels(self, data, labels):
        clusters = {}
        for i, label in enumerate(labels):
            if label == -1: continue 
            if label not in clusters: clusters[label] = []
            clusters[label].append(data[i])
        
        refined = []
        for label, members in clusters.items():
            sub_groups = self._split_by_pos(members)
            for sg in sub_groups:
                if len(sg) >= 2:
                    refined.append([{**m, "similarity": "N/A"} for m in sg])
        return refined

    def _split_by_pos(self, members):
        if not members: return []
        remaining = list(members)
        sub_groups = []
        while remaining:
            current_group = [remaining.pop(0)]
            changed = True
            while changed:
                changed = False
                for i in range(len(remaining)-1, -1, -1):
                    item = remaining[i]
                    if any(set(item['pos']) & set(m['pos']) for m in current_group):
                        current_group.append(remaining.pop(i))
                        changed = True
            sub_groups.append(current_group)
        return sub_groups

    def generate_report(self, clusters, filename='synonym_clusters.md'):
        report_path = os.path.join(os.path.dirname(USER_CONFIG_PATH), filename)
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("# Anki Synonym Clusters Report (HDBSCAN)\n\n")
            f.write(f"Generated at: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"Total groups found: {len(clusters)}\n\n")
            for i, group in enumerate(clusters):
                f.write(f"### Group {i+1}\n")
                for item in group:
                    f.write(f"- **{item['word']}**: {item['meaning']} ({', '.join(item['pos'])})\n")
                f.write("\n")
        return report_path

def run_clustering():
    clusterer = SynonymClusterer()
    raw_clusters = clusterer.process_all_vocab()
    if not raw_clusters:
        print("ℹ️ 유의어 그룹을 찾지 못했습니다.")
        return
    report_path = clusterer.generate_report(raw_clusters)
    print(f"✅ 클러스터링 완료! 보고서: {report_path}")
    print("\n🚀 유의어를 안키 카드에 반영합니다...")
    run_synonym_sync(clusters=raw_clusters)

if __name__ == "__main__":
    run_clustering()

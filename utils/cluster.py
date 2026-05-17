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
EMBEDDING_MODEL = "models/gemini-embedding-001"
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
            response = self.client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=texts,
                config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT", output_dimensionality=768)
            )
            embeddings = [e.values for e in response.embeddings]
            if len(embeddings) != len(texts):
                return self._get_embeddings_individual(texts)
            return embeddings
        except:
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
            except:
                results.append(None)
            time.sleep(0.05)
        return results

    def _get_vectors_for_data(self, data_list, type_key):
        """Fetches and caches embeddings for a list of strings."""
        texts_to_embed = list(set([item[type_key] for item in data_list if item[type_key] and item[type_key] not in self.cache]))
        
        if texts_to_embed:
            msg = f"🧠 {type_key} 벡터 변환 중 ({len(texts_to_embed)}개)..."
            if self.pbar: self.pbar.write(msg)
            else: print(msg)
            
            batch_size = 50 
            for i in tqdm(range(0, len(texts_to_embed), batch_size), disable=self.pbar is not None):
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
        for item in data_list:
            v = self.cache.get(item[type_key])
            vectors.append(v if (v is not None and len(v) == 768) else zero_vector)
        return np.array(vectors, dtype=np.float32)

    def _clean_idiom_meaning(self, meaning):
        """이디엄의 뜻에서 구조적인 노이즈를 철저히 제거합니다."""
        cleaned = re.sub(r'[\(\[\{].*?[\)\]\}]', '', meaning)
        placeholders = r'(?:\b[A-Z]\b|\bsb\b|\bsth\b|\bsbd\b|\bsomeone\b|\bsomething\b|\boneself\b)'
        particles = r'(?:에(?:게|서|대한|대해|관한|관하여|의)?|의|로(?:부터|서|써|대해)?|와|과|를|을|이|가|은|는|도|만|까지|부터|하고|이랑|나|이나)'
        cleaned = re.sub(f'{placeholders}(?:\'s)?\s*{particles}?', '', cleaned, flags=re.IGNORECASE)
        v_patterns = r'(?:하는\s*것|하기|함|하도록|할|하여|해서|하면|한|했던|하려는|함에|하기를|하느라)'
        cleaned = re.sub(f'\\bV\\b\s*{v_patterns}?', '', cleaned)
        cleaned = re.sub(r'[^가-힣a-zA-Z0-9\s,]', ' ', cleaned)
        cleaned = re.sub(f'^\\s*{particles}\\s*', '', cleaned)
        cleaned = re.sub(f'\\s*{particles}\\s*$', '', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned if len(cleaned) > 1 else meaning

    def process_all_vocab(self):
        msg = f"🔍 Anki에서 '{MODEL_VOCAB}' 노트를 가져오는 중..."
        if self.pbar: self.pbar.write(msg)
        else: print(msg)
        
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
                item['meaning_clean'] = self._clean_idiom_meaning(meaning)
                idiom_data.append(item)
            else:
                normal_data.append(item)

        final_clusters = []

        if normal_data:
            msg = f"\n📦 일반 단어 클러스터링 시작 ({len(normal_data)}개)"
            if self.pbar: self.pbar.write(msg)
            else: print(msg)
            word_vectors = self._get_vectors_for_data(normal_data, "word")
            meaning_vectors = self._get_vectors_for_data(normal_data, "meaning")
            word_vectors = normalize(word_vectors) * 0.2
            meaning_vectors = normalize(meaning_vectors) * 0.8
            combined_vectors = np.concatenate([word_vectors, meaning_vectors], axis=1)
            labels = self._run_clustering_pipeline(combined_vectors)
            final_clusters.extend(self._post_process_labels(normal_data, labels, combined_vectors))

        if idiom_data:
            msg = f"\n📦 이디엄 클러스터링 시작 ({len(idiom_data)}개)"
            if self.pbar: self.pbar.write(msg)
            else: print(msg)
            meaning_vectors = self._get_vectors_for_data(idiom_data, "meaning_clean")
            combined_vectors = normalize(meaning_vectors)
            labels = self._run_clustering_pipeline(combined_vectors)
            final_clusters.extend(self._post_process_labels(idiom_data, labels, combined_vectors))

        return final_clusters

    def _run_clustering_pipeline(self, vectors):
        msg = f"📉 UMAP 차원 축소 중 (50차원)..."
        if self.pbar: self.pbar.write(msg)
        else: print(msg)
        reducer = umap.UMAP(n_neighbors=15, n_components=50, metric='cosine', random_state=42)
        reduced_vectors = reducer.fit_transform(vectors)

        msg = f"🧬 HDBSCAN 클러스터링 실행 중..."
        if self.pbar: self.pbar.write(msg)
        else: print(msg)
        clusterer = HDBSCAN(min_cluster_size=2, min_samples=3, cluster_selection_method='leaf', metric='cosine')
        labels = clusterer.fit_predict(reduced_vectors)
        
        unique_labels = set(labels)
        if -1 in unique_labels: unique_labels.remove(-1)
        if unique_labels:
            counts = [np.sum(labels == l) for l in unique_labels]
            msg = f"📊 클러스터 분석: 총 {len(unique_labels)}개 그룹 발견 (최대 크기: {max(counts)})"
            if self.pbar: self.pbar.write(msg)
            else: print(msg)
        return labels

    def _remove_outliers_from_cluster(self, indices, vectors):
        """클러스터 중심점에서 너무 먼 단어들을 제거합니다."""
        if len(indices) < 2: return indices
        sub_vecs = vectors[indices]
        norms = np.linalg.norm(sub_vecs, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        normed_vecs = sub_vecs / norms
        
        centroid = normed_vecs.mean(axis=0)
        c_norm = np.linalg.norm(centroid)
        if c_norm == 0: return indices
        centroid /= c_norm
        
        sims = np.dot(normed_vecs, centroid)
        mean_sim = np.mean(sims)
        MIN_ABS_SIM = 0.75
        
        filtered_local_indices = [
            i for i, sim in enumerate(sims) 
            if sim >= mean_sim - 0.10 and sim >= MIN_ABS_SIM
        ]
        return [indices[i] for i in filtered_local_indices]

    def _post_process_labels(self, data, labels, vectors):
        import difflib
        def get_spelling_sim(s1, s2):
            return difflib.SequenceMatcher(None, s1.lower(), s2.lower()).ratio()

        clusters = {}
        for i, label in enumerate(labels):
            if label != -1:
                if label not in clusters: clusters[label] = []
                clusters[label].append(i)
        
        refined = []
        for label, indices in clusters.items():
            filtered_indices = self._remove_outliers_from_cluster(indices, vectors)
            if len(filtered_indices) < 2: continue
            
            current_members_data = [data[i] for i in filtered_indices]
            sub_groups_data = self._split_by_pos(current_members_data)
            
            for sg_data in sub_groups_data:
                sg_orig_indices = []
                for item in sg_data:
                    for idx in filtered_indices:
                        if data[idx]['id'] == item['id']:
                            sg_orig_indices.append(idx)
                            break
                
                if 2 <= len(sg_orig_indices) <= 6:
                    final_indices = self._remove_outliers_from_cluster(sg_orig_indices, vectors)
                    if len(final_indices) >= 2:
                        too_similar = False
                        for a in range(len(final_indices)):
                            for b in range(a + 1, len(final_indices)):
                                if get_spelling_sim(data[final_indices[a]]['word'], data[final_indices[b]]['word']) > 0.75:
                                    too_similar = True; break
                            if too_similar: break
                        if not too_similar:
                            refined.append([{**data[i], "similarity": "N/A"} for i in final_indices])
                            
                elif len(sg_orig_indices) > 6:
                    sub_vectors = vectors[sg_orig_indices]
                    norms = np.linalg.norm(sub_vectors, axis=1, keepdims=True)
                    norms[norms == 0] = 1.0
                    v_norm = sub_vectors / norms
                    sim_matrix = np.dot(v_norm, v_norm.T)
                    pool = list(range(len(sg_orig_indices)))
                    
                    while len(pool) >= 2:
                        best_sim = -1
                        best_pair = None
                        for a in range(len(pool)):
                            for b in range(a + 1, len(pool)):
                                sim = sim_matrix[pool[a], pool[b]]
                                s_sim = get_spelling_sim(sg_data[pool[a]]['word'], sg_data[pool[b]]['word'])
                                if sim > best_sim and s_sim < 0.75:
                                    best_sim = sim
                                    best_pair = (pool[a], pool[b])
                        
                        if not best_pair or best_sim < 0.85: break 
                        core_idx = [best_pair[0], best_pair[1]]
                        pool.remove(best_pair[0]); pool.remove(best_pair[1])
                        
                        for _ in range(4):
                            if not pool: break
                            best_neighbor_sim = -1
                            best_neighbor = None
                            for p_idx in pool:
                                avg_sim = np.mean([sim_matrix[p_idx, c] for c in core_idx])
                                is_morph = any(get_spelling_sim(sg_data[p_idx]['word'], sg_data[c]['word']) > 0.75 for c in core_idx)
                                if avg_sim > best_neighbor_sim and not is_morph:
                                    best_neighbor_sim = avg_sim
                                    best_neighbor = p_idx
                            if best_neighbor_sim > 0.85:
                                core_idx.append(best_neighbor); pool.remove(best_neighbor)
                            else: break
                        
                        if len(core_idx) >= 2:
                            refined.append([{**sg_data[c], "similarity": "N/A"} for c in core_idx])
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
            f.write("# Anki Synonym Clusters Report (Final Refined)\n\n")
            f.write(f"Generated at: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"Total groups found: {len(clusters)}\n\n")
            for i, group in enumerate(clusters):
                f.write(f"### Group {i+1} (Size: {len(group)})\n")
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

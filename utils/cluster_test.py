import json
import os
import re
import time
import numpy as np
from google import genai
from google.genai import types
from sklearn.neighbors import NearestNeighbors
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

from config import MODEL_VOCAB, USER_CONFIG_PATH
from integrations.anki_connect import AnkiConnector

# Shared Settings
EMBEDDING_MODEL = "models/gemini-embedding-2"
CACHE_FILE = os.path.join(os.path.dirname(USER_CONFIG_PATH), 'test_embeddings_cache.json')

class StrategyTester:
    def __init__(self):
        self.client = genai.Client(api_key=GOOGLE_API_KEY)
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
            print(f"❌ API Error: {e}")
            return None

    def get_base_data(self, limit=500):
        print(f"🔍 Fetching {MODEL_VOCAB} notes (Latest {limit})...")
        note_ids = AnkiConnector.find_notes(query=f'"note:{MODEL_VOCAB}"')
        note_ids.sort(reverse=True)
        target_ids = note_ids[:limit]
        
        notes_info = AnkiConnector.get_notes_info(target_ids)
        
        base_data = []
        for note in notes_info:
            fields = note['fields']
            word = fields['단어']['value'].strip()
            meaning = fields['뜻']['value'].strip()
            pos = fields.get('품사', {}).get('value', '').lower().strip()
            
            clean_word = re.sub('<[^<]+?>', '', word).strip()
            clean_meaning = re.sub('<[^<]+?>', '', meaning).strip()
            clean_pos = re.sub('<[^<]+?>', '', pos).strip()
            
            pos_tags = [p.strip() for p in re.split(r'[,/]', clean_pos) if p.strip()]
            
            base_data.append({
                "id": note['noteId'],
                "word": clean_word,
                "meaning": clean_meaning,
                "pos": pos_tags
            })
        return base_data

    def run_star_strategy(self, base_data, threshold=0.75):
        print(f"\n🚀 Running Simplified Star Strategy (Meaning-Only, Threshold: {threshold})")
        
        # 1. Get/Cache Embeddings for meanings
        texts_to_embed = list(set([item['meaning'] for item in base_data if item['meaning'] not in self.cache]))
        if texts_to_embed:
            print(f"🧠 Embedding {len(texts_to_embed)} new meanings...")
            batch_size = 50
            for i in tqdm(range(0, len(texts_to_embed), batch_size)):
                batch = texts_to_embed[i:i+batch_size]
                embeddings = self._get_embeddings_batch(batch)
                if embeddings:
                    for text, vector in zip(batch, embeddings):
                        self.cache[text] = vector
            self._save_cache()

        # 2. Vector Calculation
        vectors = []
        valid_items = []
        for item in base_data:
            if item['meaning'] in self.cache:
                vectors.append(self.cache[item['meaning']])
                valid_items.append(item)
        
        if not vectors: return []
        X = np.array(vectors)
        X_norm = X / np.linalg.norm(X, axis=1, keepdims=True)

        # 3. Pair Finding with POS Filter
        nn = NearestNeighbors(radius=1-threshold, metric='cosine')
        nn.fit(X_norm)
        distances, indices = nn.radius_neighbors(X_norm)

        all_pairs = []
        for i in range(len(valid_items)):
            for idx_in_results, neighbor_idx in enumerate(indices[i]):
                if neighbor_idx <= i: continue
                sim = 1 - distances[i][idx_in_results]
                
                # POS Filter
                if set(valid_items[i]['pos']) & set(valid_items[neighbor_idx]['pos']):
                    all_pairs.append({"sim": sim, "pair": (i, neighbor_idx)})
        
        all_pairs.sort(key=lambda x: x['sim'], reverse=True)
        
        # 4. Star Clustering Algorithm
        clusters = []
        word_to_cluster = {}

        for item in all_pairs:
            sim = item['sim']
            idx1, idx2 = item['pair']
            
            if idx1 not in word_to_cluster and idx2 not in word_to_cluster:
                new_c = [idx1, idx2]
                clusters.append(new_c)
                word_to_cluster[idx1] = new_c
                word_to_cluster[idx2] = new_c
            elif idx1 in word_to_cluster and idx2 not in word_to_cluster:
                c = word_to_cluster[idx1]
                # Compare only with the "Leader" (the first word in the cluster)
                if np.dot(X_norm[idx2], X_norm[c[0]]) >= threshold:
                    c.append(idx2)
                    word_to_cluster[idx2] = c
            elif idx2 in word_to_cluster and idx1 not in word_to_cluster:
                c = word_to_cluster[idx2]
                if np.dot(X_norm[idx1], X_norm[c[0]]) >= threshold:
                    c.append(idx1)
                    word_to_cluster[idx1] = c

        # 5. Result Formatting
        final = []
        for c in clusters:
            group = []
            for idx in c:
                group.append({"word": valid_items[idx]['word'], "meaning": valid_items[idx]['meaning']})
            final.append(group)
        return final

    def save_report(self, clusters):
        path = os.path.join(os.path.dirname(USER_CONFIG_PATH), f"test_result_Simplified_Star.md")
        with open(path, 'w', encoding='utf-8') as f:
            f.write(f"# Simplified Star Strategy Results\n\nTotal Groups: {len(clusters)}\n\n")
            for i, group in enumerate(clusters):
                f.write(f"### Group {i+1}\n")
                for item in group:
                    f.write(f"- **{item['word']}**: {item['meaning']}\n")
                f.write("\n")
        print(f"✅ Report saved to {path}")

def main():
    tester = StrategyTester()
    base_data = tester.get_base_data()
    results = tester.run_star_strategy(base_data)
    tester.save_report(results)

if __name__ == "__main__":
    main()

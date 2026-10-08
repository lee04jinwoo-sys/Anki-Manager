import re

with open('/Users/leejinwoo/Desktop/Projects/Anki Manager/utils/cluster.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add _load_clusters and _save_clusters right before process_all_vocab
methods = """
    def _load_clusters(self):
        cluster_file = os.path.join(os.path.dirname(USER_CONFIG_PATH), 'synonym_clusters.json')
        if os.path.exists(cluster_file):
            try:
                with open(cluster_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except: return []
        return []

    def _save_clusters(self, clusters):
        cluster_file = os.path.join(os.path.dirname(USER_CONFIG_PATH), 'synonym_clusters.json')
        with open(cluster_file, 'w', encoding='utf-8') as f:
            json.dump(clusters, f, ensure_ascii=False, indent=2)

    def process_all_vocab(self, full_recluster=False):
"""
content = re.sub(r'    def process_all_vocab\(self\):', methods, content)

# Replace the body of process_all_vocab
body_old = r"""        msg = f"🔍 Anki에서 '{MODEL_VOCAB}' 노트를 가져오는 중..."
        if self\.pbar: self\.pbar\.write\(msg\)
        else: print\(msg\)
        
        note_ids = AnkiConnector\.find_notes\(query=f'"note:{MODEL_VOCAB}"'\)
        if not note_ids: return \[\]
        notes_info = AnkiConnector\.get_notes_info\(note_ids\)
        
        normal_data = \[\]
        idiom_data = \[\]

        for note in notes_info:
            word = re\.sub\('<\[\^<\]\+?>', '', note\['fields'\]\['단어'\]\['value'\]\)\.strip\(\)
            meaning = re\.sub\('<\[\^<\]\+?>', '', note\['fields'\]\['뜻'\]\['value'\]\)\.strip\(\)
            pos = re\.sub\('<\[\^<\]\+?>', '', note\['fields'\]\.get\('품사', \{\}\)\.get\('value', ''\)\)\.lower\(\)\.strip\(\)
            pos_tags = \[p\.strip\(\) for p in re\.split\(r'\[,/\]', pos\) if p\.strip\(\)\]
            
            item = \{
                "id": note\['noteId'\],
                "word": word,
                "meaning": meaning,
                "pos": pos_tags
            \}
            
            if " " in word:
                item\['meaning_clean'\] = self\._clean_idiom_meaning\(meaning\)
                idiom_data\.append\(item\)
            else:
                normal_data\.append\(item\)

        final_clusters = \[\]

        if normal_data:
            msg = f"\\n📦 일반 단어 클러스터링 시작 \(\{len\(normal_data\)\}개\)"
            if self\.pbar: self\.pbar\.write\(msg\)
            else: print\(msg\)
            word_vectors = self\._get_vectors_for_data\(normal_data, "word"\)
            meaning_vectors = self\._get_vectors_for_data\(normal_data, "meaning"\)
            word_vectors = normalize\(word_vectors\) \* 0\.2
            meaning_vectors = normalize\(meaning_vectors\) \* 0\.8
            combined_vectors = np\.concatenate\(\[word_vectors, meaning_vectors\], axis=1\)
            labels = self\._run_clustering_pipeline\(combined_vectors\)
            final_clusters\.extend\(self\._post_process_labels\(normal_data, labels, combined_vectors\)\)

        if idiom_data:
            msg = f"\\n📦 이디엄 클러스터링 시작 \(\{len\(idiom_data\)\}개\)"
            if self\.pbar: self\.pbar\.write\(msg\)
            else: print\(msg\)
            meaning_vectors = self\._get_vectors_for_data\(idiom_data, "meaning_clean"\)
            combined_vectors = normalize\(meaning_vectors\)
            labels = self\._run_clustering_pipeline\(combined_vectors\)
            final_clusters\.extend\(self\._post_process_labels\(idiom_data, labels, combined_vectors\)\)

        return final_clusters"""

body_new = r"""        msg = f"🔍 Anki에서 '{MODEL_VOCAB}' 노트를 가져오는 중..."
        if self.pbar: self.pbar.write(msg)
        else: print(msg)
        
        note_ids = AnkiConnector.find_notes(query=f'"note:{MODEL_VOCAB}"')
        if not note_ids: return []
        notes_info = AnkiConnector.get_notes_info(note_ids)
        
        all_items = {}
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
            all_items[item['id']] = item
            
            if " " in word:
                item['meaning_clean'] = self._clean_idiom_meaning(meaning)
                idiom_data.append(item)
            else:
                normal_data.append(item)

        existing_clusters = self._load_clusters()

        if not full_recluster and existing_clusters:
            msg = f"⚡ 증분 클러스터링(Incremental Clustering) 실행 중..."
            if self.pbar: self.pbar.write(msg)
            else: print(msg)
            
            clustered_ids = set()
            for cluster in existing_clusters:
                for item in cluster:
                    clustered_ids.add(item['id'])
                    
            valid_clusters = []
            for cluster in existing_clusters:
                valid_cluster = [item for item in cluster if item['id'] in all_items]
                if valid_cluster:
                    valid_clusters.append(valid_cluster)
            
            existing_clusters = valid_clusters
            
            new_normal = [item for item in normal_data if item['id'] not in clustered_ids]
            new_idioms = [item for item in idiom_data if item['id'] not in clustered_ids]
            
            if not new_normal and not new_idioms:
                msg = f"✨ 새로 추가된 카드가 없습니다. 기존 클러스터를 유지합니다."
                if self.pbar: self.pbar.write(msg)
                else: print(msg)
                return [c for c in existing_clusters if len(c) >= 2]
            
            def get_combined_vector(item, is_idiom):
                if is_idiom:
                    v = self._get_vectors_for_data([item], "meaning_clean")[0]
                    v = v / (np.linalg.norm(v) or 1.0)
                    return v
                else:
                    wv = self._get_vectors_for_data([item], "word")[0]
                    wv = (wv / (np.linalg.norm(wv) or 1.0)) * 0.2
                    mv = self._get_vectors_for_data([item], "meaning")[0]
                    mv = (mv / (np.linalg.norm(mv) or 1.0)) * 0.8
                    return np.concatenate([wv, mv])

            def process_incremental(new_items, is_idiom):
                if not new_items: return
                relevant_clusters = []
                for c in existing_clusters:
                    has_space = " " in c[0]['word']
                    if is_idiom == has_space:
                        relevant_clusters.append(c)
                
                centroids = []
                for c in relevant_clusters:
                    vecs = [get_combined_vector(m, is_idiom) for m in c]
                    centroid = np.mean(vecs, axis=0)
                    centroid = centroid / (np.linalg.norm(centroid) or 1.0)
                    centroids.append(centroid)
                
                for item in new_items:
                    vec = get_combined_vector(item, is_idiom)
                    vec = vec / (np.linalg.norm(vec) or 1.0)
                    
                    best_sim = -1
                    best_idx = -1
                    
                    if centroids:
                        sims = np.dot(centroids, vec)
                        best_idx = np.argmax(sims)
                        best_sim = sims[best_idx]
                        
                    if best_sim > 0.85:
                        relevant_clusters[best_idx].append(item)
                        c_items = relevant_clusters[best_idx]
                        vecs = [get_combined_vector(m, is_idiom) for m in c_items]
                        new_centroid = np.mean(vecs, axis=0)
                        centroids[best_idx] = new_centroid / (np.linalg.norm(new_centroid) or 1.0)
                        msg = f"  -> '{item['word']}' 유의어 그룹 편입 (유사도: {best_sim:.2f})"
                        if self.pbar: self.pbar.write(msg)
                        else: print(msg)
                    else:
                        new_cluster = [item]
                        relevant_clusters.append(new_cluster)
                        centroids.append(vec)
                        existing_clusters.append(new_cluster)
            
            process_incremental(new_normal, is_idiom=False)
            process_incremental(new_idioms, is_idiom=True)
            
            self._save_clusters(existing_clusters)
            return [c for c in existing_clusters if len(c) >= 2]
            
        else:
            msg = f"🚀 전체 클러스터링(Full Re-clustering) 실행 중..."
            if self.pbar: self.pbar.write(msg)
            else: print(msg)

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

            self._save_clusters(final_clusters)
            return [c for c in final_clusters if len(c) >= 2]"""

content = re.sub(body_old, body_new, content)

# Change run_clustering function definition
content = re.sub(r'def run_clustering\(pbar=None, step_points=0\):', r'def run_clustering(pbar=None, step_points=0, full_recluster=False):', content)
content = re.sub(r'    raw_clusters = clusterer\.process_all_vocab\(\)', r'    raw_clusters = clusterer.process_all_vocab(full_recluster=full_recluster)', content)

with open('/Users/leejinwoo/Desktop/Projects/Anki Manager/utils/cluster.py', 'w', encoding='utf-8') as f:
    f.write(content)

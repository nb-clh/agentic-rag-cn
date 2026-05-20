import faiss
import numpy as np
import os


class VectorRetriever:
    def __init__(self, embedder, index_path=None):
        self.embedder = embedder
        self.index_path = index_path or os.getenv("FAISS_INDEX_PATH", "/app/data/faiss.index")
        self.index = None
        self.documents = []
        self._load_or_create()

    def _load_or_create(self):
        if os.path.exists(self.index_path):
            self.index = faiss.read_index(self.index_path)
        else:
            dim = 512  # bge-small-zh-v1.5 output dimension
            self.index = faiss.IndexFlatIP(dim)

    def add_documents(self, docs: list[str]):
        embeddings = self.embedder.encode(docs, normalize_embeddings=True)
        self.index.add(np.array(embeddings, dtype=np.float32))
        self.documents.extend(docs)
        faiss.write_index(self.index, self.index_path)

    def search(self, query: str, top_k: int = 10):
        if self.index is None or self.index.ntotal == 0:
            return []
        q_emb = self.embedder.encode([query], normalize_embeddings=True)
        scores, indices = self.index.search(np.array(q_emb, dtype=np.float32), min(top_k, self.index.ntotal))
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx >= 0 and idx < len(self.documents):
                results.append({"text": self.documents[idx], "score": float(score)})
        return results

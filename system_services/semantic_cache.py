import json
import hashlib
import numpy as np


class SemanticCache:
    """基于语义相似度的缓存，缓存 retrieval results 而非 LLM 答案"""

    def __init__(self, redis_client, embedder, threshold=0.88, ttl=3600):
        self.redis = redis_client
        self.embedder = embedder
        self.threshold = threshold
        self.ttl = ttl

    def _cache_key(self, query: str) -> str:
        return f"semantic_cache:{hashlib.md5(query.encode()).hexdigest()}"

    def get(self, query: str):
        """查找语义相似的缓存"""
        try:
            query_emb = self.embedder.encode([query], normalize_embeddings=True)[0]

            keys = self.redis.keys("semantic_cache:*")
            if not keys:
                return None

            best_match = None
            best_score = 0.0

            for key in keys:
                cached = self.redis.get(key)
                if not cached:
                    continue
                try:
                    data = json.loads(cached)
                    cached_emb = np.array(data["embedding"])
                    similarity = float(np.dot(query_emb, cached_emb))
                    if similarity > best_score:
                        best_score = similarity
                        best_match = data
                except (json.JSONDecodeError, KeyError):
                    continue

            if best_match and best_score >= self.threshold:
                return {
                    "chunks": best_match.get("chunks", []),
                    "similarity": best_score,
                    "original_query": best_match.get("query", ""),
                }
            return None
        except Exception:
            return None

    def set(self, query: str, chunks: list[dict]):
        """缓存 retrieval results（chunks）"""
        try:
            query_emb = self.embedder.encode([query], normalize_embeddings=True)[0]
            key = self._cache_key(query)

            data = {
                "query": query,
                "embedding": query_emb.tolist(),
                "chunks": chunks,
            }

            self.redis.setex(key, self.ttl, json.dumps(data, default=str))
        except Exception:
            pass

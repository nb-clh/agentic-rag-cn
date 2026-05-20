import numpy as np


class Evaluator:
    def __init__(self, embedder):
        self.embedder = embedder

    def score(self, query: str, context, answer: str) -> float:
        """语义相关性评分：answer 与 query+context 的相似度"""
        try:
            # 支持 list[dict]（chunks）和 list[str] 两种格式
            if context and isinstance(context[0], dict):
                texts = [c.get("text", "") for c in context[:3]]
            else:
                texts = context[:3] if context else []

            if not texts:
                ref = query
            else:
                ref = query + " " + " ".join(texts)

            ref_emb = self.embedder.encode([ref], normalize_embeddings=True)
            ans_emb = self.embedder.encode([answer], normalize_embeddings=True)
            similarity = float(np.dot(ref_emb[0], ans_emb[0]))
            return round(max(0.0, min(1.0, (similarity + 1) / 2)), 4)
        except Exception:
            return 0.0

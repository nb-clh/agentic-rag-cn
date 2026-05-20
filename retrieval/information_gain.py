import numpy as np


class InformationGainDetector:
    """检测新搜索结果是否包含新信息"""

    def __init__(self, embedder, threshold=0.92):
        self.embedder = embedder
        self.threshold = threshold

    def has_new_info(self, new_chunks: list[dict], existing_chunks: list[dict]) -> bool:
        """判断新 chunks 是否有新信息"""
        if not new_chunks:
            return False
        if not existing_chunks:
            return True

        existing_texts = [c.get("text", "") for c in existing_chunks if c.get("text")]
        if not existing_texts:
            return True

        existing_embs = self.embedder.encode(existing_texts, normalize_embeddings=True)

        new_texts = [c.get("text", "") for c in new_chunks if c.get("text")]
        if not new_texts:
            return False

        new_embs = self.embedder.encode(new_texts, normalize_embeddings=True)

        for new_emb in new_embs:
            similarities = np.dot(existing_embs, new_emb)
            max_sim = float(np.max(similarities))
            if max_sim < self.threshold:
                return True  # 有新信息

        return False  # 全部是重复信息

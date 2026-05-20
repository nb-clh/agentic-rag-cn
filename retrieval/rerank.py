import gc
import torch
from sentence_transformers import CrossEncoder


class Reranker:
    def __init__(self, model_name="BAAI/bge-reranker-v2-m3"):
        self.model = CrossEncoder(model_name)

    def rerank(self, query: str, chunks: list, top_k: int = 10) -> list[dict]:
        """对 chunks 进行 rerank，返回带 score 的 chunks"""
        if not chunks:
            return []

        # 提取文本用于 rerank
        texts = []
        for c in chunks:
            if isinstance(c, dict):
                texts.append(c.get("text", ""))
            else:
                texts.append(str(c))

        pairs = [(query, t) for t in texts]

        # 分批处理，每批最多 5 个文档，减少峰值内存
        batch_size = 5
        all_scores = []
        with torch.no_grad():
            for i in range(0, len(pairs), batch_size):
                batch = pairs[i:i + batch_size]
                scores = self.model.predict(batch)
                all_scores.extend(scores)
                gc.collect()

        # 将 score 写入 chunk
        scored_chunks = []
        for chunk, score in zip(chunks, all_scores):
            if isinstance(chunk, dict):
                chunk["score"] = float(score)
            else:
                chunk = {"text": str(chunk), "score": float(score)}
            scored_chunks.append(chunk)

        # 按 score 降序排列
        scored_chunks.sort(key=lambda x: x["score"], reverse=True)
        return scored_chunks[:top_k]

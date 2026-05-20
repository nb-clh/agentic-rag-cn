class BudgetController:
    def __init__(self, max_tokens: int = 8000, max_chunks: int = 8, max_sources: int = 5):
        self.max_tokens = max_tokens
        self.max_chunks = max_chunks
        self.max_sources = max_sources

    def select_chunks(self, ranked_chunks: list[dict]) -> list[dict]:
        """按 rerank score 从高到低选择 chunks，直到预算用完"""
        if not ranked_chunks:
            return []

        # 按 score 降序排列（如果还没排的话）
        sorted_chunks = sorted(
            ranked_chunks,
            key=lambda x: x.get("score", 0),
            reverse=True
        )

        selected = []
        total_tokens = 0
        sources_used = set()

        for chunk in sorted_chunks:
            chunk_tokens = chunk.get("token_count", 0)
            source = chunk.get("source", "unknown")

            # 检查 token 预算
            if total_tokens + chunk_tokens > self.max_tokens:
                continue

            # 检查 chunk 数量
            if len(selected) >= self.max_chunks:
                break

            # 检查来源数量（超过限制的来源不再加新 chunk）
            if len(sources_used) >= self.max_sources and source not in sources_used:
                continue

            selected.append(chunk)
            total_tokens += chunk_tokens
            sources_used.add(source)

        return selected

    def get_context_text(self, selected_chunks: list[dict]) -> str:
        """将选中的 chunks 拼接成 LLM 上下文"""
        parts = []
        for i, chunk in enumerate(selected_chunks):
            source = chunk.get("source", "未知来源")
            text = chunk.get("text", "")
            parts.append(f"[来源 {i+1}: {source}]\n{text}")
        return "\n\n---\n\n".join(parts)

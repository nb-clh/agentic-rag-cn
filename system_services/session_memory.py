"""Session Memory — 会话记忆，同一会话里记住搜过什么，避免重复搜索"""

import json
import time
from typing import Optional


class SessionMemory:
    """会话级别的搜索记忆，基于 Redis 存储

    不使用 embedder，用 Jaccard 相似度做去重判断。
    """

    KEY_PREFIX = "session_memory:"

    def __init__(self, redis_client, session_id: str, ttl: int = 3600):
        """
        Args:
            redis_client: Redis 客户端实例
            session_id: 会话 ID（可以是 query hash 或用户传入）
            ttl: 记忆过期时间（秒），默认 1 小时
        """
        self.redis = redis_client
        self.session_id = session_id
        self.ttl = ttl
        self._key = f"{self.KEY_PREFIX}{session_id}"

    def add_search(self, query: str, results_count: int):
        """记录一次搜索"""
        entry = {
            "query": query,
            "results_count": results_count,
            "timestamp": time.time(),
        }
        # 用 Redis list 存储，RPUSH 追加
        self.redis.rpush(self._key, json.dumps(entry, ensure_ascii=False))
        self.redis.expire(self._key, self.ttl)

    def has_been_searched(self, query: str, similarity_threshold: float = 0.85) -> bool:
        """检查是否已经搜过相似查询

        1. 精确匹配
        2. Jaccard 相似度（词级别的交集/并集）
        """
        history = self._get_raw_history()
        if not history:
            return False

        query_lower = query.strip().lower()
        query_tokens = set(query_lower.split())

        for entry in history:
            existing = entry.get("query", "").strip().lower()

            # 精确匹配
            if existing == query_lower:
                return True

            # Jaccard 相似度
            existing_tokens = set(existing.split())
            if not query_tokens or not existing_tokens:
                continue

            intersection = query_tokens & existing_tokens
            union = query_tokens | existing_tokens
            similarity = len(intersection) / len(union) if union else 0.0

            if similarity >= similarity_threshold:
                return True

        return False

    def get_search_history(self) -> list[dict]:
        """获取搜索历史"""
        return self._get_raw_history()

    def get_context_summary(self) -> str:
        """生成搜索历史摘要，用于 LLM 上下文

        返回格式："已搜索：xxx, yyy, zzz"
        """
        history = self._get_raw_history()
        if not history:
            return ""

        queries = [entry.get("query", "") for entry in history if entry.get("query")]
        if not queries:
            return ""

        return "已搜索：" + ", ".join(queries)

    def _get_raw_history(self) -> list[dict]:
        """从 Redis 获取原始历史记录"""
        raw_list = self.redis.lrange(self._key, 0, -1)
        if not raw_list:
            return []

        result = []
        for raw in raw_list:
            try:
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8")
                result.append(json.loads(raw))
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
        return result

import json
import time


class FeedbackLogger:
    """系统反馈日志 — 记录每次搜索的效果，用于数据驱动优化"""

    def __init__(self, redis_client, ttl: int = 604800):  # 7 天
        self.redis = redis_client
        self.ttl = ttl

    def log_query(self, trace_data: dict):
        """记录一次查询的反馈数据"""
        # 从 trace 中提取关键指标
        events = trace_data.get("events", [])
        events_dict = {}
        for ev in events:
            step = ev.get("step", "")
            data = ev.get("data", "")
            events_dict[step] = data

        feedback = {
            "timestamp": time.time(),
            "query": trace_data.get("query", ""),
            "intent": events_dict.get("intent", "unknown"),
            # 耗时
            "total_ms": round(trace_data.get("latency", 0) * 1000, 1),
            # 搜索效果
            "web_results": self._safe_int(events_dict.get("web_results", 0)),
            "vector_results": self._safe_int(events_dict.get("vector_results", 0)),
            "chunks_count": self._safe_int(events_dict.get("chunks_count", 0)),
            "reranked_count": self._safe_int(events_dict.get("reranked_count", 0)),
            "budget_chunks": self._safe_int(events_dict.get("budget_chunks", 0)),
            "budget_tokens": self._safe_int(events_dict.get("budget_tokens", 0)),
            # 缓存命中
            "cache_hit": events_dict.get("cache_hit") == "True",
            "semantic_cache_hit": events_dict.get("semantic_cache_hit") == "True",
            # 信息增益
            "info_gain_early_stop": events_dict.get("early_stop", None),
            # 质量
            "evaluation_score": self._safe_float(events_dict.get("evaluation", 0)),
            "evidence_count": self._safe_int(events_dict.get("evidence_count", 0)),
            "contradictions": self._safe_int(events_dict.get("contradictions", 0)),
            # LLM
            "llm_output_len": self._safe_int(events_dict.get("llm_done", 0)),
        }

        # 存入 Redis list
        key = "feedback_log"
        self.redis.rpush(key, json.dumps(feedback, ensure_ascii=False))
        self.redis.expire(key, self.ttl)

    def get_stats(self, last_n: int = 100) -> dict:
        """获取最近 N 次查询的统计"""
        key = "feedback_log"
        entries = self.redis.lrange(key, -last_n, -1)
        if not entries:
            return {"total": 0}

        data = [json.loads(e) for e in entries]

        # 统计
        total = len(data)
        avg_ms = sum(d.get("total_ms", 0) for d in data) / total
        cache_hits = sum(1 for d in data if d.get("cache_hit") or d.get("semantic_cache_hit"))
        avg_score = sum(d.get("evaluation_score", 0) for d in data) / total
        avg_chunks = sum(d.get("budget_chunks", 0) for d in data) / total

        # 按意图分组
        intent_counts = {}
        for d in data:
            intent = d.get("intent", "unknown")
            intent_counts[intent] = intent_counts.get(intent, 0) + 1

        return {
            "total": total,
            "avg_ms": round(avg_ms, 1),
            "cache_hit_rate": round(cache_hits / total * 100, 1),
            "avg_score": round(avg_score, 3),
            "avg_chunks": round(avg_chunks, 1),
            "intent_distribution": intent_counts,
        }

    @staticmethod
    def _safe_int(val) -> int:
        try:
            return int(val)
        except (ValueError, TypeError):
            return 0

    @staticmethod
    def _safe_float(val) -> float:
        try:
            return float(val)
        except (ValueError, TypeError):
            return 0.0

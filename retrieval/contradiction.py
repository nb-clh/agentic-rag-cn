from openai import AsyncOpenAI
import json


class ContradictionDetector:
    """矛盾检测器 — 检查多源信息是否矛盾"""

    def __init__(self, client: AsyncOpenAI, model: str = "mimo-v2.5-pro"):
        self.client = client
        self.model = model

    async def detect(self, chunks: list[dict]) -> list[dict]:
        """
        检查 chunks 之间是否有矛盾。

        输入：chunks 列表，每个有 text、source、rerank_score 字段

        输出：矛盾列表，每个 dict 包含：
        - topic: 矛盾主题
        - source_a: 来源A的信息
        - source_b: 来源B的信息
        - severity: high/medium/low
        """
        if not chunks or len(chunks) < 2:
            return []

        # 取 top 5 chunks（rerank_score 最高的 5 个）
        top_chunks = sorted(
            chunks, key=lambda c: c.get("rerank_score", 0), reverse=True
        )[:5]

        # 格式化 chunks 文本
        chunks_text_parts = []
        for i, c in enumerate(top_chunks, 1):
            source = c.get("source", f"来源{i}")
            text = c.get("text", "")[:500]  # 限制长度避免 prompt 过长
            chunks_text_parts.append(f"[来源{i}: {source}]\n{text}")
        chunks_text = "\n\n".join(chunks_text_parts)

        prompt = f"""检查以下信息片段是否有矛盾或冲突。只报告明确的矛盾，忽略补充性信息。

信息片段：
{chunks_text}

输出 JSON 数组，每个元素：
{{"topic": "矛盾主题", "source_a": "来源A的说法", "source_b": "来源B的说法", "severity": "high/medium/low"}}

如果没有矛盾，返回空数组 []
直接返回 JSON 数组，不要解释。"""

        try:
            resp = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )
            content = resp.choices[0].message.content
            if "[" in content:
                start = content.index("[")
                end = content.rindex("]") + 1
                result = json.loads(content[start:end])
                if isinstance(result, list):
                    # 验证每个元素的结构
                    validated = []
                    for item in result:
                        if isinstance(item, dict) and "topic" in item:
                            validated.append({
                                "topic": str(item.get("topic", "")),
                                "source_a": str(item.get("source_a", "")),
                                "source_b": str(item.get("source_b", "")),
                                "severity": str(item.get("severity", "medium")),
                            })
                    return validated
            return []
        except Exception:
            return []

    def format_contradictions(self, contradictions: list[dict]) -> str:
        """格式化矛盾报告"""
        if not contradictions:
            return ""

        lines = ["---", "⚠️ 信息矛盾"]
        for i, item in enumerate(contradictions, 1):
            severity = item.get("severity", "medium")
            topic = item.get("topic", "")
            source_a = item.get("source_a", "")
            source_b = item.get("source_b", "")
            lines.append(f"{i}. [{severity}] {topic}：A说{source_a}，B说{source_b}")
        return "\n".join(lines)

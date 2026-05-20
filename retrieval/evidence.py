from openai import AsyncOpenAI
import json


class EvidenceExtractor:
    """证据提取器 — 从 LLM 答案中提取结构化证据表"""

    def __init__(self, client: AsyncOpenAI, model: str = "mimo-v2.5-pro"):
        self.client = client
        self.model = model

    async def extract(self, query: str, answer: str, sources: list[dict]) -> list[dict]:
        """
        从答案中提取证据表。

        输入：
        - query: 原始问题
        - answer: LLM 生成的答案
        - sources: 来源列表，每个 dict 有 url、source、text 字段

        输出：证据列表，每个 dict 包含：
        - claim: 具体论点（一句话）
        - evidence: 支撑证据（原文摘要）
        - source_url: 来源 URL（如果能匹配到）
        - confidence: 置信度（high/medium/low）
        """
        sources_json = json.dumps(sources, ensure_ascii=False, indent=2)

        prompt = f"""从以下答案中提取关键论点及其证据来源。

问题：{query}
答案：{answer}
参考来源：{sources_json}

输出 JSON 数组，每个元素：
{{"claim": "论点", "evidence": "证据摘要", "source_url": "来源URL或unknown", "confidence": "high/medium/low"}}

如果答案中没有明确论点，返回空数组 []
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
                        if isinstance(item, dict) and "claim" in item:
                            validated.append({
                                "claim": str(item.get("claim", "")),
                                "evidence": str(item.get("evidence", "")),
                                "source_url": str(item.get("source_url", "unknown")),
                                "confidence": str(item.get("confidence", "medium")),
                            })
                    return validated
            return []
        except Exception:
            return []

    def format_table(self, evidence_list: list[dict]) -> str:
        """把证据表格式化成可读文本，追加到答案后面"""
        if not evidence_list:
            return ""

        lines = ["---", "📋 证据表"]
        for i, item in enumerate(evidence_list, 1):
            confidence = item.get("confidence", "medium")
            claim = item.get("claim", "")
            evidence = item.get("evidence", "")
            source_url = item.get("source_url", "unknown")
            if source_url and source_url != "unknown":
                lines.append(f"{i}. [{confidence}] {claim} → {evidence}（来源：{source_url}）")
            else:
                lines.append(f"{i}. [{confidence}] {claim} → {evidence}")
        return "\n".join(lines)

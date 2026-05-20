from openai import AsyncOpenAI
import json

VALID_INTENTS = {"factual", "comparison", "howto", "opinion", "general"}


class QueryDecomposer:
    """查询拆解器 — 把复杂问题拆成独立子问题，同时判断意图"""

    def __init__(self, client: AsyncOpenAI, model: str = "mimo-v2.5-pro"):
        self.client = client
        self.model = model

    async def decompose(self, query: str, max_sub: int = 4) -> dict:
        """
        拆解查询。返回 dict，包含意图和子问题列表。

        返回格式：
        {
            "intent": "comparison" | "factual" | "howto" | "opinion" | "general",
            "sub_queries": ["子问题1", "子问题2", ...]
        }

        规则：
        1. 简单问题不拆（返回原问题）
        2. 复杂问题拆成 2-4 个子问题
        3. 子问题应该独立可搜索
        4. 用 LLM 拆解（prompt 要求输出 JSON）
        """
        prompt = f"""你是一个查询分析器。做两件事：
1. 判断问题的意图类型：
   - factual：事实查询（什么是、是多少）
   - comparison：对比分析（A和B哪个好、对比）
   - howto：操作指南（怎么安装、如何配置）
   - opinion：观点讨论（你觉得、评价、推荐）
   - general：其他

2. 如果是复杂问题，拆成 2-{max_sub} 个独立子问题。简单问题不拆。

问题：{query}

输出 JSON：
{{"intent": "类型", "sub_queries": ["子问题1", "子问题2"]}}
如果是简单查询：{{"intent": "类型", "sub_queries": ["原问题"]}}

直接返回JSON，不要解释。"""

        fallback = {"intent": "general", "sub_queries": [query]}

        try:
            resp = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )
            content = resp.choices[0].message.content

            # 提取 JSON
            if "{" in content:
                start = content.index("{")
                end = content.rindex("}") + 1
                parsed = json.loads(content[start:end])

                if isinstance(parsed, dict):
                    intent = parsed.get("intent", "general")
                    sub_queries = parsed.get("sub_queries", [query])

                    # 验证 intent
                    if intent not in VALID_INTENTS:
                        intent = "general"

                    # 验证 sub_queries
                    if isinstance(sub_queries, list) and all(isinstance(q, str) for q in sub_queries):
                        # 去重，保持顺序
                        seen = set()
                        result = []
                        for q in sub_queries:
                            q = q.strip()
                            if q and q not in seen:
                                seen.add(q)
                                result.append(q)
                        if len(result) > 1:
                            return {"intent": intent, "sub_queries": result[:max_sub]}
                        else:
                            return {"intent": intent, "sub_queries": [query]}

            return fallback
        except Exception:
            return fallback

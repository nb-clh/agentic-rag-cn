from openai import AsyncOpenAI
import json


class QueryRewriter:
    def __init__(self, client: AsyncOpenAI, model: str = "mimo-v2.5-pro"):
        self.client = client
        self.model = model

    async def rewrite(self, query: str) -> list[str]:
        prompt = f"""你是一个搜索查询优化器。用户的问题是："{query}"

请生成 3-5 个搜索查询（不要超过 5 个）：
1. 简化版查询（去掉冗余词）
2. 扩展查询（同义替换、不同角度）
3. 意图分离查询（怎么做/为什么/教程/对比/最新）

直接返回JSON数组，不要解释。格式：["query1", "query2", ...]"""

        try:
            resp = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )
            content = resp.choices[0].message.content
            if "[" in content:
                start = content.index("[")
                end = content.rindex("]") + 1
                return json.loads(content[start:end])
            return [query]
        except:
            return [query]

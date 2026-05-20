from openai import AsyncOpenAI
import os


class LLM:
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=os.getenv("OPENAI_API_KEY", ""),
            base_url=os.getenv("OPENAI_BASE_URL", "https://token-plan-cn.xiaomimimo.com/v1")
        )
        self.model = os.getenv("LLM_MODEL", "mimo-v2.5-pro")

    async def generate(self, query: str, context: list[str]) -> str:
        # 如果 context 只有一个元素（budget 已经拼接好），直接用
        if len(context) == 1:
            context_text = context[0]
        else:
            context_text = "\n\n".join(context) if context else "无相关上下文"

        # 限制上下文最大长度（安全网）
        max_chars = 30000  # 约 8000 token
        if len(context_text) > max_chars:
            context_text = context_text[:max_chars] + "\n\n[上下文已截断]"

        prompt = f"""基于以下搜索结果回答用户问题。如果搜索结果不足以回答，请说明。

搜索结果：
{context_text}

用户问题：{query}

请给出准确、简洁的回答："""

        try:
            resp = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=2000
            )
            return resp.choices[0].message.content
        except Exception as e:
            return f"LLM 调用失败: {str(e)}"

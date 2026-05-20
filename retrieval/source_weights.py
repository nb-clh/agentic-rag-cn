"""Source Weights — 来源权重，不同来源可信度不同"""

from urllib.parse import urlparse


class SourceWeights:
    """根据 URL / 来源给不同权重，用于 rerank 排序时加权"""

    WEIGHTS = {
        "github.com": 0.95,
        "docs.github.com": 0.95,
        "mp.weixin.qq.com": 0.70,  # 微信公众号
        "official": 0.90,  # 官方文档
        "v2ex.com": 0.85,
        "zhihu.com": 0.80,
        "bilibili.com": 0.75,
        "default": 0.50,
        "seo_spam": 0.20,  # SEO 垃圾站
    }

    SEO_SPAM_DOMAINS = [
        "wenda.so.com",
        "zhidao.baidu.com",
        "wenku.baidu.com",
        "blog.csdn.net",  # CSDN 大量 SEO 垃圾
    ]

    def get_weighted_domains(self, intent: str) -> dict:
        """根据意图返回域名权重调整

        不同意图下，不同来源的可信度不同：
        - howto：加权官方文档
        - comparison：加权论坛和社区
        - opinion：加权社区
        - factual：加权官方和文档
        - general：不调整
        """
        base = dict(self.WEIGHTS)
        if intent == "howto":
            base["official"] = 0.95
            base["docs.github.com"] = 0.98
        elif intent == "comparison":
            base["v2ex.com"] = 0.90
            base["zhihu.com"] = 0.85
            base["bilibili.com"] = 0.80
        elif intent == "opinion":
            base["v2ex.com"] = 0.90
            base["zhihu.com"] = 0.90
            base["bilibili.com"] = 0.85
        elif intent == "factual":
            base["official"] = 0.95
            base["github.com"] = 0.95
        return base

    def get_weight(self, url: str, weights: dict = None) -> float:
        """根据 URL 返回权重

        1. 检查是否 SEO 垃圾站 → 0.20
        2. 匹配域名 → 对应权重
        3. 无法匹配 → 0.50
        """
        if weights is None:
            weights = self.WEIGHTS

        if not url:
            return weights["default"]

        try:
            parsed = urlparse(url if "://" in url else f"https://{url}")
            hostname = (parsed.hostname or "").lower()
        except Exception:
            return weights["default"]

        # 1. SEO 垃圾站检查
        for spam_domain in self.SEO_SPAM_DOMAINS:
            if hostname == spam_domain or hostname.endswith(f".{spam_domain}"):
                return weights["seo_spam"]

        # 2. 精确域名匹配
        if hostname in weights:
            return weights[hostname]

        # 3. 子域名匹配（如 xxx.github.com → github.com）
        for domain, weight in weights.items():
            if domain in ("default", "seo_spam", "official"):
                continue
            if hostname.endswith(f".{domain}"):
                return weight

        return weights["default"]

    def apply_weights(self, chunks: list[dict], intent: str = "general") -> list[dict]:
        """给 chunks 加上 source_weight 字段，根据意图调整权重

        优先级：
        1. 有 url 字段 → 用 URL 匹配
        2. source 字段是 "local" → 默认权重
        3. source 字段包含域名 → 尝试匹配
        4. 兜底 → 默认权重
        """
        weights = self.get_weighted_domains(intent)

        for chunk in chunks:
            url = chunk.get("url", "")
            source = chunk.get("source", "")

            if url:
                weight = self.get_weight(url, weights)
            elif source == "local":
                weight = weights["default"]
            elif source and "." in source:
                # source 字段可能是域名
                weight = self.get_weight(source, weights)
            else:
                weight = weights["default"]

            chunk["source_weight"] = weight

        return chunks

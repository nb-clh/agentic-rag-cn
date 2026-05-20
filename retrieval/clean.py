from bs4 import BeautifulSoup
import re


class ContentCleaner:
    def clean_html(self, html_docs: list[str]) -> list[str]:
        cleaned = []
        for html in html_docs:
            soup = BeautifulSoup(html, "html.parser")
            for tag in soup(["script", "style", "noscript", "nav", "footer", "header"]):
                tag.decompose()
            text = soup.get_text(separator=" ")
            text = re.sub(r"\s+", " ", text).strip()
            text = re.sub(r"cookie|subscribe|登录|注册|广告|关注我们", "", text, flags=re.I)
            if len(text) < 50:
                continue
            cleaned.append(text)
        return cleaned

    def clean_docs(self, docs: list[dict]) -> list[str]:
        cleaned = []
        for doc in docs:
            if isinstance(doc, dict):
                text = doc.get("content", "") or doc.get("text", "")
            else:
                text = str(doc)
            text = re.sub(r"\s+", " ", text).strip()
            if len(text) > 20:
                cleaned.append(text)
        return cleaned

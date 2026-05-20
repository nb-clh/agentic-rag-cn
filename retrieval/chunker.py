import tiktoken
import hashlib


class Chunker:
    def __init__(self, chunk_size: int = 400, overlap: int = 50):
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.enc = tiktoken.get_encoding("cl100k_base")

    def split(self, text: str, source: str = "") -> list[dict]:
        """将文本按 token 分块"""
        if not text or not text.strip():
            return []

        tokens = self.enc.encode(text)
        chunks = []
        start = 0

        while start < len(tokens):
            end = min(start + self.chunk_size, len(tokens))
            chunk_tokens = tokens[start:end]
            chunk_text = self.enc.decode(chunk_tokens)

            chunk_id = hashlib.md5(
                f"{source}:{start}:{end}".encode()
            ).hexdigest()[:12]

            chunks.append({
                "chunk_id": chunk_id,
                "text": chunk_text,
                "source": source,
                "token_count": len(chunk_tokens),
                "start": start,
                "end": end,
            })

            # 下一块从 overlap 位置开始
            start = end - self.overlap if end < len(tokens) else end

        return chunks

    def split_docs(self, docs: list[dict]) -> list[dict]:
        """批量分块，docs 是 [{text, source, ...}] 格式"""
        all_chunks = []
        for doc in docs:
            text = doc.get("text", "") or doc.get("content", "")
            source = doc.get("source", "") or doc.get("url", "")
            chunks = self.split(text, source)
            # 保留原始文档的其他字段
            for chunk in chunks:
                chunk["original_doc"] = {k: v for k, v in doc.items()
                                         if k not in ("text", "content")}
            all_chunks.extend(chunks)
        return all_chunks

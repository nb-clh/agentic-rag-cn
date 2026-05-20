import asyncio
import gc
import torch
from cache.redis_cache import RedisCache
from retrieval.web import WebRetriever
from retrieval.vector import VectorRetriever
from retrieval.rerank import Reranker
from retrieval.rewrite import QueryRewriter
from retrieval.decompose import QueryDecomposer
from retrieval.multi_source import MultiSourceSearch
from retrieval.clean import ContentCleaner
from retrieval.chunker import Chunker
from retrieval.budget import BudgetController
from observability.trace_store import TraceStore
from observability.evaluator import Evaluator
from system_services.semantic_cache import SemanticCache
from system_services.feedback_logger import FeedbackLogger
from retrieval.source_weights import SourceWeights
from retrieval.information_gain import InformationGainDetector
from retrieval.evidence import EvidenceExtractor
from retrieval.contradiction import ContradictionDetector
from core.llm import LLM
from core.trace import Trace

# 限制文档数量，防止内存爆炸
MAX_WEB_DOCS = 15
MAX_CONCURRENT_SEARCHES = 3


class Orchestrator:
    def __init__(self, redis_client):
        self.cache = RedisCache(redis_client)
        self.web = WebRetriever()
        self.multi_source = MultiSourceSearch()
        self.cleaner = ContentCleaner()
        self.llm = LLM()
        self.rewriter = QueryRewriter(self.llm.client, self.llm.model)
        self._decomposer = None  # 延迟初始化（用 LLM client，不需要 ML 模型）
        self.trace_store = TraceStore(redis_client)
        self.redis_client = redis_client
        # Chunker 和 BudgetController 不需要 ML 模型，直接初始化
        self._chunker = Chunker(chunk_size=400, overlap=50)
        self._budget = BudgetController(max_tokens=8000, max_chunks=8, max_sources=5)
        # 模型按需加载，用完即卸载，避免 OOM
        self._embedder = None
        self._vector = None
        self._reranker = None
        self._evidence_extractor = None
        self._contradiction_detector = None
        self._source_weights = SourceWeights()
        self._feedback_logger = FeedbackLogger(redis_client)
        self._models_lock = asyncio.Lock()

    async def _load_embedder(self):
        """加载 embedder 模型（bge-small-zh，~90MB），用于向量搜索/语义缓存/评估"""
        if self._embedder is not None:
            return
        async with self._models_lock:
            if self._embedder is not None:
                return
            import os
            os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
            from sentence_transformers import SentenceTransformer
            # 使用小型中文模型，大幅降低内存（~90MB vs bge-m3的~5GB）
            self._embedder = await asyncio.to_thread(
                SentenceTransformer, "BAAI/bge-small-zh-v1.5"
            )

    async def _unload_embedder(self):
        """卸载 embedder 模型，释放内存"""
        if self._embedder is None:
            return
        del self._embedder
        self._embedder = None
        self._vector = None
        gc.collect()
        try:
            torch.cuda.empty_cache()
        except Exception:
            pass
        # 强制 glibc 释放内存回 OS
        try:
            import ctypes
            ctypes.CDLL("libc.so.6").malloc_trim(0)
        except Exception:
            pass

    async def _load_reranker(self):
        """加载 reranker 模型（bge-reranker-v2-m3），用于重排序"""
        if self._reranker is not None:
            return
        async with self._models_lock:
            if self._reranker is not None:
                return
            import os
            os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
            self._reranker = await asyncio.to_thread(Reranker)

    async def _unload_reranker(self):
        """卸载 reranker 模型，释放内存"""
        if self._reranker is None:
            return
        del self._reranker
        self._reranker = None
        gc.collect()
        try:
            torch.cuda.empty_cache()
        except Exception:
            pass
        # 强制 glibc 释放内存回 OS
        try:
            import ctypes
            ctypes.CDLL("libc.so.6").malloc_trim(0)
        except Exception:
            pass

    async def run(self, query: str, trace: Trace = None):
        import time as _time
        import sys
        _step_times = []
        def _tick(label):
            t = _time.time()
            _step_times.append((label, t))
            elapsed = t - _step_times[0][1] if _step_times else 0
            print(f"[TICK] {label}: +{elapsed:.1f}s from start", flush=True)

        _tick("start")
        if trace is None:
            trace = Trace(query=query)

        # 1. CACHE
        cached = await asyncio.to_thread(self.cache.get, query)
        _tick("cache_check")
        if cached:
            trace.log("cache_hit", True)
            result = trace.finalize(cached, score=1.0)
            await asyncio.to_thread(self.trace_store.save, result)
            return result
        trace.log("cache_hit", False)

        # 2. QUERY REWRITE（用 LLM client，不需要 ML 模型）
        queries = await self.rewriter.rewrite(query)
        queries = queries[:5]
        trace.log("rewrite", queries)
        _tick("rewrite")

        # 2.1 QUERY DECOMPOSE（用 LLM client，不需要 ML 模型）
        if not self._decomposer:
            self._decomposer = QueryDecomposer(self.llm.client, self.llm.model)
        decompose_result = await self._decomposer.decompose(query)
        sub_queries = decompose_result.get("sub_queries", [query])
        intent = decompose_result.get("intent", "general")
        trace.log("decompose", decompose_result)
        trace.log("intent", intent)
        _tick("decompose")

        # 合并 rewrite + decompose 结果，去重，限制总数 ≤ 6
        seen = set()
        merged = []
        for q in queries + sub_queries:
            q = q.strip()
            if q and q not in seen:
                seen.add(q)
                merged.append(q)
        queries = merged[:6]
        trace.log("merged_queries", queries)
        _tick("merge")

        # ═══════════════════════════════════════════════════════════
        # Phase 1: EMBEDDER — 语义缓存 + 向量搜索 + 信息增益 + 评估
        # 加载 embedder，完成所有需要它的操作后卸载
        # ═══════════════════════════════════════════════════════════
        await self._load_embedder()
        _tick("embedder_load")

        # 临时创建需要 embedder 的组件
        _vector = VectorRetriever(self._embedder)
        _semantic_cache = SemanticCache(self.redis_client, self._embedder)
        _info_gain = InformationGainDetector(self._embedder)
        _evaluator = Evaluator(self._embedder)

        # 2.5 SEMANTIC CACHE CHECK
        cached_result = await asyncio.to_thread(_semantic_cache.get, query)
        _tick("semantic_cache_check")
        if cached_result:
            trace.log("semantic_cache_hit", True)
            trace.log("cache_similarity", cached_result["similarity"])
            selected_chunks = cached_result["chunks"]
            context_text = self._budget.get_context_text(selected_chunks)
            # 评估（在 embedder 卸载前）
            # 先生成答案，再评估
            await self._unload_embedder()
            answer = await self.llm.generate(query, [context_text])
            trace.log("llm_done", len(answer))
            # EVIDENCE + CONTRADICTION（用 LLM client）
            if not self._evidence_extractor:
                self._evidence_extractor = EvidenceExtractor(self.llm.client, self.llm.model)
                self._contradiction_detector = ContradictionDetector(self.llm.client, self.llm.model)
            contradictions = await self._contradiction_detector.detect(selected_chunks[:5])
            trace.log("contradictions", len(contradictions))
            sources = [{"url": c.get("url", ""), "source": c.get("source", ""), "text": c.get("text", "")[:200]} for c in selected_chunks]
            evidence_list = await self._evidence_extractor.extract(query, answer, sources)
            trace.log("evidence_count", len(evidence_list))
            if evidence_list:
                answer += "\n\n" + self._evidence_extractor.format_table(evidence_list)
            if contradictions:
                answer += "\n\n" + self._contradiction_detector.format_contradictions(contradictions)
            # 重新加载 embedder 做评估
            await self._load_embedder()
            _evaluator2 = Evaluator(self._embedder)
            score = _evaluator2.score(query, selected_chunks, answer)
            trace.log("evaluation", score)
            await self._unload_embedder()
            del selected_chunks, context_text
            gc.collect()
            await asyncio.to_thread(self.cache.set, query, answer)
            self._feedback_logger.log_query(trace.finalize(answer, score=score))
            trace.log("feedback_logged", True)
            result = trace.finalize(answer, score=score)
            await asyncio.to_thread(self.trace_store.save, result)
            return result
        trace.log("semantic_cache_hit", False)

        # 3. WEB SEARCH + 信息增益检查（信息增益需要 embedder）
        _tick("web_search_start")
        sem = asyncio.Semaphore(MAX_CONCURRENT_SEARCHES)

        async def limited_search(coro):
            async with sem:
                return await coro

        web_docs = []
        multi_docs = []
        seen_urls = set()
        existing_chunks_for_gain = []

        for i, q in enumerate(queries):
            tasks = [
                limited_search(self.web.search(q)),
                limited_search(self.multi_source.search_all(q)),
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            new_web = []
            new_multi = []
            for j, result in enumerate(results):
                if isinstance(result, list):
                    for doc in result:
                        if isinstance(doc, dict):
                            url = doc.get("url", doc.get("title", ""))
                            if url and url not in seen_urls:
                                seen_urls.add(url)
                                if j == 0:
                                    new_web.append(doc)
                                else:
                                    new_multi.append(doc)

            web_docs.extend(new_web[:MAX_WEB_DOCS - len(web_docs)])
            multi_docs.extend(new_multi[:MAX_WEB_DOCS - len(multi_docs)])

            # 信息增益检查（需要 embedder）
            if i > 0 and existing_chunks_for_gain:
                new_chunks = []
                for doc in new_web + new_multi:
                    text = doc.get("text", doc.get("content", ""))
                    if text:
                        new_chunks.append({"text": text, "source": "web"})
                if new_chunks:
                    has_new = await asyncio.to_thread(
                        _info_gain.has_new_info, new_chunks, existing_chunks_for_gain
                    )
                    trace.log(f"info_gain_q{i}", has_new)
                    if not has_new:
                        trace.log("early_stop", f"no new info at query {i+1}")
                        break

            for doc in new_web + new_multi:
                text = doc.get("text", doc.get("content", ""))
                if text:
                    existing_chunks_for_gain.append({"text": text, "source": "web"})

            if len(web_docs) >= MAX_WEB_DOCS and len(multi_docs) >= MAX_WEB_DOCS:
                break

        _tick("web_search_done")

        # 4. VECTOR SEARCH（需要 embedder）
        vec_docs = await asyncio.to_thread(_vector.search, query)
        _tick("vector_search")

        trace.log("web_results", len(web_docs))
        trace.log("multi_results", len(multi_docs))
        trace.log("vector_results", len(vec_docs))

        # ═══════════════════════════════════════════════════════════
        # 卸载 embedder，释放内存给 reranker
        # ═══════════════════════════════════════════════════════════
        del _vector, _semantic_cache, _info_gain, _evaluator
        await self._unload_embedder()
        _tick("embedder_unload")

        # 5. MERGE + CLEAN
        all_docs = web_docs + multi_docs
        clean_texts = self.cleaner.clean_docs(all_docs)
        vec_texts = [d.get("text", "") for d in vec_docs if isinstance(d, dict)]

        docs_for_chunking = []
        for t in clean_texts:
            docs_for_chunking.append({"text": t, "source": "web"})
        for t in vec_texts:
            docs_for_chunking.append({"text": t, "source": "local"})

        del all_docs, clean_texts, web_docs, multi_docs, existing_chunks_for_gain
        del new_web, new_multi, results, vec_docs, vec_texts
        gc.collect()
        _tick("clean")

        # 6. CHUNKING
        chunks = self._chunker.split_docs(docs_for_chunking)
        trace.log("chunks_count", len(chunks))
        _tick("chunking")

        # ═══════════════════════════════════════════════════════════
        # Phase 2: RERANKER — 加载 reranker，完成 rerank 后卸载
        # ═══════════════════════════════════════════════════════════
        if chunks:
            await self._load_reranker()
            ranked_chunks = await asyncio.to_thread(
                self._reranker.rerank, query, chunks, 20
            )
            await self._unload_reranker()
        else:
            ranked_chunks = []
        trace.log("reranked_count", len(ranked_chunks))
        _tick("rerank")

        # 7.5 SOURCE WEIGHTS
        if ranked_chunks:
            ranked_chunks = self._source_weights.apply_weights(ranked_chunks, intent)
        _tick("source_weights")

        # 8. BUDGET CONTROL
        selected_chunks = self._budget.select_chunks(ranked_chunks)
        context_text = self._budget.get_context_text(selected_chunks)
        trace.log("budget_chunks", len(selected_chunks))
        trace.log("budget_tokens", sum(c.get("token_count", 0) for c in selected_chunks))
        _tick("budget")

        # 8.5 SEMANTIC CACHE WRITE（需要 embedder）
        if selected_chunks:
            await self._load_embedder()
            _sc2 = SemanticCache(self.redis_client, self._embedder)
            await asyncio.to_thread(_sc2.set, query, selected_chunks)
            del _sc2
            await self._unload_embedder()
            trace.log("semantic_cache_write", True)
        _tick("cache_write")

        del chunks, docs_for_chunking, ranked_chunks
        gc.collect()

        # ═══════════════════════════════════════════════════════════
        # Phase 3: LLM — 纯 API 调用，不需要本地 ML 模型
        # ═══════════════════════════════════════════════════════════
        answer = await self.llm.generate(query, [context_text])
        trace.log("llm_done", len(answer))
        _tick("llm")

        # EVIDENCE TABLE + CONTRADICTION DETECTION（用 LLM client）
        if not self._evidence_extractor:
            self._evidence_extractor = EvidenceExtractor(self.llm.client, self.llm.model)
            self._contradiction_detector = ContradictionDetector(self.llm.client, self.llm.model)

        contradictions = await self._contradiction_detector.detect(selected_chunks[:5])
        trace.log("contradictions", len(contradictions))

        sources = [{"url": c.get("url", ""), "source": c.get("source", ""), "text": c.get("text", "")[:200]} for c in selected_chunks]
        evidence_list = await self._evidence_extractor.extract(query, answer, sources)
        trace.log("evidence_count", len(evidence_list))

        if evidence_list:
            answer += "\n\n" + self._evidence_extractor.format_table(evidence_list)
        if contradictions:
            answer += "\n\n" + self._contradiction_detector.format_contradictions(contradictions)
        _tick("evidence")

        # ═══════════════════════════════════════════════════════════
        # Phase 4: EVALUATION — 重新加载 embedder 做评估
        # ═══════════════════════════════════════════════════════════
        await self._load_embedder()
        _evaluator_final = Evaluator(self._embedder)
        score = _evaluator_final.score(query, selected_chunks, answer)
        trace.log("evaluation", score)
        del _evaluator_final, selected_chunks, context_text
        await self._unload_embedder()
        gc.collect()
        _tick("evaluation")

        # 打印各步骤耗时
        print("\n=== PIPELINE TIMING ===")
        for i in range(len(_step_times) - 1):
            label = _step_times[i][0]
            dt = _step_times[i+1][1] - _step_times[i][1]
            print(f"  {label}: {dt:.1f}s")
        total = _step_times[-1][1] - _step_times[0][1]
        print(f"  TOTAL: {total:.1f}s")
        print("=======================\n")

        # 11. CACHE WRITE
        await asyncio.to_thread(self.cache.set, query, answer)

        # 11.5 FEEDBACK LOG
        self._feedback_logger.log_query(trace.finalize(answer, score=score))
        trace.log("feedback_logged", True)

        # 12. FINALIZE TRACE
        result = trace.finalize(answer, score=score)
        await asyncio.to_thread(self.trace_store.save, result)
        return result

[中文版](README_zh.md)

<p align="center">
  <h1 align="center">Agentic RAG-CN</h1>
  <p align="center"><strong>Multi-source search, structured answers with evidence</strong></p>
  <p align="center"><a href="https://github.com/nb-clh/agentic-rag-cn/releases">v1.0.0</a></p>
</p>

<p align="center">
  <a href="https://docs.openclaw.ai">Website</a> •
  <a href="https://docs.openclaw.ai">Docs</a> •
  <a href="https://github.com/nb-clh/agentic-rag-cn">GitHub</a>
</p>

---

> AI knowing your goal is the baseline. AI knowing who you are is the next level. AI having access to high-quality search results is the ultimate level.
>
> This project solves the third one.

Most AI search tools have poor Chinese search quality and limited coverage. This project uses SearXNG + Zhihu/Bilibili/GitHub and 8 other sources, runs a full RAG pipeline (16 steps), and outputs structured answers with an evidence table. Everything runs on your own hardware — data never leaves your machine.

```bash
# Start in 30 seconds
git clone https://github.com/nb-clh/agentic-rag-cn.git && cd agentic-rag-cn
cp .env.example .env && docker compose up -d
# Verify: curl http://localhost:8000/health
```

## 📖 Table of Contents

- [Why We Built This](#why-we-built-this)
- [Features](#features)
- [Architecture](#architecture)
- [Pipeline Deep Dive](#pipeline-deep-dive)
- [Tech Selection](#tech-selection)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [API](#api)
- [Project Structure](#project-structure)
- [Tech Stack](#tech-stack)
- [FAQ](#faq)
- [OpenClaw Integration](#openclaw-integration)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)

## Why We Built This

**The core problem:** ChatGPT, Perplexity, and Tavily search backends are primarily designed for the English internet. Chinese community content from Zhihu, Bilibili, V2EX, and others is barely covered.

**Our approach:** Use SearXNG meta-search to aggregate 7 search sources (Baidu, Bing, Sogou, Quark, ChinaSo, WeChat, Yandex), plus dedicated APIs for Zhihu, Bilibili, V2EX, and GitHub — 11 sources in one query. Results go through a 16-step RAG pipeline and output structured answers with evidence tables and contradiction detection.

### Search Sources

**SearXNG Meta-search (7):**

| # | Source | Description |
|---|--------|-------------|
| 1 | Baidu | Primary Chinese search engine |
| 2 | Bing | Microsoft search |
| 3 | Sogou | Sogou search |
| 4 | Quark | Quark search |
| 5 | ChinaSo | National search engine |
| 6 | WeChat | WeChat public account articles |
| 7 | Yandex | Russian search engine |

**Dedicated APIs (4):**

| # | Source | Description |
|---|--------|-------------|
| 8 | Zhihu | Q&A community |
| 9 | Bilibili | Video/content platform |
| 10 | V2EX | Tech forum |
| 11 | GitHub | Code & Issues |

## Features

- **🔄 Query Rewrite** — Synonym expansion, up to 5 sub-queries for better recall
- **🧩 Query Decompose** — LLM breaks complex questions into independent sub-queries
- **🎯 Intent Recognition** — Classifies: factual / comparison / howto / opinion
- **🔀 Merge & Dedup** — Combines rewrite + decompose results, up to 6 unique queries
- **💾 Semantic Cache** — Embedding similarity ≥ 0.88 skips search, fast path to LLM
- **🔍 Vector Search** — FAISS local retrieval for supplementary results
- **🌐 Multi-Source Search** — 11 sources concurrent, semaphore-controlled
- **📈 Information Gain** — Semantic similarity check, early stop when no new info
- **🧹 Content Clean** — BeautifulSoup HTML → plain text
- **✂️ Chunking** — tiktoken-based, 400 tokens/chunk, 50 overlap
- **⚖️ Source Weights** — Intent-aware credibility scoring (GitHub 0.95, Zhihu 0.80, etc.)
- **🔀 Chunk Rerank** — BGE-reranker-v2-m3 cross-encoder reranking
- **📋 Evidence Table** — Structured claims with confidence & source URLs
- **⚠️ Contradiction Detection** — Cross-source conflict detection
- **📊 Feedback Logger** — Latency, hit rate, scores logged to Redis
- **🔍 Full Trace** — Every pipeline step recorded for debugging

## Architecture

```
User Query
    │
    ▼
┌─────────────────────────────────────┐
│  1. Query Rewrite                   │  Synonym expansion (LLM), ≤5 sub-queries
│  2. Query Decompose + Intent        │  Break complex Q + classify
│  3. Merge & Dedup (≤6 queries)      │  Combine & remove duplicates
└─────────────┬───────────────────────┘
              │
              ▼
┌─────────────────────────────────────┐
│  4. Semantic Cache Check            │  Embedding similarity ≥ 0.88?
│     ├─ HIT → skip to LLM            │
│     └─ MISS ↓                       │
└─────────────┬───────────────────────┘
              │
              ▼
┌─────────────────────────────────────┐
│  5. Multi-Source Search (11 sources)│  Concurrent + semaphore
│  6. Vector Search (FAISS)           │  Local retrieval
│  7. Information Gain Detection      │  Early stop if no new info
└─────────────┬───────────────────────┘
              │
              ▼
┌─────────────────────────────────────┐
│  8. Content Clean                   │  HTML → text
│  9. Chunking (400 tok, 50 overlap)  │  tiktoken split
│ 10. Rerank (BGE-reranker-v2-m3)    │  Cross-encoder
│ 11. Source Weights (intent-aware)   │  Credibility scoring
│ 12. Budget Control                  │  8K tok / 8 chunks / 5 sources
└─────────────┬───────────────────────┘
              │
              ▼
┌─────────────────────────────────────┐
│ 13. Semantic Cache Write            │  Cache selected chunks (TTL 1h)
│ 14. LLM Generate                    │  MiMo / GPT / any OpenAI-compat
│ 15. Evidence Table + Contradiction  │  Structured extraction
│ 16. Evaluation                      │  Semantic scoring
│ 17. Feedback Logger                 │  Metrics → Redis
└─────────────┬───────────────────────┘
              │
              ▼
         Structured Answer
```

### Architecture Layers

| Layer | Components | Responsibility |
|-------|-----------|----------------|
| **Entry** | `app/main.py`, `app/api.py` | FastAPI routes, injects Orchestrator |
| **Orchestration** | `core/orchestrator.py` | Core pipeline, ~320 lines orchestrating 16 steps |
| **Retrieval** | `retrieval/*.py` | Search, clean, chunk, rerank, budget control |
| **System Services** | `system_services/*.py` | Semantic cache, feedback logging |
| **Observability** | `observability/*.py` | Semantic scoring, full-pipeline tracing |
| **Cache** | `cache/redis_cache.py` | Redis exact-match cache |
| **Infrastructure** | `infra/model_loader.py` | Model loading (reserved) |

## Pipeline Deep Dive

<details>
<summary><strong>Expand for 16-step Pipeline details</strong></summary>

### Step 1: Query Rewrite

LLM rewrites the user's original query into up to 5 semantically equivalent variants with different wording. This improves recall because search engines return different results for different phrasings.

```
Original: "Python asyncio tutorial"
Rewrite:  ["Python asyncio beginner guide", "Python async await learning path", "Python asynchronous programming tutorial"]
```

**Code:** `retrieval/rewrite.py`

### Step 2: Query Decompose + Intent Recognition

Two things happen simultaneously:

1. Classify the query's **intent type**
2. If it's a complex question, break it into 2-4 independent sub-questions

**Intent types (5):**

| Intent | Meaning | Example |
|--------|---------|---------|
| `factual` | Fact lookup | "When was Python 3.12 released?" |
| `comparison` | Compare options | "Redis vs Memcached which is better" |
| `howto` | How-to guide | "How to install PostgreSQL in Docker" |
| `opinion` | Discussion | "What do people think about Rust?" |
| `general` | Other | Anything not in the above four |

**Code:** `retrieval/decompose.py`

### Step 3: Merge & Dedup

Combines results from Query Rewrite and Query Decompose, deduplicates, and caps at ≤ 6 queries.

**Code:** `core/orchestrator.py`

### Step 4: Semantic Cache Check

Before searching, checks if there's a semantically similar cached query. If hit, uses cached chunks directly with the LLM, skipping search and reranking.

- Computes query vector with bge-small-zh-v1.5
- Retrieves all cached query vectors from Redis
- Computes cosine similarity
- Highest similarity ≥ 0.88 → cache hit

**What's cached:** Not the final answer, but the **selected chunks** (after Budget Control). TTL 1 hour. Chunks can be reused for different questions on the same topic.

**Code:** `system_services/semantic_cache.py`

### Step 5: Multi-Source Search

Concurrently searches 11 sources:

| # | Source | Implementation | Notes |
|---|--------|---------------|-------|
| 1 | Baidu | SearXNG | Primary Chinese search |
| 2 | Bing | SearXNG | Microsoft search |
| 3 | Sogou | SearXNG | Sogou search |
| 4 | Quark | SearXNG | Quark search |
| 5 | ChinaSo | SearXNG | National search engine |
| 6 | WeChat | SearXNG | WeChat public account articles |
| 7 | Yandex | SearXNG | Russian search engine |
| 8 | Zhihu | Dedicated API | Q&A community |
| 9 | Bilibili | Dedicated API | Video content |
| 10 | V2EX | Dedicated API | Tech forum |
| 11 | GitHub | Dedicated API | Code & Issues |

- SearXNG 7 engines fetched in one request (internal concurrency)
- Zhihu, Bilibili, V2EX, GitHub each have independent API calls
- `asyncio.gather` for concurrency, semaphore caps at 3
- URL-level deduplication

**Code:** `retrieval/web.py` (SearXNG), `retrieval/multi_source.py` (Zhihu/Bilibili/V2EX/GitHub)

### Step 6: Information Gain Detection

Starting from the second sub-query, checks if new search results contain new information. If not, stops searching early — saving time and API calls.

- Computes vectors for new and existing chunks with bge-small-zh-v1.5
- For each new chunk, finds max cosine similarity with existing chunks
- All new chunks have max similarity ≥ 0.92 → no new info → early stop

**Code:** `retrieval/information_gain.py`

### Step 7: Content Clean

BeautifulSoup converts HTML content to plain text, removing tags, ads, navigation bars, and other noise.

**Code:** `retrieval/clean.py`

### Step 8: Chunking

Splits long text into small chunks by token count. LLM context windows are limited, so only the most relevant parts are selected.

- Chunk size: 400 tokens
- Overlap: 50 tokens (prevents information loss at boundaries)
- Encodes with tiktoken, splits by token count

**Code:** `retrieval/chunker.py`

### Step 9: Chunk Rerank

Uses a cross-encoder to rerank all chunks by relevance to the query.

- Model: BAAI/bge-reranker-v2-m3
- Input: (query, chunk_text) pairs
- Output: relevance scores
- Batch processing (5 per batch) to reduce peak memory
- Returns top 20

**Why cross-encoder:** Vector search (bi-encoder) is fast but less precise. Cross-encoder is precise but slower. First recall candidates with vector search, then rerank with cross-encoder — classic two-stage retrieval.

**Code:** `retrieval/rerank.py`

### Step 10: Source Weights

Assigns different credibility weights to different sources based on query intent. Different sources are more trustworthy for different intents.

| Source | Default | factual | comparison | howto | opinion |
|--------|---------|---------|------------|-------|---------|
| GitHub | 0.95 | 0.95 | 0.95 | 0.95 | 0.95 |
| Official docs | 0.90 | 0.95 | 0.90 | 0.95 | 0.90 |
| V2EX | 0.85 | 0.85 | 0.90 | 0.85 | 0.90 |
| Zhihu | 0.80 | 0.80 | 0.85 | 0.80 | 0.90 |
| Bilibili | 0.75 | 0.75 | 0.80 | 0.75 | 0.85 |
| WeChat | 0.70 | 0.70 | 0.70 | 0.70 | 0.70 |
| SEO spam | 0.20 | 0.20 | 0.20 | 0.20 | 0.20 |

Built-in SEO spam blacklist (e.g., `blog.csdn.net`, `zhidao.baidu.com`), auto-downweighted to 0.20.

**Code:** `retrieval/source_weights.py`

### Step 11: Budget Control

Selects which reranked chunks to send to the LLM, controlling total token count. Balances information volume against cost.

| Limit | Value | Description |
|-------|-------|-------------|
| Max tokens | 8000 | Total context tokens |
| Max chunks | 8 | At most 8 chunks |
| Max sources | 5 | At most 5 different sources |

Selects in descending rerank score until any limit is hit.

**Code:** `retrieval/budget.py`

### Step 12: Semantic Cache Write

Writes the selected chunks (after Budget Control) to semantic cache. TTL 1 hour — search results have limited freshness, and 1 hour is the balance between information recency and cache hit rate.

**Code:** `system_services/semantic_cache.py`

### Step 13: LLM Generate

Concatenates selected chunks into context, sends with the user query to the LLM to generate the final answer.

- Format: `[Source 1: xxx]\nContent\n\n---\n\n[Source 2: xxx]\nContent`
- Safety net: max 30000 characters for context
- LLM params: temperature=0.3 (low, more deterministic), max_tokens=2000
- Supports any OpenAI-compatible API (MiMo, GPT, Claude, etc.)

**Code:** `core/llm.py`

### Step 14: Evidence Table + Contradiction Detection

Two things:

1. **Evidence table extraction** — Extracts key claims from the LLM answer, annotates with evidence sources and confidence
2. **Contradiction detection** — Checks if different sources have conflicting information

```
📋 Evidence
1. [high] asyncio is ideal for I/O-bound tasks → Python docs explicitly state... (source: https://docs.python.org)
2. [medium] threading suits CPU-bound tasks → Stack Overflow majority agrees... (source: https://stackoverflow.com)

⚠️ Contradictions
1. [medium] GIL impact on asyncio: A says no impact, B says indirect impact
```

**Code:** `retrieval/evidence.py`, `retrieval/contradiction.py`

### Step 15: Feedback Logger

Records complete metrics for each query to Redis (TTL 7 days).

| Metric | Description |
|--------|-------------|
| `intent` | Recognized intent |
| `web_results` | Web search result count |
| `chunks_count` | Chunk count |
| `reranked_count` | Chunks after reranking |
| `budget_chunks` | Chunks after budget control |
| `cache_hit` | Exact cache hit |
| `semantic_cache_hit` | Semantic cache hit |
| `evaluation_score` | Semantic score (0-1) |
| `evidence_count` | Evidence items |
| `contradictions` | Contradiction items |

**Code:** `system_services/feedback_logger.py`

### Step 16: Evaluation

Uses the embedding model to compute semantic similarity between the answer and the query+context, producing a 0-1 score for answer quality quantification.

**Code:** `observability/evaluator.py`

</details>

## Tech Selection

<details>
<summary><strong>Expand for tech selection details</strong></summary>

### Why bge-small-zh-v1.5 for Embedding?

- **Chinese-optimized:** Purpose-built for Chinese, excellent performance
- **Open source & free:** No API call costs
- **Runs locally:** Data stays on your machine, CPU-friendly
- **Balanced dimensions:** 1024 dimensions, good precision-speed tradeoff

### Why BGE-reranker-v2-m3 for Reranking?

- **Cross-encoder architecture:** Higher precision than bi-encoder
- **Multilingual:** Works well for both Chinese and English
- **Open source & free:** Runs locally
- **Same model family:** Consistency with the embedding model

### Why SearXNG Instead of Direct Search Engine APIs?

- **Aggregation:** One request fetches results from multiple search engines
- **Privacy:** Doesn't expose user IP directly to search engines
- **Extensible:** Adding new engines only requires SearXNG config changes
- **Open source:** No API fees

### Why Cache Chunks Instead of Final Answers?

- **Reusability:** Same chunks can serve different questions on the same topic
- **Flexibility:** Chunks can generate different answer styles with different prompts
- **Freshness:** Expired chunks auto-invalidate, avoiding stale answers

### Why 5 Intent Types?

- **Comprehensive coverage:** These 5 intents cover the vast majority of user queries
- **Source weight differentiation:** Different intents warrant different source credibility
- **Simplicity:** Too many intents reduce classification accuracy; 5 is the sweet spot

</details>

## Quick Start

### Prerequisites

- Docker & Docker Compose
- A SearXNG instance (or use the included setup)
- An OpenAI-compatible API key (MiMo, GPT, etc.)

### 1. Clone & Configure

```bash
git clone https://github.com/nb-clh/agentic-rag-cn.git
cd agentic-rag-cn

# Copy and edit environment file
cp .env.example .env
```

Edit `.env`:

```bash
# Required
OPENAI_API_KEY=your_api_key_here
OPENAI_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini

# SearXNG (must be running separately)
SEARXNG_URL=http://searxng:8080

# Redis (auto-configured in docker-compose)
REDIS_HOST=redis
REDIS_PORT=6379

# HuggingFace mirror (for China users)
HF_ENDPOINT=https://hf-mirror.com

# FAISS index path
FAISS_INDEX_PATH=/app/data/faiss.index
```

### 2. Start Services

```bash
docker compose up -d
```

This starts:
- **API server** on port `8000`
- **Redis** on port `6379` (mapped from container 6379)

### 3. Verify

```bash
# Health check
curl http://localhost:8000/health
# → {"status": "ok"}

# First query (models need to load, please wait)
curl -s http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is RAG"}' | jq .
```

> **Note:** The first request loads ML models (bge-small-zh-v1.5 embedding + BGE-reranker). Once loaded, models stay in memory and subsequent requests are fast.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | — | API key for LLM (required) |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | OpenAI-compatible API endpoint |
| `LLM_MODEL` | `gpt-4o-mini` | Model name |
| `SEARXNG_URL` | `http://searxng:8080` | SearXNG instance URL |
| `REDIS_HOST` | `localhost` | Redis host |
| `REDIS_PORT` | `6379` | Redis port |
| `HF_ENDPOINT` | `https://hf-mirror.com` | HuggingFace mirror (for China) |
| `FAISS_INDEX_PATH` | `/app/data/faiss.index` | FAISS index file path |

## API

### POST /query

Execute a full search + RAG pipeline.

**Request:**

```json
{
  "query": "Python asyncio vs threading performance comparison"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | string | ✅ | User query |

**Response:**

```json
{
  "trace_id": "a1b2c3d4-e5f6-...",
  "query": "Python asyncio vs threading performance comparison",
  "events": [
    {"step": "cache_hit", "data": "False"},
    {"step": "rewrite", "data": "[...]"},
    {"step": "intent", "data": "comparison"},
    {"step": "web_results", "data": "12"},
    {"step": "chunks_count", "data": "45"},
    {"step": "reranked_count", "data": "20"},
    {"step": "budget_chunks", "data": "8"},
    {"step": "evaluation", "data": "0.8234"}
  ],
  "final": "## Python asyncio vs threading\n\n...",
  "score": 0.8234,
  "metadata": {}
}
```

### GET /health

```json
{"status": "ok"}
```

## Project Structure

```
agentic-rag-cn/
├── app/
│   ├── main.py              # FastAPI entry + lifespan init
│   └── api.py               # Routes, injects Orchestrator
├── core/
│   ├── orchestrator.py      # Core pipeline (~320 lines, 16 steps)
│   ├── llm.py               # LLM adapter (AsyncOpenAI)
│   └── trace.py             # Full-pipeline tracing
├── retrieval/
│   ├── web.py               # SearXNG search
│   ├── multi_source.py      # Zhihu / Bilibili / V2EX / GitHub
│   ├── vector.py            # FAISS + bge-small-zh vector search
│   ├── rerank.py            # BGE-reranker-v2-m3 cross-encoder
│   ├── rewrite.py           # LLM query rewrite
│   ├── decompose.py         # LLM query decomposition + intent
│   ├── clean.py             # BeautifulSoup HTML cleaning
│   ├── chunker.py           # tiktoken chunking (400 tok, 50 overlap)
│   ├── budget.py            # Token budget controller
│   ├── source_weights.py    # Intent-aware source credibility
│   ├── evidence.py          # Evidence table extraction
│   ├── contradiction.py     # Cross-source contradiction detection
│   └── information_gain.py  # Information gain early-stop
├── cache/
│   └── redis_cache.py       # Redis exact-match cache
├── system_services/
│   ├── semantic_cache.py    # Semantic cache (embedding similarity)
│   ├── session_memory.py    # Session memory (Jaccard dedup)
│   └── feedback_logger.py   # Feedback metrics → Redis
├── observability/
│   ├── evaluator.py         # Semantic scoring
│   └── trace_store.py       # Redis + file dual backup
├── infra/
│   └── model_loader.py      # Model loading (reserved)
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| API framework | FastAPI + uvicorn |
| LLM | OpenAI-compatible API (MiMo, GPT, etc.) |
| Embedding | BAAI/bge-small-zh-v1.5 (sentence-transformers) |
| Reranker | BAAI/bge-reranker-v2-m3 (cross-encoder) |
| Vector store | FAISS (CPU) |
| Cache & session | Redis 7 |
| Token counting | tiktoken |
| HTML parsing | BeautifulSoup4 |
| HTTP client | httpx |
| Meta-search | SearXNG |
| Runtime | Python 3.11, PyTorch (CPU) |

## FAQ

<details>
<summary><strong>Expand for frequently asked questions</strong></summary>

### Why is the first request slow?

The first request loads two ML models (bge-small-zh-v1.5 embedding + BGE-reranker). Once loaded, models stay in memory and subsequent requests are fast.

### How much memory does it use?

About 4-6 GB, mainly for the two ML models. If memory is tight, consider smaller models or GPU acceleration.

### Which LLMs are supported?

Any OpenAI-compatible API works. Default is Xiaomi's MiMo-v2.5-pro. Also works with GPT-4, Claude (via API), DeepSeek, etc.

### Can I skip SearXNG?

SearXNG is the core search component — without it, there's no search. But you can use only the Zhihu/Bilibili/V2EX/GitHub searches from `multi_source.py` by removing the SearXNG parts. Requires code changes.

### How was the semantic cache threshold 0.88 determined?

Empirically. 0.88 means only highly similar queries hit the cache. Too low causes irrelevant cache hits (quality drops); too high means the cache almost never hits (useless).

### Can I add new search sources?

Yes. Add a new search method in `retrieval/multi_source.py`, then call it in `search_all()`.

### Does data really never leave my machine?

Except for LLM API calls (which send the query to the API server), all search, caching, and logging happen locally. If you use a local LLM (e.g., Ollama), nothing leaves your machine at all.

</details>

## OpenClaw Integration

This project provides an OpenClaw Skill that lets AI assistants call deep search directly:

```bash
# Install the skill
npx clawhub install agentic-rag-cn
```

Once installed, the AI assistant will automatically call this project's API when deep search is needed. If the service is unavailable, it falls back to built-in web_search.

Skill page: [clawhub.ai/nb-clh/agentic-rag-cn](https://clawhub.ai/nb-clh/agentic-rag-cn)

## Roadmap

- [ ] Streaming response support
- [ ] Multi-turn conversation with context
- [ ] Custom search source plugins
- [ ] Web UI dashboard
- [ ] Query analytics dashboard
- [ ] GPU acceleration for reranker
- [ ] Distributed deployment (multi-node)
- [ ] API authentication & rate limiting
- [ ] Docker image on GHCR/DockerHub
- [ ] Benchmark suite with standard datasets
- [ ] Deep-dive mode (auto re-search on low confidence)
- [ ] Hypothesis-guided search
- [ ] Evidence graph
- [ ] Adaptive strategy engine

## Contributing

Contributions welcome! Here are ways to get involved:

- **Submit code** — Fork the repo, create a feature branch, open a Pull Request
- **Report bugs** — File bug reports in Issues
- **Suggest features** — Open feature requests in Issues
- **Improve docs** — Documentation PRs are equally welcome
- **Add search sources** — Add new sources in `retrieval/multi_source.py`

### Development Setup

```bash
# Clone
git clone https://github.com/nb-clh/agentic-rag-cn.git
cd agentic-rag-cn

# Install dependencies
pip install -r requirements.txt

# Start Redis (required)
docker run -d --name redis -p 6379:6379 redis:7-alpine

# Run dev server
uvicorn app.main:app --reload --port 8000
```

### Areas that need help

- 🌐 More search sources (Douyin, Xiaohongshu, Weibo)
- 🎨 Web UI
- 📊 Benchmarking & evaluation
- 🐳 Kubernetes deployment manifests
- 📖 Documentation & tutorials
- 🌍 Internationalization

## License

[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)

You are free to share and adapt this work for non-commercial purposes, with attribution and under the same license.

---

## Acknowledgments

- [SearXNG](https://docs.searxng.org/) — Privacy-respecting meta-search engine
- [BAAI/bge-small-zh-v1.5](https://huggingface.co/BAAI/bge-small-zh-v1.5) — Chinese embedding model
- [BAAI/bge-reranker-v2-m3](https://huggingface.co/BAAI/bge-reranker-v2-m3) — Cross-encoder reranker
- [FastAPI](https://fastapi.tiangolo.com/) — Modern Python web framework

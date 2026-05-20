[English](README.md)

<p align="center">
  <h1 align="center">Agentic RAG-CN</h1>
  <p align="center"><strong>一次查询，11 个搜索源，带证据的结构化答案</strong></p>
  <p align="center"><a href="https://github.com/nb-clh/agentic-rag-cn/releases">v1.0.0</a></p>
</p>

<p align="center">
  <a href="https://docs.openclaw.ai">Website</a> •
  <a href="https://docs.openclaw.ai">Docs</a> •
  <a href="https://github.com/nb-clh/agentic-rag-cn">GitHub</a>
</p>

---

> ai知道你想达成什么，是及格线；ai知道你是谁，是优秀线；ai能用到高质量搜索结果，是顶级线。
>
> 本项目解决第三条。

当前 AI 搜索工具对中文支持不佳——搜索结果质量差、覆盖不全。本项目用 SearXNG + 知乎/B站/GitHub 等 多个来源做搜索，经过完整 RAG 流水线（16 步），输出带证据表的结构化答案。全部跑在你自己的硬件上，数据不出门。

```bash
# 30 秒启动
git clone https://github.com/nb-clh/agentic-rag-cn.git && cd agentic-rag-cn
cp .env.example .env && docker compose up -d
# 验证：curl http://localhost:8000/health
```

## 📖 目录

- [为什么做这个项目](#为什么做这个项目)
- [功能特性](#功能特性)
- [系统架构](#系统架构)
- [Pipeline 详解](#pipeline-详解)
- [技术选型](#技术选型)
- [快速开始](#快速开始)
- [配置](#配置)
- [API](#api)
- [项目结构](#项目结构)
- [技术栈](#技术栈)
- [FAQ](#faq)
- [OpenClaw 集成](#openclaw-集成)
- [路线图](#路线图)
- [贡献](#贡献)
- [许可证](#许可证)

## 为什么做这个项目

**根本问题：** ChatGPT、Perplexity、Tavily 等工具的搜索后端主要面向英文互联网，对中文搜索的覆盖和优化不足。知乎、B站、V2EX 等中文社区的内容几乎搜不到。

**本项目的解法：** 用 SearXNG 元搜索引擎聚合 7 个搜索源（百度、Bing、搜狗、夸克、中国搜索、微信、Yandex），再对接知乎、B站、V2EX、GitHub 的独立 API——一次查询覆盖 11 个来源，经过 16 步 RAG 流水线，输出带证据表和矛盾检测的结构化答案。

### 搜索来源

**SearXNG 元搜索（7 个）：**

| # | 来源 | 说明 |
|---|------|------|
| 1 | 百度 | 国内搜索主力 |
| 2 | Bing | 微软搜索 |
| 3 | 搜狗 | 搜狗搜索 |
| 4 | 夸克 | 夸克搜索 |
| 5 | 中国搜索 | 国家搜索引擎 |
| 6 | 微信 | 微信公众号文章 |
| 7 | Yandex | 俄罗斯搜索引擎 |

**独立 API（4 个）：**

| # | 来源 | 说明 |
|---|------|------|
| 8 | 知乎 | 问答社区 |
| 9 | B站 | 视频/内容平台 |
| 10 | V2EX | 技术论坛 |
| 11 | GitHub | 代码与 Issues |

## 功能特性

- **🔄 查询改写** — 同义词扩展，最多 5 个子查询，提高召回率
- **🧩 查询分解** — LLM 将复杂问题拆分为独立子查询
- **🎯 意图识别** — 自动分类：事实型 / 对比型 / 操作型 / 观点型
- **🔀 合并去重** — 合并改写与分解结果，最多 6 个唯一查询
- **💾 语义缓存** — Embedding 相似度 ≥ 0.88 命中缓存，跳过搜索直接走 LLM
- **🔍 向量搜索** — FAISS 本地检索，补充搜索结果
- **🌐 多源搜索** — 多个引擎并发，信号量控制
- **📈 信息增益** — 语义相似度检测，无新信息时提前停止搜索
- **🧹 内容清洗** — BeautifulSoup HTML 转纯文本，去除噪音
- **✂️ 分块** — 基于 tiktoken，400 tokens/块，50 重叠
- **⚖️ 来源权重** — 意图感知的可信度评分（GitHub 0.95、知乎 0.80 等）
- **🔀 重排序** — BGE-reranker-v2-m3 交叉编码器精排
- **📋 证据表** — 结构化声明，含置信度和来源 URL
- **⚠️ 矛盾检测** — 自动检测跨来源的信息冲突
- **📊 反馈日志** — 延迟、命中率、评分记录到 Redis
- **🔍 完整追踪** — Pipeline 每一步都有记录，便于调试

## 系统架构

```
用户查询
    │
    ▼
┌─────────────────────────────────────┐
│  1. 查询改写                         │  同义替换（LLM），生成 ≤5 个子查询
│  2. 查询分解 + 意图识别              │  拆解复杂问题 + 分类
│  3. 合并去重（≤6 个查询）             │  合并并去除重复
└─────────────┬───────────────────────┘
              │
              ▼
┌─────────────────────────────────────┐
│  4. 语义缓存检查                     │  Embedding 相似度 ≥ 0.88？
│     ├─ 命中 → 跳转到 LLM             │
│     └─ 未命中 ↓                      │
└─────────────┬───────────────────────┘
              │
              ▼
┌─────────────────────────────────────┐
│  5. 多源搜索（11 源）              │  并发 + 信号量控制
│  6. 向量搜索（FAISS）                │  本地检索
│  7. 信息增益检测                     │  无新信息时提前停止
└─────────────┬───────────────────────┘
              │
              ▼
┌─────────────────────────────────────┐
│  8. 内容清洗                         │  HTML → 纯文本
│  9. 分块（400 token, 50 重叠）        │  tiktoken 分块
│ 10. 重排序（BGE-reranker-v2-m3）     │  交叉编码器
│ 11. 来源权重                         │  可信度评分（意图感知）
│ 12. 预算控制                         │  8K token / 8 块 / 5 来源
└─────────────┬───────────────────────┘
              │
              ▼
┌─────────────────────────────────────┐
│ 13. 语义缓存写入                     │  缓存精选结果（TTL 1小时）
│ 14. LLM 生成                         │  MiMo / GPT / 任何 OpenAI 兼容 API
│ 15. 证据表 + 矛盾检测               │  结构化信息抽取
│ 16. 语义评估                         │  Embedding 相似度评分
│ 17. 反馈日志                         │  指标 → Redis
└─────────────┬───────────────────────┘
              │
              ▼
         结构化答案
```

### 架构分层

| 层 | 组件 | 职责 |
|---|------|------|
| **入口层** | `app/main.py`, `app/api.py` | FastAPI 路由，注入 Orchestrator |
| **编排层** | `core/orchestrator.py` | 核心 pipeline，约 320 行代码编排 16 步 |
| **检索层** | `retrieval/*.py` | 搜索、清洗、分块、重排序、预算控制 |
| **系统服务层** | `system_services/*.py` | 语义缓存、反馈日志 |
| **可观测层** | `observability/*.py` | 语义评分、全链路追踪 |
| **缓存层** | `cache/redis_cache.py` | Redis 精确缓存 |
| **基础设施层** | `infra/model_loader.py` | 模型加载（预留） |

## Pipeline 详解

<details>
<summary><strong>展开查看 16 步 Pipeline 详细说明</strong></summary>

### Step 1: 查询改写（Query Rewrite）

用 LLM 对用户原始查询做同义替换，生成最多 5 个不同表述的子查询。用户的原始查询可能不够精确，不同表述能让搜索引擎返回不同结果，提高召回率。

```
原始查询: "Python 异步编程怎么学"
改写结果: ["Python asyncio 入门教程", "Python 异步编程指南", "Python async await 学习路线"]
```

**代码位置：** `retrieval/rewrite.py`

### Step 2: 查询分解 + 意图识别（Query Decompose + Intent）

两件事同时完成：

1. 判断查询的**意图类型**
2. 如果是复杂问题，拆成 2-4 个独立子问题

**意图类型（5 种）：**

| 意图 | 含义 | 示例 |
|------|------|------|
| `factual` | 事实查询 | "Python 3.12 什么时候发布的" |
| `comparison` | 对比分析 | "Redis vs Memcached 哪个好" |
| `howto` | 操作指南 | "怎么在 Docker 里装 PostgreSQL" |
| `opinion` | 观点讨论 | "大家怎么看 Rust 这门语言" |
| `general` | 其他 | 不属于以上四类 |

**代码位置：** `retrieval/decompose.py`

### Step 3: 合并去重（Merge & Dedup）

把查询改写和查询分解的结果合并，去重，限制总数 ≤ 6。

**代码位置：** `core/orchestrator.py`

### Step 4: 语义缓存检查（Semantic Cache Check）

在搜索之前，检查是否有语义相似的历史查询。如果命中，直接用缓存的 chunks 走 LLM，跳过搜索和重排序。

- 用 bge-small-zh-v1.5 模型计算当前查询的向量
- 从 Redis 中取出所有缓存的查询向量
- 计算余弦相似度
- 最高相似度 ≥ 0.88 → 命中缓存

**缓存内容：** 不是缓存最终答案，而是缓存**精选后的 chunks**（预算控制之后的结果）。TTL 1 小时。Chunks 可以复用于同一主题的不同角度问题。

**代码位置：** `system_services/semantic_cache.py`

### Step 5: 多源搜索（Multi-Source Search）

并发搜索 11 个来源：

| # | 来源 | 实现方式 | 备注 |
|---|------|---------|------|
| 1 | 百度 | SearXNG | 国内搜索主力 |
| 2 | Bing | SearXNG | 微软搜索 |
| 3 | 搜狗 | SearXNG | 搜狗搜索 |
| 4 | 夸克 | SearXNG | 夸克搜索 |
| 5 | 中国搜索 | SearXNG | 国家搜索引擎 |
| 6 | 微信 | SearXNG | 微信公众号文章 |
| 7 | Yandex | SearXNG | 俄罗斯搜索引擎 |
| 8 | 知乎 | 独立 API | 问答社区 |
| 9 | B站 | 独立 API | 视频内容 |
| 10 | V2EX | 独立 API | 技术论坛 |
| 11 | GitHub | 独立 API | 代码与 Issues |

- SearXNG 7 个引擎通过 `/search` API 一次请求获取
- 知乎、B站、V2EX、GitHub 各自独立调用
- 用 `asyncio.gather` 并发，信号量控制最大并发数为 3
- URL 级别去重

**代码位置：** `retrieval/web.py`（SearXNG）、`retrieval/multi_source.py`（知乎/B站/V2EX/GitHub）

### Step 6: 信息增益检测（Information Gain Detection）

从第二个子查询开始，检查新搜索结果是否包含新信息。如果没有新信息，提前停止搜索，节省搜索时间和 API 调用。

- 用 bge-small-zh-v1.5 计算新 chunks 和已有 chunks 的向量
- 对每个新 chunk，找与已有 chunks 的最高余弦相似度
- 所有新 chunk 的最高相似度都 ≥ 0.92 → 没有新信息 → 提前停止

**代码位置：** `retrieval/information_gain.py`

### Step 7: 内容清洗（Content Clean）

用 BeautifulSoup 把 HTML 内容清洗成纯文本，去除标签、广告、导航栏等噪音。

**代码位置：** `retrieval/clean.py`

### Step 8: 分块（Chunking）

把长文本按 token 数切分成小块。LLM 的上下文窗口有限，需要把长文档切成小块，只选最相关的部分。

- 块大小：400 tokens
- 重叠：50 tokens（避免信息在边界丢失）
- 用 tiktoken 编码文本，按 token 数切分

**代码位置：** `retrieval/chunker.py`

### Step 9: 重排序（Chunk Rerank）

用交叉编码器（Cross-encoder）对所有 chunks 按与查询的相关性重新排序。

- 模型：BAAI/bge-reranker-v2-m3
- 输入：(query, chunk_text) 配对
- 输出：相关性分数
- 分批处理（每批 5 个），减少峰值内存
- 返回 top 20

**为什么用交叉编码器：** 向量检索（Bi-encoder）速度快但精度低，交叉编码器精度高但速度慢。先向量检索召回候选，再交叉编码器精排，是经典的两阶段检索范式。

**代码位置：** `retrieval/rerank.py`

### Step 10: 来源权重（Source Weights）

根据查询意图，给不同来源分配不同的可信度权重。不同意图下，不同来源的可信度不同。

| 来源 | 默认 | factual | comparison | howto | opinion |
|------|------|---------|------------|-------|---------|
| GitHub | 0.95 | 0.95 | 0.95 | 0.95 | 0.95 |
| 官方文档 | 0.90 | 0.95 | 0.90 | 0.95 | 0.90 |
| V2EX | 0.85 | 0.85 | 0.90 | 0.85 | 0.90 |
| 知乎 | 0.80 | 0.80 | 0.85 | 0.80 | 0.90 |
| B站 | 0.75 | 0.75 | 0.80 | 0.75 | 0.85 |
| 微信公众号 | 0.70 | 0.70 | 0.70 | 0.70 | 0.70 |
| SEO 垃圾站 | 0.20 | 0.20 | 0.20 | 0.20 | 0.20 |

内置 SEO 垃圾站黑名单（如 `blog.csdn.net`、`zhidao.baidu.com`），自动降权到 0.20。

**代码位置：** `retrieval/source_weights.py`

### Step 11: 预算控制（Budget Control）

从重排序后的 chunks 中选择最终送给 LLM 的部分，控制总 token 数。在信息量和资源消耗之间找平衡。

| 限制项 | 值 | 说明 |
|--------|-----|------|
| 最大 token 数 | 8000 | 上下文总 token 数 |
| 最大 chunk 数 | 8 | 最多选 8 个 chunk |
| 最大来源数 | 5 | 最多来自 5 个不同来源 |

按 rerank score 从高到低依次选择，直到任一预算限制被触发。

**代码位置：** `retrieval/budget.py`

### Step 12: 语义缓存写入（Semantic Cache Write）

把预算控制选出的精选 chunks 写入语义缓存。TTL 1 小时——搜索结果的时效性有限，1 小时是信息新鲜度和缓存命中率的平衡点。

**代码位置：** `system_services/semantic_cache.py`

### Step 13: LLM 生成（LLM Generate）

把精选 chunks 拼接成上下文，连同用户查询一起发给 LLM，生成最终答案。

- 拼接格式：`[来源 1: xxx]\n内容\n\n---\n\n[来源 2: xxx]\n内容`
- 安全网：上下文最大 30000 字符
- LLM 参数：temperature=0.3（低温度，更确定性的回答），max_tokens=2000
- 支持任意 OpenAI 兼容 API（MiMo、GPT、Claude 等）

**代码位置：** `core/llm.py`

### Step 14: 证据表 + 矛盾检测（Evidence Table + Contradiction Detection）

两件事：

1. **证据表提取** — 从 LLM 答案中提取关键论点，标注证据来源和置信度
2. **矛盾检测** — 检查不同来源的信息是否有矛盾

```
📋 证据表
1. [high] asyncio 适合 I/O 密集型任务 → Python 官方文档明确说明...（来源：https://docs.python.org）
2. [medium] threading 适合 CPU 密集型任务 → Stack Overflow 多数回答...（来源：https://stackoverflow.com）

⚠️ 信息矛盾
1. [medium] GIL 对 asyncio 的影响：A 说无影响，B 说有间接影响
```

**代码位置：** `retrieval/evidence.py`、`retrieval/contradiction.py`

### Step 15: 反馈日志（Feedback Logger）

记录每次查询的完整指标，存入 Redis（TTL 7 天）。

| 指标 | 说明 |
|------|------|
| `intent` | 识别出的意图 |
| `web_results` | Web 搜索结果数 |
| `chunks_count` | 分块数 |
| `reranked_count` | 重排序后 chunk 数 |
| `budget_chunks` | 预算控制后 chunk 数 |
| `cache_hit` | 精确缓存命中 |
| `semantic_cache_hit` | 语义缓存命中 |
| `evaluation_score` | 语义评分（0-1） |
| `evidence_count` | 证据条数 |
| `contradictions` | 矛盾条数 |

**代码位置：** `system_services/feedback_logger.py`

### Step 16: 语义评估（Evaluation）

用 Embedding 模型计算答案与查询+上下文的语义相似度，给出 0-1 的评分，用于量化答案质量。

**代码位置：** `observability/evaluator.py`

</details>

## 技术选型

<details>
<summary><strong>展开查看技术选型说明</strong></summary>

### 为什么选 bge-small-zh-v1.5 做 Embedding？

- **中文优化：** 专为中文优化，效果好
- **开源免费：** 不需要 API 调用费用
- **本地运行：** 数据不出门，CPU 就能跑
- **维度适中：** 1024 维，精度和速度的平衡

### 为什么选 BGE-reranker-v2-m3 做 Reranker？

- **Cross-encoder 架构：** 比 Bi-encoder 精度更高
- **多语言支持：** 中英文都好
- **开源免费：** 本地运行
- **与 Embedding 模型同系列：** 一致性好

### 为什么用 SearXNG 而不是直接调搜索引擎 API？

- **聚合能力：** 一次请求获取多个搜索引擎结果
- **隐私保护：** 不直接暴露用户 IP 给搜索引擎
- **可扩展：** 添加新搜索引擎只需修改 SearXNG 配置
- **开源：** 无 API 费用

### 为什么缓存 chunks 而不是最终答案？

- **复用性：** 同一主题的不同问题可以复用相同的 chunks
- **灵活性：** Chunks 可以用不同的 prompt 生成不同风格的答案
- **时效性：** Chunks 过期后自动失效，避免过时答案

### 为什么设置 5 种意图类型？

- **覆盖全面：** 这 5 种意图覆盖了绝大多数用户查询
- **来源权重差异化：** 不同意图下，不同来源的可信度不同
- **简洁：** 意图太多会导致分类不准，5 个是平衡点

</details>

## 快速开始

### 前置条件

- Docker 和 Docker Compose
- SearXNG 实例（或使用内置的配置）
- OpenAI 兼容的 API Key（MiMo、GPT 等）

### 1. 克隆并配置

```bash
git clone https://github.com/nb-clh/agentic-rag-cn.git
cd agentic-rag-cn

# 复制并编辑环境变量文件
cp .env.example .env
```

编辑 `.env`：

```bash
# 必填
OPENAI_API_KEY=your_api_key_here
OPENAI_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini

# SearXNG（需要单独运行）
SEARXNG_URL=http://searxng:8080

# Redis（在 docker-compose 中已自动配置）
REDIS_HOST=redis
REDIS_PORT=6379

# HuggingFace 镜像（国内用户使用）
HF_ENDPOINT=https://hf-mirror.com

# FAISS 索引路径
FAISS_INDEX_PATH=/app/data/faiss.index
```

### 2. 启动服务

```bash
docker compose up -d
```

这将启动：
- **API 服务** 运行在端口 `8000`
- **Redis** 运行在端口 `6379`（从容器 6379 映射）

### 3. 验证

```bash
# 健康检查
curl http://localhost:8000/health
# → {"status": "ok"}

# 首次查询（模型需要加载，请耐心等待）
curl -s http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "什么是 RAG"}' | jq .
```

> **注意：** 首次请求需要加载 ML 模型（bge-small-zh-v1.5 embedding + BGE-reranker），加载完成后模型常驻内存，后续请求很快。

## 配置

| 变量名 | 默认值 | 说明 |
|----------|---------|-------------|
| `OPENAI_API_KEY` | — | LLM 的 API Key（必填） |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | OpenAI 兼容的 API 端点 |
| `LLM_MODEL` | `gpt-4o-mini` | 模型名称 |
| `SEARXNG_URL` | `http://searxng:8080` | SearXNG 实例 URL |
| `REDIS_HOST` | `localhost` | Redis 主机 |
| `REDIS_PORT` | `6379` | Redis 端口 |
| `HF_ENDPOINT` | `https://hf-mirror.com` | HuggingFace 镜像（国内用户） |
| `FAISS_INDEX_PATH` | `/app/data/faiss.index` | FAISS 索引文件路径 |

## API

### POST /query

执行一次完整的搜索 + RAG 流水线。

**请求：**

```json
{
  "query": "Python asyncio vs threading 性能对比"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `query` | string | ✅ | 用户查询 |

**响应：**

```json
{
  "trace_id": "a1b2c3d4-e5f6-...",
  "query": "Python asyncio vs threading 性能对比",
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

## 项目结构

```
agentic-rag-cn/
├── app/
│   ├── main.py              # FastAPI 入口 + lifespan 初始化
│   └── api.py               # 路由，注入 Orchestrator
├── core/
│   ├── orchestrator.py      # 核心 Pipeline（约 320 行，16 个步骤）
│   ├── llm.py               # LLM 适配器（AsyncOpenAI）
│   └── trace.py             # 全 Pipeline 追踪
├── retrieval/
│   ├── web.py               # SearXNG 搜索
│   ├── multi_source.py      # 知乎 / B站 / V2EX / GitHub
│   ├── vector.py            # FAISS + bge-small-zh 向量搜索
│   ├── rerank.py            # BGE-reranker-v2-m3 交叉编码器
│   ├── rewrite.py           # LLM 查询改写
│   ├── decompose.py         # LLM 查询分解 + 意图识别
│   ├── clean.py             # BeautifulSoup HTML 清洗
│   ├── chunker.py           # tiktoken 分块（400 tok, 50 重叠）
│   ├── budget.py            # Token 预算控制器
│   ├── source_weights.py    # 意图感知的来源可信度
│   ├── evidence.py          # 证据表抽取
│   ├── contradiction.py     # 跨来源矛盾检测
│   └── information_gain.py  # 信息增益提前停止
├── cache/
│   └── redis_cache.py       # Redis 精确匹配缓存
├── system_services/
│   ├── semantic_cache.py    # 语义缓存（Embedding 相似度）
│   ├── session_memory.py    # 会话记忆（Jaccard 去重）
│   └── feedback_logger.py   # 反馈指标 → Redis
├── observability/
│   ├── evaluator.py         # 语义评分
│   └── trace_store.py       # Redis + 文件双备份
├── infra/
│   └── model_loader.py      # 模型加载（预留）
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## 技术栈

| 组件 | 技术 |
|-----------|-----------|
| API 框架 | FastAPI + uvicorn |
| LLM | OpenAI 兼容 API（MiMo、GPT 等） |
| Embedding | BAAI/bge-small-zh-v1.5 (sentence-transformers) |
| Reranker | BAAI/bge-reranker-v2-m3 (cross-encoder) |
| 向量存储 | FAISS (CPU) |
| 缓存与会话 | Redis 7 |
| Token 计数 | tiktoken |
| HTML 解析 | BeautifulSoup4 |
| HTTP 客户端 | httpx |
| 元搜索 | SearXNG |
| 运行环境 | Python 3.11, PyTorch (CPU) |

## FAQ

<details>
<summary><strong>展开查看常见问题</strong></summary>

### 首次请求为什么慢？

首次请求需要加载两个 ML 模型（bge-small-zh-v1.5 embedding + BGE-reranker）。加载完成后模型常驻内存，后续请求很快。

### 内存占用多少？

约 4-6 GB，主要是两个 ML 模型。如果内存不够，可以考虑用更小的模型或者 GPU 加速。

### 支持哪些 LLM？

任何 OpenAI 兼容 API 都支持。默认配置是小米的 MiMo-v2.5-pro，也可以用 GPT-4、Claude（通过 API）、DeepSeek 等。

### 可以不部署 SearXNG 吗？

SearXNG 是搜索的核心组件，没有它就无法搜索。但你可以只用 `multi_source.py` 中的知乎/B站/V2EX/GitHub 搜索，去掉 SearXNG 部分。需要修改代码。

### 语义缓存的阈值 0.88 是怎么定的？

经验值。0.88 意味着两个查询的语义相似度很高才会命中缓存。太低会导致不相关的查询命中缓存（质量下降），太高会导致缓存几乎不会命中（失去意义）。

### 可以加新的搜索来源吗？

可以。在 `retrieval/multi_source.py` 中添加新的搜索方法，然后在 `search_all()` 中调用即可。

### 数据真的不出门吗？

除了 LLM API 调用（需要发送查询到 API 服务器），所有搜索、缓存、日志都在本地处理。如果你用本地 LLM（如 Ollama），则完全不出门。

</details>

## OpenClaw 集成

本项目提供了一个 OpenClaw Skill，可以让 AI 助手直接调用深度搜索：

```bash
# 安装 skill
npx clawhub install agentic-rag-cn
```

安装后，AI 助手在对话中遇到需要深度搜索的问题时，会自动调用本项目的 API。如果服务未运行，会自动回退到内置的 web_search。

Skill 页面：[clawhub.ai/nb-clh/agentic-rag-cn](https://clawhub.ai/nb-clh/agentic-rag-cn)

## 路线图

- [ ] 流式响应支持
- [ ] 多轮对话（带上下文）
- [ ] 自定义搜索源插件
- [ ] Web UI 仪表盘
- [ ] 查询分析仪表盘
- [ ] GPU 加速 Reranker
- [ ] 分布式部署（多节点）
- [ ] API 认证与限流
- [ ] 发布 Docker 镜像到 GHCR/DockerHub
- [ ] 标准数据集基准测试套件
- [ ] 深挖模式（低置信度自动补搜）
- [ ] 假设引导搜索
- [ ] 证据图
- [ ] 自适应策略引擎

## 贡献

欢迎贡献！以下是几种参与方式：

- **提交代码** — Fork 仓库，创建功能分支，提 Pull Request
- **报告 Bug** — 在 Issues 中提交 bug 报告
- **建议新功能** — 在 Issues 中提 feature request
- **改进文档** — 文档 PR 同样欢迎
- **添加搜索源** — 在 `retrieval/multi_source.py` 中添加新的搜索来源

### 开发环境搭建

```bash
# 克隆
git clone https://github.com/nb-clh/agentic-rag-cn.git
cd agentic-rag-cn

# 安装依赖
pip install -r requirements.txt

# 启动 Redis（必需）
docker run -d --name redis -p 6379:6379 redis:7-alpine

# 运行开发服务器
uvicorn app.main:app --reload --port 8000
```

### 需要帮助的领域

- 🌐 更多搜索来源（抖音、小红书、微博）
- 🎨 Web UI
- 📊 基准测试与评估
- 🐳 Kubernetes 部署清单
- 📖 文档与教程
- 🌍 国际化

## 许可证

[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)

你可以自由分享和改编本作品，但仅限非商业用途，需注明出处并采用相同许可证。

---

## 致谢

- [SearXNG](https://docs.searxng.org/) — 尊重隐私的元搜索引擎
- [BAAI/bge-small-zh-v1.5](https://huggingface.co/BAAI/bge-small-zh-v1.5) — 中文 Embedding 模型
- [BAAI/bge-reranker-v2-m3](https://huggingface.co/BAAI/bge-reranker-v2-m3) — 交叉编码器 Reranker
- [FastAPI](https://fastapi.tiangolo.com/) — 现代 Python Web 框架

# 更新日志

本项目所有重要更改都会记录在此文件。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [1.0.0] - 2025-05-20

### 新增
- 11 源并发搜索（SearXNG 7 引擎 + 知乎/B站/V2EX/GitHub）
- 完整 RAG 流水线（16 步自动化处理）
- 查询改写（Query Rewrite）— 同义替换，≤5 个子查询
- 查询拆解（Query Decompose）— 复杂问题分解为独立子问题
- 意图识别（Intent Recognition）— 5 种意图类型
- 语义缓存（Semantic Cache）— 余弦相似度 ≥ 0.88 命中
- 信息增益检测（Information Gain）— 无新信息提前停止
- 内容清洗（Content Clean）— HTML → 纯文本
- 分块（Chunking）— 400 token/块，50 overlap
- 重排序（Rerank）— BGE-reranker-v2-m3 交叉编码器
- 来源权重（Source Weights）— 按意图动态调整可信度
- 预算控制（Budget Control）— 8K token / 8 chunks / 5 sources
- 证据表提取（Evidence Table）— 结构化论点 + 来源 + 置信度
- 矛盾检测（Contradiction Detection）— 跨来源冲突检测
- 反馈日志（Feedback Logger）— 完整指标记录到 Redis
- 语义评估（Evaluation）— 答案质量 0-1 评分
- 全链路追踪（Full Trace）— 每步执行记录
- Docker Compose 一键部署
- SearXNG 预配置（7 个中文搜索引擎）
- 一键部署脚本（setup.sh）
- HuggingFace 国内镜像支持

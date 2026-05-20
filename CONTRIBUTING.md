# 贡献指南

感谢你对 Agentic RAG-CN 项目的关注！以下是参与贡献的方式。

## 如何贡献

### 提交代码

1. Fork 本仓库
2. 创建你的功能分支：`git checkout -b feature/your-feature`
3. 提交你的改动：`git commit -m 'feat: add some feature'`
4. 推送到你的分支：`git push origin feature/your-feature`
5. 创建 Pull Request

### 报告 Bug

在 [Issues](https://github.com/nb-clh/agentic-rag-cn/issues) 中提交 Bug 报告，请包含：

- 问题描述
- 复现步骤
- 期望行为 vs 实际行为
- 环境信息（OS、Docker 版本等）
- 相关日志

### 功能建议

在 [Issues](https://github.com/nb-clh/agentic-rag-cn/issues) 中提交功能建议，请说明：

- 你希望添加什么功能
- 为什么需要这个功能
- 你期望的实现方式

## 开发环境搭建

```bash
# 1. Fork 并克隆
git clone https://github.com/your-username/agentic-rag-cn.git
cd agentic-rag-cn

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动 Redis（必须）
docker run -d --name redis -p 6379:6379 redis:7-alpine

# 4. 启动 SearXNG（必须）
docker run -d --name searxng -p 8080:8080 \
  -v $(pwd)/searxng/settings.yml:/etc/searxng/settings.yml \
  searxng/searxng

# 5. 配置环境变量
cp .env.example .env
# 编辑 .env，填入你的 API Key

# 6. 启动开发服务器
uvicorn app.main:app --reload --port 8000
```

## 代码风格

- **Python:** 遵循 PEP 8 规范
- **命名:** 函数和变量用 `snake_case`，类用 `PascalCase`
- **注释:** 关键逻辑必须有注释，复杂算法需要文档说明
- **类型提示:** 公共函数必须有类型提示
- **docstring:** 公共函数和类必须有 docstring

### 示例

```python
async def search_all(query: str, max_results: int = 10) -> list[dict]:
    """并发搜索所有来源，返回去重后的结果列表。

    Args:
        query: 搜索查询
        max_results: 每个来源的最大结果数

    Returns:
        去重后的搜索结果列表
    """
    # 实现...
```

## 提交规范

使用 [Conventional Commits](https://www.conventionalcommits.org/) 格式：

```
<type>: <description>

[optional body]
[optional footer]
```

类型：
- `feat:` 新功能
- `fix:` 修复 Bug
- `docs:` 文档更新
- `style:` 代码格式调整（不影响逻辑）
- `refactor:` 重构
- `perf:` 性能优化
- `test:` 测试
- `chore:` 构建/工具链

## Pull Request 规范

- 一个 PR 只做一件事
- PR 标题清晰描述改动内容
- 包含必要的测试
- 更新相关文档
- 确保现有测试通过

## Issue 模板

### Bug 报告

```
## 描述
简要描述问题

## 复现步骤
1. ...
2. ...

## 期望行为
...

## 实际行为
...

## 环境
- OS:
- Docker:
- 项目版本:

## 日志
```

### 功能建议

```
## 描述
简要描述建议的功能

## 使用场景
为什么需要这个功能

## 期望实现
你期望的实现方式

## 备注
其他相关信息
```

## 需要帮助的方向

- 🌐 更多搜索来源（抖音、小红书、微博）
- 🎨 Web UI
- 📊 性能基准测试
- 🐳 Kubernetes 部署
- 📖 文档和教程
- 🌍 国际化

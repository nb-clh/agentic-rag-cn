#!/bin/bash
# ============================================
# Agentic RAG-CN - 一键部署脚本
# ============================================
# 用法: curl -sSL https://raw.githubusercontent.com/nb-clh/agentic-rag-cn/main/setup.sh | bash
# 或者: git clone https://github.com/nb-clh/agentic-rag-cn.git && cd agentic-rag-cn && bash setup.sh

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

REPO_URL="https://github.com/nb-clh/agentic-rag-cn.git"
PROJECT_DIR="agentic-rag-cn"

# --- 工具函数 ---
info() { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# --- 步骤 1: 检查 Docker ---
echo ""
echo "=========================================="
echo "  Agentic RAG-CN 一键部署"
echo "=========================================="
echo ""

info "检查 Docker 环境..."

if ! command -v docker &> /dev/null; then
    error "未找到 Docker。请先安装 Docker: https://docs.docker.com/get-docker/"
fi
success "Docker 已安装: $(docker --version)"

if ! docker compose version &> /dev/null && ! docker-compose --version &> /dev/null; then
    error "未找到 Docker Compose。请先安装: https://docs.docker.com/compose/install/"
fi
success "Docker Compose 已安装"

# --- 步骤 2: 克隆项目 ---
echo ""
info "克隆项目..."

if [ -d "$PROJECT_DIR" ]; then
    warn "目录 $PROJECT_DIR 已存在，跳过克隆"
    cd "$PROJECT_DIR"
else
    git clone "$REPO_URL"
    cd "$PROJECT_DIR"
    success "项目已克隆到 $PROJECT_DIR"
fi

# --- 步骤 3: 配置环境变量 ---
echo ""
info "配置环境变量..."

if [ -f ".env" ]; then
    warn ".env 文件已存在，跳过创建"
else
    cp .env.example .env
    success "已从 .env.example 创建 .env"
fi

# 提示用户填写 API Key
echo ""
echo -e "${YELLOW}========================================${NC}"
echo -e "${YELLOW}  请编辑 .env 文件填入你的配置${NC}"
echo -e "${YELLOW}========================================${NC}"
echo ""
echo "必填项:"
echo "  OPENAI_API_KEY     - 你的 LLM API Key"
echo ""
echo "可选项（已有默认值）:"
echo "  OPENAI_BASE_URL    - API 地址（默认 OpenAI）"
echo "  LLM_MODEL          - 模型名称（默认 gpt-4o-mini）"
echo "  HF_ENDPOINT        - HuggingFace 镜像（国内用户建议用 hf-mirror.com）"
echo ""

# 检测是否在交互模式
if [ -t 0 ]; then
    read -p "是否现在编辑 .env？[y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        ${EDITOR:-vi} .env
    else
        info "请稍后手动编辑 .env 文件"
    fi
else
    info "非交互模式，请手动编辑 .env 文件"
fi

# 加载 .env
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
fi

# 检查 API Key
if [ "$OPENAI_API_KEY" = "your_api_key_here" ] || [ -z "$OPENAI_API_KEY" ]; then
    warn "OPENAI_API_KEY 未设置或仍为默认值，服务启动后可能无法正常工作"
fi

# --- 步骤 4: 启动服务 ---
echo ""
info "启动服务..."

if docker compose version &> /dev/null; then
    docker compose up -d
else
    docker-compose up -d
fi

success "服务已启动"

# --- 步骤 5: 等待健康检查 ---
echo ""
info "等待服务就绪..."

MAX_RETRIES=30
RETRY_INTERVAL=2

for i in $(seq 1 $MAX_RETRIES); do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        success "API 服务就绪"
        break
    fi
    if [ $i -eq $MAX_RETRIES ]; then
        warn "API 服务启动超时，请检查日志: docker compose logs api"
    fi
    sleep $RETRY_INTERVAL
done

# --- 步骤 6: 完成 ---
echo ""
echo "=========================================="
echo -e "  ${GREEN}部署完成！${NC}"
echo "=========================================="
echo ""
echo "服务地址:"
echo "  API:     http://localhost:8000"
echo "  SearXNG: http://localhost:8080"
echo "  Redis:   localhost:6379"
echo ""
echo "测试查询:"
echo '  curl -s http://localhost:8000/query \'
echo '    -H "Content-Type: application/json" \'
echo '    -d '"'"'{"query": "什么是 RAG"}'"'"' | python3 -m json.tool'
echo ""
echo "查看日志:"
echo "  docker compose logs -f api"
echo ""
echo "停止服务:"
echo "  docker compose down"
echo ""

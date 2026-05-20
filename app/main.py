import os
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.api import router
import redis
from core.orchestrator import Orchestrator


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: 只初始化轻量级组件，模型延迟加载
    redis_client = redis.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        decode_responses=True
    )
    app.state.orchestrator = Orchestrator(redis_client)
    yield
    # Shutdown
    redis_client.close()


app = FastAPI(title="Agentic RAG-CN", version="1.0.0", lifespan=lifespan)
app.include_router(router)


@app.get("/health")
async def health():
    return {"status": "ok"}

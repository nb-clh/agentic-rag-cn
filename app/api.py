from fastapi import APIRouter, Request
from core.trace import Trace

router = APIRouter()


@router.post("/query")
async def query(body: dict, request: Request):
    q = body.get("query", "")
    if not q:
        return {"error": "query is required"}

    orchestrator = request.app.state.orchestrator
    trace = Trace(query=q)
    result = await orchestrator.run(q, trace=trace)
    return result

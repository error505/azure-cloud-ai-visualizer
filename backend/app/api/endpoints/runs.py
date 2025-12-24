# app/api/endpoints/runs.py
import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.obs.tracing import tracer

router = APIRouter()

@router.get("/runs/{run_id}/events")
async def stream_run(run_id: str):
    async def event_source():
        persisted = await tracer.read_persisted(run_id)
        sent_any = False
        for payload in persisted:
            sent_any = True
            yield f"data: {json.dumps(payload)}\n\n"

        if tracer.is_active(run_id):
            async for item in tracer.stream(run_id):
                sent_any = True
                yield f"data: {item}\n\n"   # SSE format

        if not sent_any:
            yield "event: end\ndata: {}\n\n"

    return StreamingResponse(event_source(), media_type="text/event-stream")

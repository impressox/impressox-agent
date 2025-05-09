from typing import Dict, Any
import json
import time
import logging
from contextlib import asynccontextmanager
from fastapi import (
    FastAPI,
    Request,
    BackgroundTasks
)
from pydantic import BaseModel
from langfuse.callback import CallbackHandler
from sse_starlette.sse import EventSourceResponse
from fastapi.middleware.cors import CORSMiddleware

from app.agents.agent_orchestrator import graph
from app.configs import app_configs

logger = logging.getLogger("uvicorn.error")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting the app ...")
    yield
    logger.warning("Shutting down the app ...")

app = FastAPI(
    root_path = app_configs.API_CONF["root_path"],
    lifespan = lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.get("/", tags=["Health Check"])
@app.get("/healthz", tags=["Health Check"])
def get_heathz() -> Dict[str, str]:
    return {"status": "ok"}

class PayloadRequest(BaseModel):
    assistant_id: str = ""
    input: Dict[str, Any] = {}
    config: Dict[str, Any] = {}
    stream_mode: str = "events"
    stream_subgraphs: bool = False
    multitask_strategy: str = "enqueue"

from langchain_core.load.serializable import Serializable

def parse_start_event(event):
    if isinstance(event, Serializable):
        return event.__dict__
    elif isinstance(event, dict):
        return {k: parse_start_event(v) for k, v in event.items()}
    elif isinstance(event, list):
        return [parse_start_event(item) for item in event]
    elif isinstance(event, tuple):
        return tuple(parse_start_event(item) for item in event)
    else:
        return event

async def stream_from_agent(
    input,
    config,
    log_data,
):
    t1 = time.time()
    events = []
    run_idx = 0
    async for event in graph.astream_events(
        input,
        config = config,
        version = "v2",
    ):
        t = time.time() - t1
        event = parse_start_event(event)
        if isinstance(event, dict):
            if event.get("metadata", {}).get("langgraph_node", "") in ["supervisor", "tool_choice"]:
                continue
        if event["event"] == "on_chat_model_start":
            log_data["runs"].append({
                "run": run_idx,
                "start": t,
            })
        elif event["event"] == "on_chat_model_stream":
            if not "ttft" in log_data["runs"][-1]:
                log_data["runs"][-1]["ttft"] = t
        elif event["event"] == "on_chat_model_end":
            log_data["runs"][-1]["stream"] = t - log_data["runs"][-1]["ttft"]
            log_data["runs"][-1]["end"] = t
            run_idx += 1
        
        events.append(
            {
                "time": t,
                "event": event["event"]
            }
        )
        yield json.dumps(event)
    log_data["events"] = events

@app.post("/threads/{session_id}/runs/stream", tags=["Run with stream"])
async def run_stream(
    session_id: str,
    request: Request,
    request_body: PayloadRequest,
    background_tasks: BackgroundTasks,
):
    logger.info(f"Received request for session {session_id}:\n{request_body.__dict__}")
    input = request_body.input
    config = request_body.config
    
    log_data = {
        "session_id": session_id,
        "input": input.copy(),
        "config": config.copy(),
        "runs": []
    }
    config["thread_id"] = session_id
    langfuse_config = app_configs.get_langfuse_config()
    langfuse_handler = CallbackHandler(
        secret_key = langfuse_config["secret_key"],
        public_key = langfuse_config["public_key"],
        host = langfuse_config["host"],
        session_id=session_id
    )
    config["callbacks"] = [langfuse_handler]
    config["recursion_limit"] = 15
    
    return EventSourceResponse(stream_from_agent(input, config, log_data), media_type = "text/plain")

@app.post("/threads/{session_id}/runs", tags=["Run without stream"])
async def run_non_stream(
    session_id: str,
    request_body: PayloadRequest,
):
    logger.info(f"[non-stream] Received request for session {session_id}:\n{request_body.__dict__}")
    input = request_body.input
    config = request_body.config

    # Optionally add callback, etc.
    langfuse_config = app_configs.get_langfuse_config()
    langfuse_handler = CallbackHandler(
        secret_key = langfuse_config["secret_key"],
        public_key = langfuse_config["public_key"],
        host = langfuse_config["host"],
        session_id=session_id
    )
    config["thread_id"] = session_id
    config["callbacks"] = [langfuse_handler]
    config["recursion_limit"] = 15

    # Call graph directly without streaming
    result = await graph.ainvoke(input, config=config)

    return {"result": result}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api:app",
        host = "0.0.0.0",
        port = 8564,
    )

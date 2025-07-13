import asyncio
import time
import uuid
from contextlib import asynccontextmanager
from typing import Dict, Any

import structlog
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .workflow import create_research_workflow
from .models import ResearchRequest, ResearchResponse, ResearchState

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Python LangGraph benchmark server")
    yield
    logger.info("Stopping Python LangGraph benchmark server")


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

workflow = create_research_workflow()


@app.get("/health")
async def health():
    return "OK"


@app.post("/research")
async def research(request: ResearchRequest) -> ResearchResponse:
    start_time = time.time()
    session_id = str(uuid.uuid4())
    
    logger.info("starting_research_workflow", session_id=session_id, topic=request.topic)
    
    try:
        initial_state = ResearchState(
            topic=request.topic,
            questions=[],
            research_results=[],
            summary="",
            report="",
            task_times={}
        )
        
        config = {"configurable": {"thread_id": session_id}}
        
        final_state = await workflow.ainvoke(initial_state, config)
        
        total_time_ms = int((time.time() - start_time) * 1000)
        
        logger.info(
            "workflow_completed",
            session_id=session_id,
            total_time_ms=total_time_ms,
            task_times=final_state["task_times"]
        )
        
        return ResearchResponse(
            session_id=session_id,
            topic=request.topic,
            questions=final_state["questions"],
            summary=final_state["summary"],
            report=final_state["report"],
            total_time_ms=total_time_ms,
            task_times=final_state["task_times"]
        )
        
    except Exception as e:
        logger.error("workflow_error", session_id=session_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import structlog
    
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.dev.ConsoleRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=3001,
        reload=True,
        log_config=None
    )
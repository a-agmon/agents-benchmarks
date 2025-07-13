from typing import List, Dict, TypedDict
from pydantic import BaseModel


class ResearchRequest(BaseModel):
    topic: str


class ResearchResponse(BaseModel):
    session_id: str
    topic: str
    questions: List[str]
    summary: str
    report: str
    total_time_ms: int
    task_times: Dict[str, int]


class Finding(TypedDict):
    title: str
    url: str
    content: str


class ResearchResult(TypedDict):
    question: str
    findings: List[Finding]


class ResearchState(TypedDict):
    topic: str
    questions: List[str]
    research_results: List[ResearchResult]
    summary: str
    report: str
    task_times: Dict[str, int]
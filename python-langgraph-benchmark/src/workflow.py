import asyncio
import time
from typing import List

import structlog
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph
from tavily import TavilyClient

from .models import ResearchState, ResearchResult, Finding
from .tools import TavilySearchTool

logger = structlog.get_logger()


def create_research_workflow():
    workflow = StateGraph(ResearchState)
    
    workflow.add_node("extract_questions", extract_questions)
    workflow.add_node("research", research)
    workflow.add_node("summarize", summarize)
    workflow.add_node("generate_report", generate_report)
    
    workflow.add_edge("extract_questions", "research")
    workflow.add_edge("research", "summarize")
    workflow.add_edge("summarize", "generate_report")
    
    workflow.set_entry_point("extract_questions")
    
    return workflow.compile()


async def extract_questions(state: ResearchState) -> ResearchState:
    start_time = time.time()
    logger.info("starting_question_extraction", topic=state["topic"])
    
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    
    messages = [
        SystemMessage(content="""You are a research assistant. Generate 3-5 specific research questions about the given topic.

Requirements:
- Questions should be factual and answerable through web research
- Questions should cover different aspects of the topic
- Questions should be clear and well-defined
- Format: Return only the questions, one per line, no numbering or bullets"""),
        HumanMessage(content=f'Generate research questions about: "{state["topic"]}"')
    ]
    
    response = await llm.ainvoke(messages)
    
    questions = [
        line.strip() 
        for line in response.content.split('\n') 
        if line.strip()
    ]
    
    elapsed_ms = int((time.time() - start_time) * 1000)
    logger.info("questions_extracted", count=len(questions), elapsed_ms=elapsed_ms)
    
    state["questions"] = questions
    state["task_times"]["extract_questions"] = elapsed_ms
    
    return state


async def research(state: ResearchState) -> ResearchState:
    start_time = time.time()
    logger.info("starting_research", questions_count=len(state["questions"]))
    
    async def research_question(question: str) -> ResearchResult:
        logger.info("researching_question", question=question)
        
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        tavily_tool = TavilySearchTool()
        
        llm_with_tools = llm.bind_tools([tavily_tool])
        
        messages = [
            SystemMessage(content="""Search for information to answer the research question.
Use the tavily_search tool to find relevant information. Search for specific, factual information that directly addresses the question."""),
            HumanMessage(content=f'Research this question: "{question}"')
        ]
        
        response = await llm_with_tools.ainvoke(messages)
        
        findings = []
        if response.tool_calls:
            for tool_call in response.tool_calls:
                if tool_call["name"] == "tavily_search":
                    search_results = await tavily_tool.ainvoke(tool_call["args"])
                    
                    for result in search_results.get("results", [])[:3]:
                        findings.append(Finding(
                            title=result.get("title", ""),
                            url=result.get("url", ""),
                            content=result.get("content", "")
                        ))
        
        return ResearchResult(question=question, findings=findings)
    
    research_tasks = [research_question(q) for q in state["questions"]]
    results = await asyncio.gather(*research_tasks)
    
    elapsed_ms = int((time.time() - start_time) * 1000)
    logger.info("research_completed", results_count=len(results), elapsed_ms=elapsed_ms)
    
    state["research_results"] = results
    state["task_times"]["research"] = elapsed_ms
    
    return state


async def summarize(state: ResearchState) -> ResearchState:
    start_time = time.time()
    logger.info("starting_summarization")
    
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    
    findings_text = "\n\n".join([
        f"Question: {result['question']}\nFindings:\n" + 
        "\n".join([
            f"- {finding['title']} ({finding['url']}): {finding['content']}"
            for finding in result['findings']
        ])
        for result in state["research_results"]
    ])
    
    messages = [
        SystemMessage(content="""You are a research assistant. Summarize the key findings from this research.

Requirements:
- Create a concise summary (3-5 paragraphs) of the most important findings
- Focus on facts and insights that directly relate to the topic
- Organize information logically
- Use clear, professional language
- Do not include URLs or citations in the summary"""),
        HumanMessage(content=f"""Summarize the research findings about "{state['topic']}":

{findings_text}""")
    ]
    
    response = await llm.ainvoke(messages)
    
    elapsed_ms = int((time.time() - start_time) * 1000)
    logger.info("summarization_completed", summary_length=len(response.content), elapsed_ms=elapsed_ms)
    
    state["summary"] = response.content
    state["task_times"]["summarize"] = elapsed_ms
    
    return state


async def generate_report(state: ResearchState) -> ResearchState:
    start_time = time.time()
    logger.info("starting_report_generation")
    
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    
    questions_text = "\n- ".join(state["questions"])
    
    raw_data_text = "\n\n".join([
        f"Question: {result['question']}\nSources:\n" + 
        "\n".join([
            f"- {finding['title']} ({finding['url']})\n  {finding['content']}"
            for finding in result['findings']
        ])
        for result in state["research_results"]
    ])
    
    messages = [
        SystemMessage(content="""You are a research assistant. Create a comprehensive research report.

Requirements:
- Create a well-structured markdown report
- Include an executive summary
- Organize findings by research question
- Add a conclusion section
- Include citations with URLs where appropriate
- Use proper markdown formatting (headers, lists, etc.)
- Make it professional and comprehensive"""),
        HumanMessage(content=f"""Create a research report about "{state['topic']}" based on:

Research Questions:
- {questions_text}

Summary of Findings:
{state['summary']}

Raw Research Data:
{raw_data_text}""")
    ]
    
    response = await llm.ainvoke(messages)
    
    elapsed_ms = int((time.time() - start_time) * 1000)
    logger.info("report_generated", report_length=len(response.content), elapsed_ms=elapsed_ms)
    
    state["report"] = response.content
    state["task_times"]["generate_report"] = elapsed_ms
    
    return state
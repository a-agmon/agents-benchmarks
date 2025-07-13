import os
from typing import Type, Dict, Any

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from tavily import AsyncTavilyClient


class TavilySearchInput(BaseModel):
    query: str = Field(description="The search query")


class TavilySearchTool(BaseTool):
    name: str = "tavily_search"
    description: str = "Search the web for information using Tavily search engine"
    args_schema: Type[BaseModel] = TavilySearchInput
    
    def _run(self, query: str) -> Dict[str, Any]:
        raise NotImplementedError("Use ainvoke for async operation")
    
    async def _arun(self, query: str) -> Dict[str, Any]:
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            raise ValueError("TAVILY_API_KEY environment variable not set")
        
        client = AsyncTavilyClient(api_key=api_key)
        
        response = await client.search(
            query=query,
            max_results=5,
            search_depth="advanced",
            include_raw_content=True
        )
        
        return response
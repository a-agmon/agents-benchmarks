use crate::models::{TavilySearchRequest, TavilySearchResponse};
use rig::tool::Tool;
use rig::completion::ToolDefinition;
use serde::{Deserialize, Serialize};
use serde_json::json;
use std::env;

#[derive(Debug)]
pub struct TavilyError(String);

impl std::fmt::Display for TavilyError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "Tavily error: {}", self.0)
    }
}

impl std::error::Error for TavilyError {}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TavilySearch;

#[derive(Debug, Serialize, Deserialize)]
pub struct TavilySearchArgs {
    pub query: String,
}

impl Tool for TavilySearch {
    const NAME: &'static str = "tavily_search";

    type Error = TavilyError;
    type Args = TavilySearchArgs;
    type Output = String;

    async fn definition(&self, _prompt: String) -> ToolDefinition {
        ToolDefinition {
            name: Self::NAME.to_string(),
            description: "Search the web for information using Tavily search engine".to_string(),
            parameters: json!({
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query"
                    }
                },
                "required": ["query"]
            }),
        }
    }

    async fn call(&self, args: Self::Args) -> Result<Self::Output, Self::Error> {
        let api_key = env::var("TAVILY_API_KEY")
            .map_err(|_| TavilyError("TAVILY_API_KEY not set".to_string()))?;

        let client = reqwest::Client::new();
        let request = TavilySearchRequest {
            query: args.query,
            max_results: 5,
            search_depth: "advanced".to_string(),
            include_raw_content: true,
        };

        let response = client
            .post("https://api.tavily.com/search")
            .header("api-key", api_key)
            .json(&request)
            .send()
            .await
            .map_err(|e| TavilyError(format!("Request failed: {}", e)))?;

        let search_response: TavilySearchResponse = response
            .json()
            .await
            .map_err(|e| TavilyError(format!("Failed to parse response: {}", e)))?;

        let formatted_results = search_response
            .results
            .iter()
            .map(|r| format!("Title: {}\nURL: {}\nContent: {}\n", r.title, r.url, r.content))
            .collect::<Vec<_>>()
            .join("\n---\n");

        Ok(formatted_results)
    }
}
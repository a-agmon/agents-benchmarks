use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ResearchRequest {
    pub topic: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ResearchResponse {
    pub session_id: String,
    pub topic: String,
    pub questions: Vec<String>,
    pub summary: String,
    pub report: String,
    pub total_time_ms: u64,
    pub task_times: HashMap<String, u64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ResearchContext {
    pub topic: String,
    pub questions: Vec<String>,
    pub research_results: Vec<ResearchResult>,
    pub summary: String,
    pub report: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ResearchResult {
    pub question: String,
    pub findings: Vec<Finding>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Finding {
    pub title: String,
    pub url: String,
    pub content: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TavilySearchRequest {
    pub query: String,
    pub max_results: i32,
    pub search_depth: String,
    pub include_raw_content: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TavilySearchResponse {
    pub results: Vec<TavilyResult>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TavilyResult {
    pub title: String,
    pub url: String,
    pub content: String,
    pub score: f64,
}
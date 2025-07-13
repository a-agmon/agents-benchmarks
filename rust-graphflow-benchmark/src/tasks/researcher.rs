use crate::models::{Finding, ResearchContext, ResearchResult};
use crate::tools::{llm::get_llm_with_tool, tavily::TavilySearch};
use async_trait::async_trait;
use futures::future::join_all;
use graph_flow::{Context, GraphError, NextAction, Task, TaskResult};
use rig::completion::Prompt;
use tracing::{info, instrument};

pub struct ResearcherTask;

#[async_trait]
impl Task for ResearcherTask {
    fn id(&self) -> &str {
        "researcher"
    }

    #[instrument(skip(self, context))]
    async fn run(&self, context: Context) -> Result<TaskResult, GraphError> {
        let start_time = std::time::Instant::now();
        info!("Starting research task");

        let mut research_context: ResearchContext = context
            .get("research_context")
            .await
            .ok_or_else(|| GraphError::ContextError("Research context not found".to_string()))?;

        let search_futures = research_context.questions.iter().map(|question| {
            let question = question.clone();
            async move {
                info!("Researching question: {}", question);
                research_question(question).await
            }
        });

        let results = join_all(search_futures).await;
        
        research_context.research_results = results
            .into_iter()
            .filter_map(|r| r.ok())
            .collect();

        info!("Completed research for {} questions", research_context.research_results.len());
        context.set("research_context", research_context).await;

        let elapsed = start_time.elapsed().as_millis() as u64;
        let mut task_times: std::collections::HashMap<String, u64> = 
            context.get("task_times").await.unwrap_or_default();
        task_times.insert("researcher".to_string(), elapsed);
        context.set("task_times", task_times).await;

        Ok(TaskResult::new(
            Some("Research completed successfully".to_string()),
            NextAction::ContinueAndExecute,
        ))
    }
}

async fn research_question(question: String) -> anyhow::Result<ResearchResult> {
    let tavily = TavilySearch;
    let agent = get_llm_with_tool(tavily).map_err(anyhow::Error::from)?;

    let prompt = format!(
        r#"Search for information to answer this research question: "{}"

Use the tavily_search tool to find relevant information. Search for specific, factual information that directly addresses the question."#,
        question
    );

    let response = agent.prompt(&prompt).await.map_err(|e| anyhow::anyhow!("Prompt error: {}", e))?;
    
    let findings = parse_search_results(&response);

    Ok(ResearchResult {
        question,
        findings,
    })
}

fn parse_search_results(response: &str) -> Vec<Finding> {
    response
        .split("---")
        .filter_map(|section| {
            let lines: Vec<&str> = section.trim().lines().collect();
            if lines.len() >= 3 {
                let title = lines.iter()
                    .find(|l| l.starts_with("Title:"))
                    .map(|l| l.trim_start_matches("Title:").trim())
                    .unwrap_or("")
                    .to_string();
                
                let url = lines.iter()
                    .find(|l| l.starts_with("URL:"))
                    .map(|l| l.trim_start_matches("URL:").trim())
                    .unwrap_or("")
                    .to_string();
                
                let content = lines.iter()
                    .find(|l| l.starts_with("Content:"))
                    .map(|l| l.trim_start_matches("Content:").trim())
                    .unwrap_or("")
                    .to_string();

                if !title.is_empty() && !url.is_empty() {
                    Some(Finding { title, url, content })
                } else {
                    None
                }
            } else {
                None
            }
        })
        .take(3)
        .collect()
}
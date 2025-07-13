use crate::models::ResearchContext;
use crate::tools::llm::get_llm;
use async_trait::async_trait;
use graph_flow::{Context, GraphError, NextAction, Task, TaskResult};
use rig::completion::Prompt;
use tracing::{info, instrument};

pub struct SummarizerTask;

#[async_trait]
impl Task for SummarizerTask {
    fn id(&self) -> &str {
        "summarizer"
    }

    #[instrument(skip(self, context))]
    async fn run(&self, context: Context) -> Result<TaskResult, GraphError> {
        let start_time = std::time::Instant::now();
        info!("Starting summarization task");

        let mut research_context: ResearchContext = context
            .get("research_context")
            .await
            .ok_or_else(|| GraphError::ContextError("Research context not found".to_string()))?;

        let findings_text = research_context
            .research_results
            .iter()
            .map(|result| {
                format!(
                    "Question: {}\nFindings:\n{}",
                    result.question,
                    result
                        .findings
                        .iter()
                        .map(|f| format!("- {} ({}): {}", f.title, f.url, f.content))
                        .collect::<Vec<_>>()
                        .join("\n")
                )
            })
            .collect::<Vec<_>>()
            .join("\n\n");

        let prompt = format!(
            r#"You are a research assistant. Summarize the key findings from this research about "{}":

{}

Requirements:
- Create a concise summary (3-5 paragraphs) of the most important findings
- Focus on facts and insights that directly relate to the topic
- Organize information logically
- Use clear, professional language
- Do not include URLs or citations in the summary"#,
            research_context.topic, findings_text
        );

        let agent = get_llm().map_err(GraphError::Other)?;
        let summary = agent.prompt(&prompt).await.map_err(|e| GraphError::Other(anyhow::anyhow!("Prompt error: {}", e)))?;

        info!("Generated summary with {} characters", summary.len());
        research_context.summary = summary;
        context.set("research_context", research_context).await;

        let elapsed = start_time.elapsed().as_millis() as u64;
        let mut task_times: std::collections::HashMap<String, u64> = 
            context.get("task_times").await.unwrap_or_default();
        task_times.insert("summarizer".to_string(), elapsed);
        context.set("task_times", task_times).await;

        Ok(TaskResult::new(
            Some("Summary generated successfully".to_string()),
            NextAction::ContinueAndExecute,
        ))
    }
}
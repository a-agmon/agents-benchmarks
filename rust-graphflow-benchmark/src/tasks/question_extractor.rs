use crate::models::ResearchContext;
use crate::tools::llm::get_llm;
use async_trait::async_trait;
use graph_flow::{Context, GraphError, NextAction, Task, TaskResult};
use rig::completion::Prompt;
use tracing::{info, instrument};

pub struct QuestionExtractorTask;

#[async_trait]
impl Task for QuestionExtractorTask {
    fn id(&self) -> &str {
        "question_extractor"
    }

    #[instrument(skip(self, context))]
    async fn run(&self, context: Context) -> Result<TaskResult, GraphError> {
        let start_time = std::time::Instant::now();
        info!("Starting question extraction task");

        let mut research_context: ResearchContext = context
            .get("research_context")
            .await
            .ok_or_else(|| GraphError::ContextError("Research context not found".to_string()))?;

        let prompt = format!(
            r#"You are a research assistant. Generate 3-5 specific research questions about the following topic: "{}"

Requirements:
- Questions should be factual and answerable through web research
- Questions should cover different aspects of the topic
- Questions should be clear and well-defined
- Format: Return only the questions, one per line, no numbering or bullets"#,
            research_context.topic
        );

        let agent = get_llm().map_err(GraphError::Other)?;
        let response = agent.prompt(&prompt).await.map_err(|e| GraphError::Other(anyhow::anyhow!("Prompt error: {}", e)))?;

        let questions: Vec<String> = response
            .split('\n')
            .filter(|line| !line.trim().is_empty())
            .map(|line| line.trim().to_string())
            .collect();

        info!("Extracted {} research questions", questions.len());
        research_context.questions = questions;
        context.set("research_context", research_context).await;

        let elapsed = start_time.elapsed().as_millis() as u64;
        let mut task_times: std::collections::HashMap<String, u64> = 
            context.get("task_times").await.unwrap_or_default();
        task_times.insert("question_extractor".to_string(), elapsed);
        context.set("task_times", task_times).await;

        Ok(TaskResult::new(
            Some("Questions extracted successfully".to_string()),
            NextAction::ContinueAndExecute,
        ))
    }
}
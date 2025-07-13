use crate::models::ResearchContext;
use crate::tools::llm::get_llm;
use async_trait::async_trait;
use graph_flow::{Context, GraphError, NextAction, Task, TaskResult};
use rig::completion::Prompt;
use tracing::{info, instrument};

pub struct ReporterTask;

#[async_trait]
impl Task for ReporterTask {
    fn id(&self) -> &str {
        "reporter"
    }

    #[instrument(skip(self, context))]
    async fn run(&self, context: Context) -> Result<TaskResult, GraphError> {
        let start_time = std::time::Instant::now();
        info!("Starting report generation task");

        let mut research_context: ResearchContext = context
            .get("research_context")
            .await
            .ok_or_else(|| GraphError::ContextError("Research context not found".to_string()))?;

        let prompt = format!(
            r#"You are a research assistant. Create a comprehensive research report about "{}" based on the following information:

Research Questions:
{}

Summary of Findings:
{}

Raw Research Data:
{}

Requirements:
- Create a well-structured markdown report
- Include an executive summary
- Organize findings by research question
- Add a conclusion section
- Include citations with URLs where appropriate
- Use proper markdown formatting (headers, lists, etc.)
- Make it professional and comprehensive"#,
            research_context.topic,
            research_context.questions.join("\n- "),
            research_context.summary,
            format_research_results(&research_context)
        );

        let agent = get_llm().map_err(GraphError::Other)?;
        let report = agent.prompt(&prompt).await.map_err(|e| GraphError::Other(anyhow::anyhow!("Prompt error: {}", e)))?;

        info!("Generated report with {} characters", report.len());
        research_context.report = report;
        context.set("research_context", research_context).await;

        let elapsed = start_time.elapsed().as_millis() as u64;
        let mut task_times: std::collections::HashMap<String, u64> = 
            context.get("task_times").await.unwrap_or_default();
        task_times.insert("reporter".to_string(), elapsed);
        context.set("task_times", task_times).await;

        Ok(TaskResult::new(
            Some("Report generated successfully".to_string()),
            NextAction::End,
        ))
    }
}

fn format_research_results(context: &ResearchContext) -> String {
    context
        .research_results
        .iter()
        .map(|result| {
            format!(
                "Question: {}\nSources:\n{}",
                result.question,
                result
                    .findings
                    .iter()
                    .map(|f| format!("- {} ({})\n  {}", f.title, f.url, f.content))
                    .collect::<Vec<_>>()
                    .join("\n")
            )
        })
        .collect::<Vec<_>>()
        .join("\n\n")
}
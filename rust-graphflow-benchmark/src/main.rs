mod models;
mod tasks;
mod tools;

use anyhow::Result;
use axum::{
    extract::State,
    http::StatusCode,
    response::Json,
    routing::{get, post},
    Router,
};
use graph_flow::{FlowRunner, GraphBuilder, Session, SessionStorage};
use models::{ResearchContext, ResearchRequest, ResearchResponse};
use std::sync::Arc;
use tasks::{QuestionExtractorTask, ReporterTask, ResearcherTask, SummarizerTask};
use tower_http::cors::CorsLayer;
use tracing::{info, instrument};
use uuid::Uuid;

#[derive(Clone)]
struct AppState {
    runner: Arc<FlowRunner>,
    storage: Arc<dyn SessionStorage>,
}

#[tokio::main]
async fn main() -> Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter("rust_graphflow_benchmark=debug,graph_flow=info")
        .init();

    let storage: Arc<dyn SessionStorage> = Arc::new(graph_flow::InMemorySessionStorage::new());
    
    let graph = GraphBuilder::new("research_workflow")
        .add_task(Arc::new(QuestionExtractorTask))
        .add_task(Arc::new(ResearcherTask))
        .add_task(Arc::new(SummarizerTask))
        .add_task(Arc::new(ReporterTask))
        .add_edge("question_extractor", "researcher")
        .add_edge("researcher", "summarizer")
        .add_edge("summarizer", "reporter")
        .build();

    let runner = Arc::new(FlowRunner::new(Arc::new(graph), storage.clone()));
    let state = AppState { runner, storage };

    let app = Router::new()
        .route("/health", get(health))
        .route("/research", post(research))
        .layer(CorsLayer::permissive())
        .with_state(state);

    let listener = tokio::net::TcpListener::bind("0.0.0.0:3000").await?;
    info!("Rust GraphFlow benchmark server running on http://0.0.0.0:3000");
    
    axum::serve(listener, app).await?;
    Ok(())
}

async fn health() -> &'static str {
    "OK"
}

#[instrument(skip(state))]
async fn research(
    State(state): State<AppState>,
    Json(req): Json<ResearchRequest>,
) -> Result<Json<ResearchResponse>, StatusCode> {
    let start_time = std::time::Instant::now();
    let session_id = Uuid::new_v4().to_string();
    
    info!("Starting research workflow for session {}", session_id);

    let session = Session::new_from_task(session_id.clone(), "question_extractor");
    let context = ResearchContext {
        topic: req.topic.clone(),
        questions: vec![],
        research_results: vec![],
        summary: String::new(),
        report: String::new(),
    };
    
    session.context.set("research_context", context).await;
    (*state.storage).save(session).await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

    loop {
        let result = state.runner.run(&session_id).await
            .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;

        match &result.status {
            graph_flow::ExecutionStatus::Completed => {
                info!("Workflow completed in {:?}", start_time.elapsed());
                break;
            }
            graph_flow::ExecutionStatus::Paused { next_task_id, .. } => {
                info!("Workflow paused, next task: {}", next_task_id);
                continue;
            }
            graph_flow::ExecutionStatus::Error(e) => {
                tracing::error!("Workflow error: {}", e);
                return Err(StatusCode::INTERNAL_SERVER_ERROR);
            }
            _ => continue,
        }
    }

    let session = (*state.storage).get(&session_id).await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?
        .ok_or(StatusCode::NOT_FOUND)?;

    let context: ResearchContext = session.context.get("research_context").await
        .ok_or(StatusCode::INTERNAL_SERVER_ERROR)?;

    let response = ResearchResponse {
        session_id,
        topic: req.topic,
        questions: context.questions,
        summary: context.summary,
        report: context.report,
        total_time_ms: start_time.elapsed().as_millis() as u64,
        task_times: session.context.get("task_times").await.unwrap_or_default(),
    };

    Ok(Json(response))
}
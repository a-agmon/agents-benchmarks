use anyhow::Result;
use rig::prelude::*;
use rig::providers::openai;
use rig::tool::Tool;

type LLMAgent = rig::agent::Agent<openai::CompletionModel>;

pub fn get_llm() -> Result<LLMAgent> {
    let api_key = std::env::var("OPENAI_API_KEY")
        .map_err(|_| anyhow::anyhow!("OpenAI API key not configured"))?;
    let client = openai::Client::new(&api_key);
    Ok(client.agent("gpt-4o-mini").build())
}

pub fn get_llm_with_tool<T: Tool + Clone + 'static>(tool: T) -> Result<LLMAgent> {
    let api_key = std::env::var("OPENAI_API_KEY")
        .map_err(|_| anyhow::anyhow!("OpenAI API key not configured"))?;
    let client = openai::Client::new(&api_key);
    Ok(client.agent("gpt-4o-mini").tool(tool).build())
}
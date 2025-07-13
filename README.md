# AI Workflow Benchmark: Rust graph-flow vs Python LangGraph

This benchmark compares the performance and resource efficiency of AI workflows implemented in Rust (using graph-flow) versus Python (using LangGraph).

## Overview

Both implementations provide identical functionality:
1. **Question Extraction**: Generate 3-5 research questions from a given topic
2. **Research**: Parallel web searches using Tavily for each question
3. **Summarization**: Consolidate findings into a cohesive summary
4. **Report Generation**: Create a comprehensive markdown report

## Architecture

### Rust Implementation
- Framework: graph-flow (custom Rust workflow library)
- Web Server: Axum
- LLM Integration: rig-core with OpenAI
- Async Runtime: Tokio

### Python Implementation
- Framework: LangGraph
- Web Server: FastAPI with Uvicorn
- LLM Integration: LangChain with OpenAI
- Async: Native Python asyncio

## Setup

### Prerequisites
- Rust (latest stable)
- Python 3.11+
- OpenAI API key
- Tavily API key

### Environment Variables
Create `.env` files in both project directories:
```bash
OPENAI_API_KEY=your_openai_api_key
TAVILY_API_KEY=your_tavily_api_key
```

### Rust Setup
```bash
cd rust-graphflow-benchmark
cargo build --release
cargo run --release
```

### Python Setup
```bash
cd python-langgraph-benchmark
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
python -m src.main
```

## Running the Benchmark

### Servers
- Rust: http://localhost:3000
- Python: http://localhost:3001

### API Endpoints
Both servers expose identical endpoints:
- `GET /health` - Health check
- `POST /research` - Execute research workflow

### Example Request
```bash
curl -X POST http://localhost:3000/research \
  -H "Content-Type: application/json" \
  -d '{"topic": "quantum computing applications in medicine"}'
```

### Response Format
```json
{
  "session_id": "uuid",
  "topic": "quantum computing applications in medicine",
  "questions": ["...", "..."],
  "summary": "...",
  "report": "...",
  "total_time_ms": 25000,
  "task_times": {
    "question_extractor": 1500,
    "researcher": 12000,
    "summarizer": 3500,
    "reporter": 8000
  }
}
```

## Performance Testing

### Prerequisites for Benchmarking
Install benchmark dependencies:
```bash
pip install -r requirements.txt
```

### Enhanced Benchmark Script

The `benchmark.py` script provides comprehensive performance testing with:
- **Concurrent request execution** with configurable worker threads
- **Real-time resource monitoring** (CPU, memory usage)
- **Detailed latency analysis** (avg, p50, p95, p99, min, max)
- **Throughput measurement**
- **Task-level performance breakdown**
- **JSON results export** for further analysis

### Basic Usage

```bash
# Quick benchmark with 10 requests and 5 concurrent workers
python benchmark.py

# Custom configuration
python benchmark.py --num-requests 20 --max-workers 8 --topic "machine learning in finance"

# Stress test with many concurrent requests
python benchmark.py --num-requests 100 --max-workers 15

# Disable resource monitoring for faster execution
python benchmark.py --no-resource-monitoring
```

### Advanced Usage Examples

```bash
# Test different concurrency levels
python benchmark.py --num-requests 50 --max-workers 5   # Low concurrency
python benchmark.py --num-requests 50 --max-workers 20  # High concurrency

# Test custom services
python benchmark.py --rust-url http://server1:3000 --python-url http://server2:3001

# Extended stress test
python benchmark.py --num-requests 200 --max-workers 25 --topic "quantum computing research"
```

### Benchmark Output

The script provides detailed output including:

```
============================================================
AI Workflow Benchmark: Rust graph-flow vs Python LangGraph
============================================================
Topic: artificial intelligence in healthcare
Total Requests: 10
Max Concurrent Workers: 5
Resource Monitoring: Enabled

🦀 Testing Rust service...
Request 1: 28543ms
Request 2: 25123ms
...

🐍 Testing Python service...
Request 1: 31245ms
Request 2: 28567ms
...

============================================================
BENCHMARK RESULTS
============================================================

Metric                   Rust            Python          Improvement    
----------------------------------------------------------------------
Avg Latency (ms)         26832           29543           1.10x
P50 Latency (ms)         26123           28967           1.11x
P95 Latency (ms)         31245           35123           1.12x
Max Latency (ms)         33567           38234           
Min Latency (ms)         24123           26543           
Total Time (s)           67.2            74.8           
Throughput (req/s)       0.15            0.13           
Successful Requests      10              10             
Error Rate (%)           0.0             0.0            

Resource Usage:
--------------------------------------------------
Avg CPU (%)              12.3            23.7            1.93x
Avg Memory (MB)          45.2            156.8           3.47x
Max Memory (MB)          52.1            178.3           

Task Performance Breakdown:
--------------------------------------------------
question_extractor       1245            1567            1.26x
researcher               18543           21234           1.15x
summarizer               3456            4123            1.19x
reporter                 3588            2619            0.73x
```

### Results Analysis

- **Results are saved** to `benchmark_results.json` with detailed metrics
- **Resource monitoring** tracks CPU and memory usage during execution
- **Task breakdown** shows performance of individual workflow steps
- **Improvement ratios** help identify performance differences

### Manual Resource Monitoring

If you prefer manual monitoring:

```bash
# Monitor Rust process
ps aux | grep -E "rust-graphflow|target/release" | grep -v grep

# Monitor Python process  
ps aux | grep -E "python.*main|uvicorn" | grep -v grep

# Continuous monitoring
watch 'ps aux | grep -E "(rust-graphflow|python.*main)" | grep -v grep'
```

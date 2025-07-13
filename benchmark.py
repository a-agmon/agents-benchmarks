#!/usr/bin/env python3
"""
Benchmark script to compare Rust graph-flow vs Python LangGraph performance
Enhanced with threading, resource monitoring, and comprehensive metrics
"""

import asyncio
import httpx
import time
import statistics
import json
import argparse
import psutil
import threading
import concurrent.futures
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class ResourceMetrics:
    """Resource usage metrics"""
    cpu_percent: float
    memory_mb: float
    threads: int


class ResourceMonitor:
    """Monitor system resource usage for specific processes"""
    
    def __init__(self, process_names: List[str]):
        self.process_names = process_names
        self.metrics = []
        self.monitoring = False
        self.monitor_thread = None
    
    def start_monitoring(self, interval: float = 1.0):
        """Start monitoring resources"""
        self.monitoring = True
        self.metrics = []
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop, 
            args=(interval,),
            daemon=True
        )
        self.monitor_thread.start()
    
    def stop_monitoring(self) -> List[ResourceMetrics]:
        """Stop monitoring and return collected metrics"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2.0)
        return self.metrics
    
    def _monitor_loop(self, interval: float):
        """Internal monitoring loop"""
        while self.monitoring:
            try:
                total_cpu = 0.0
                total_memory = 0.0
                total_threads = 0
                found_processes = 0
                
                for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info', 'num_threads']):
                    try:
                        proc_name = proc.info['name']
                        if any(name in proc_name for name in self.process_names):
                            cpu = proc.info['cpu_percent'] or 0.0
                            memory = proc.info['memory_info'].rss / (1024 * 1024)  # MB
                            threads = proc.info['num_threads'] or 0
                            
                            total_cpu += cpu
                            total_memory += memory
                            total_threads += threads
                            found_processes += 1
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                
                if found_processes > 0:
                    self.metrics.append(ResourceMetrics(
                        cpu_percent=total_cpu,
                        memory_mb=total_memory,
                        threads=total_threads
                    ))
                
                time.sleep(interval)
            except Exception as e:
                print(f"Resource monitoring error: {e}")
                break


async def benchmark_service_threaded(
    url: str,
    topic: str,
    num_requests: int,
    max_workers: int = 5,
    timeout: float = 120.0
) -> Dict:
    """Benchmark service using threading for concurrent requests"""
    
    print(f"Starting threaded benchmark: {num_requests} requests with {max_workers} workers")
    
    latencies = []
    errors = 0
    responses = []
    start_time = time.time()
    
    async def make_request(session_num: int) -> Optional[Dict]:
        """Make a single request"""
        request_start = time.time()
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    f"{url}/research",
                    json={"topic": f"{topic} (request {session_num})"}
                )
                response.raise_for_status()
                
                latency = (time.time() - request_start) * 1000
                data = response.json()
                
                print(f"Request {session_num}: {latency:.0f}ms")
                return {"latency": latency, "response": data}
                
        except Exception as e:
            print(f"Error in request {session_num}: {e}")
            return None
    
    # Use semaphore to limit concurrent requests
    semaphore = asyncio.Semaphore(max_workers)
    
    async def bounded_request(session_num: int):
        async with semaphore:
            return await make_request(session_num)
    
    # Execute all requests concurrently
    tasks = [bounded_request(i + 1) for i in range(num_requests)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Process results
    for result in results:
        if isinstance(result, Exception):
            errors += 1
        elif result is None:
            errors += 1
        else:
            latencies.append(result["latency"])
            responses.append(result["response"])
    
    total_time = time.time() - start_time
    
    # Calculate task time statistics
    task_times = {}
    for response in responses:
        for task, duration in response.get("task_times", {}).items():
            if task not in task_times:
                task_times[task] = []
            task_times[task].append(duration)
    
    task_stats = {}
    for task, times in task_times.items():
        task_stats[task] = {
            "avg_ms": statistics.mean(times),
            "p50_ms": statistics.median(times),
            "p95_ms": statistics.quantiles(times, n=20)[18] if len(times) > 20 else max(times) if times else 0,
        }
    
    return {
        "service_url": url,
        "total_requests": num_requests,
        "successful_requests": len(latencies),
        "errors": errors,
        "error_rate": errors / num_requests if num_requests > 0 else 0,
        "total_time_seconds": total_time,
        "throughput_rps": len(latencies) / total_time if total_time > 0 else 0,
        "avg_latency_ms": statistics.mean(latencies) if latencies else 0,
        "p50_latency_ms": statistics.median(latencies) if latencies else 0,
        "p95_latency_ms": statistics.quantiles(latencies, n=20)[18] if len(latencies) > 20 else max(latencies) if latencies else 0,
        "p99_latency_ms": statistics.quantiles(latencies, n=100)[98] if len(latencies) > 100 else max(latencies) if latencies else 0,
        "max_latency_ms": max(latencies) if latencies else 0,
        "min_latency_ms": min(latencies) if latencies else 0,
        "task_statistics": task_stats,
        "raw_latencies": latencies
    }


async def benchmark_service(
    url: str, 
    topic: str, 
    requests_per_second: int = 10, 
    duration: int = 60
) -> Dict:
    """Benchmark a service with specified load parameters"""
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        latencies = []
        errors = 0
        responses = []
        
        start_time = time.time()
        request_count = 0
        
        print(f"Starting benchmark for {url}")
        print(f"Target: {requests_per_second} req/s for {duration} seconds")
        
        while time.time() - start_time < duration:
            request_start = time.time()
            
            try:
                response = await client.post(
                    f"{url}/research",
                    json={"topic": topic}
                )
                response.raise_for_status()
                
                latency = (time.time() - request_start) * 1000
                latencies.append(latency)
                
                data = response.json()
                responses.append(data)
                
                print(f"Request {request_count + 1}: {latency:.0f}ms")
                
            except Exception as e:
                errors += 1
                print(f"Error in request {request_count + 1}: {e}")
            
            request_count += 1
            
            # Wait to maintain request rate
            elapsed = time.time() - request_start
            sleep_time = max(0, (1.0 / requests_per_second) - elapsed)
            await asyncio.sleep(sleep_time)
        
        # Calculate task time statistics
        task_times = {}
        for response in responses:
            for task, duration in response.get("task_times", {}).items():
                if task not in task_times:
                    task_times[task] = []
                task_times[task].append(duration)
        
        task_stats = {}
        for task, times in task_times.items():
            task_stats[task] = {
                "avg_ms": statistics.mean(times),
                "p50_ms": statistics.median(times),
                "p95_ms": statistics.quantiles(times, n=20)[18] if len(times) > 20 else max(times) if times else 0,
            }
        
        return {
            "service_url": url,
            "total_requests": request_count,
            "successful_requests": len(latencies),
            "errors": errors,
            "error_rate": errors / request_count if request_count > 0 else 0,
            "avg_latency_ms": statistics.mean(latencies) if latencies else 0,
            "p50_latency_ms": statistics.median(latencies) if latencies else 0,
            "p95_latency_ms": statistics.quantiles(latencies, n=20)[18] if len(latencies) > 20 else max(latencies) if latencies else 0,
            "p99_latency_ms": statistics.quantiles(latencies, n=100)[98] if len(latencies) > 100 else max(latencies) if latencies else 0,
            "task_statistics": task_stats,
            "raw_latencies": latencies
        }


async def run_comparison_benchmark(
    rust_url: str = "http://localhost:3000",
    python_url: str = "http://localhost:3001",
    topic: str = "artificial intelligence in healthcare",
    num_requests: int = 10,
    max_workers: int = 5,
    monitor_resources: bool = True
):
    """Run benchmark against both services and compare results"""
    
    print("=" * 60)
    print("AI Workflow Benchmark: Rust graph-flow vs Python LangGraph")
    print("=" * 60)
    print(f"Topic: {topic}")
    print(f"Total Requests: {num_requests}")
    print(f"Max Concurrent Workers: {max_workers}")
    print(f"Resource Monitoring: {'Enabled' if monitor_resources else 'Disabled'}")
    print()
    
    # Check if services are running
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            rust_health = await client.get(f"{rust_url}/health")
            rust_health.raise_for_status()
            print("✓ Rust service is running")
        except Exception as e:
            print(f"✗ Rust service not available: {e}")
            return
            
        try:
            python_health = await client.get(f"{python_url}/health")
            python_health.raise_for_status()
            print("✓ Python service is running")
        except Exception as e:
            print(f"✗ Python service not available: {e}")
            return
    
    print("\nStarting benchmarks...\n")
    
    # Setup resource monitoring
    rust_monitor = None
    python_monitor = None
    
    if monitor_resources:
        rust_monitor = ResourceMonitor(["rust-graphflow", "target/release"])
        python_monitor = ResourceMonitor(["python", "uvicorn", "main.py"])

            # Run Python benchmark
    print("🐍 Testing Python service...")
    if python_monitor:
        python_monitor.start_monitoring()
    
    python_results = await benchmark_service_threaded(
        python_url, topic, num_requests, max_workers
    )
    
    python_resource_metrics = []
    if python_monitor:
        python_resource_metrics = python_monitor.stop_monitoring()
    
    print(f"Python benchmark completed: {python_results['successful_requests']}/{python_results['total_requests']} successful")
    print()
    
    # Run Rust benchmark first
    print("🦀 Testing Rust service...")
    if rust_monitor:
        rust_monitor.start_monitoring()
    
    rust_results = await benchmark_service_threaded(
        rust_url, topic, num_requests, max_workers
    )
    
    rust_resource_metrics = []
    if rust_monitor:
        rust_resource_metrics = rust_monitor.stop_monitoring()
    
    print(f"Rust benchmark completed: {rust_results['successful_requests']}/{rust_results['total_requests']} successful")
    print()
    

    
    # Print comparison results
    print("\n" + "=" * 60)
    print("BENCHMARK RESULTS")
    print("=" * 60)
    
    print(f"\n{'Metric':<25} {'Rust':<15} {'Python':<15} {'Improvement':<15}")
    print("-" * 70)
    
    # Latency comparison
    rust_avg = rust_results['avg_latency_ms']
    python_avg = python_results['avg_latency_ms']
    avg_improvement = python_avg / rust_avg if rust_avg > 0 else 0
    
    rust_p50 = rust_results['p50_latency_ms']
    python_p50 = python_results['p50_latency_ms']
    p50_improvement = python_p50 / rust_p50 if rust_p50 > 0 else 0
    
    rust_p95 = rust_results['p95_latency_ms']
    python_p95 = python_results['p95_latency_ms']
    p95_improvement = python_p95 / rust_p95 if rust_p95 > 0 else 0
    
    print(f"{'Avg Latency (ms)':<25} {rust_avg:<15.0f} {python_avg:<15.0f} {avg_improvement:.2f}x")
    print(f"{'P50 Latency (ms)':<25} {rust_p50:<15.0f} {python_p50:<15.0f} {p50_improvement:.2f}x")
    print(f"{'P95 Latency (ms)':<25} {rust_p95:<15.0f} {python_p95:<15.0f} {p95_improvement:.2f}x")
    print(f"{'Max Latency (ms)':<25} {rust_results['max_latency_ms']:<15.0f} {python_results['max_latency_ms']:<15.0f}")
    print(f"{'Min Latency (ms)':<25} {rust_results['min_latency_ms']:<15.0f} {python_results['min_latency_ms']:<15.0f}")
    
    # Throughput and reliability
    print(f"{'Total Time (s)':<25} {rust_results['total_time_seconds']:<15.1f} {python_results['total_time_seconds']:<15.1f}")
    print(f"{'Throughput (req/s)':<25} {rust_results['throughput_rps']:<15.1f} {python_results['throughput_rps']:<15.1f}")
    print(f"{'Successful Requests':<25} {rust_results['successful_requests']:<15} {python_results['successful_requests']:<15}")
    print(f"{'Error Rate (%)':<25} {rust_results['error_rate']*100:<15.1f} {python_results['error_rate']*100:<15.1f}")
    
    # Resource usage comparison
    if monitor_resources and rust_resource_metrics and python_resource_metrics:
        print("\nResource Usage:")
        print("-" * 50)
        
        rust_avg_cpu = statistics.mean([m.cpu_percent for m in rust_resource_metrics])
        rust_avg_memory = statistics.mean([m.memory_mb for m in rust_resource_metrics])
        rust_max_memory = max([m.memory_mb for m in rust_resource_metrics])
        
        python_avg_cpu = statistics.mean([m.cpu_percent for m in python_resource_metrics])
        python_avg_memory = statistics.mean([m.memory_mb for m in python_resource_metrics])
        python_max_memory = max([m.memory_mb for m in python_resource_metrics])
        
        cpu_improvement = python_avg_cpu / rust_avg_cpu if rust_avg_cpu > 0 else 0
        memory_improvement = python_avg_memory / rust_avg_memory if rust_avg_memory > 0 else 0
        
        print(f"{'Avg CPU (%)':<25} {rust_avg_cpu:<15.1f} {python_avg_cpu:<15.1f} {cpu_improvement:.2f}x")
        print(f"{'Avg Memory (MB)':<25} {rust_avg_memory:<15.1f} {python_avg_memory:<15.1f} {memory_improvement:.2f}x")
        print(f"{'Max Memory (MB)':<25} {rust_max_memory:<15.1f} {python_max_memory:<15.1f}")
    elif monitor_resources:
        print("\nResource monitoring was enabled but no metrics collected.")
        print("Make sure the services are running and process names are correct.")
    
    # Task breakdown
    print("\nTask Performance Breakdown:")
    print("-" * 50)
    
    all_tasks = set(rust_results['task_statistics'].keys()) | set(python_results['task_statistics'].keys())
    
    for task in sorted(all_tasks):
        rust_avg = rust_results['task_statistics'].get(task, {}).get('avg_ms', 0)
        python_avg = python_results['task_statistics'].get(task, {}).get('avg_ms', 0)
        
        if rust_avg > 0 and python_avg > 0:
            improvement = python_avg / rust_avg
            print(f"{task:<25} {rust_avg:<15.0f} {python_avg:<15.0f} {improvement:.2f}x")
    
    # Save detailed results
    results = {
        "timestamp": time.time(),
        "benchmark_config": {
            "topic": topic,
            "num_requests": num_requests,
            "max_workers": max_workers,
            "monitor_resources": monitor_resources
        },
        "rust_results": rust_results,
        "python_results": python_results,
        "rust_resource_metrics": [
            {"cpu_percent": m.cpu_percent, "memory_mb": m.memory_mb, "threads": m.threads}
            for m in rust_resource_metrics
        ] if rust_resource_metrics else [],
        "python_resource_metrics": [
            {"cpu_percent": m.cpu_percent, "memory_mb": m.memory_mb, "threads": m.threads}
            for m in python_resource_metrics
        ] if python_resource_metrics else []
    }
    
    with open("benchmark_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\nDetailed results saved to benchmark_results.json")
    print("\nBenchmark completed! 🎉")
    print("\nNext steps:")
    print("  1. Review the detailed results in benchmark_results.json")
    print("  2. Run with different request counts: --num-requests N")
    print("  3. Adjust concurrency: --max-workers N")
    print("  4. Test different topics for varied workloads")


async def main():
    parser = argparse.ArgumentParser(
        description="Benchmark AI workflow services with threading and resource monitoring",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic benchmark with 10 requests and 3 workers
  python benchmark.py --num-requests 10 --max-workers 3
  
  # Stress test with many concurrent requests
  python benchmark.py --num-requests 50 --max-workers 10
  
  # Custom topic and URLs
  python benchmark.py --topic "machine learning in finance" --rust-url http://localhost:3000
  
  # Disable resource monitoring for faster execution
  python benchmark.py --no-resource-monitoring
        """
    )
    parser.add_argument("--rust-url", default="http://localhost:3000", help="Rust service URL")
    parser.add_argument("--python-url", default="http://localhost:3001", help="Python service URL")
    parser.add_argument("--topic", default="artificial intelligence in healthcare", help="Research topic")
    parser.add_argument("--num-requests", type=int, default=10, help="Total number of requests to send")
    parser.add_argument("--max-workers", type=int, default=5, help="Maximum concurrent workers")
    parser.add_argument("--no-resource-monitoring", action="store_true", help="Disable resource monitoring")
    
    args = parser.parse_args()
    
    await run_comparison_benchmark(
        rust_url=args.rust_url,
        python_url=args.python_url,
        topic=args.topic,
        num_requests=args.num_requests,
        max_workers=args.max_workers,
        monitor_resources=not args.no_resource_monitoring
    )


if __name__ == "__main__":
    asyncio.run(main())
# LLM Metrics Tracking System

## Overview

The LLM Metrics Tracking System captures detailed information about every LLM API call in your text-to-SQL agent workflow. This enables you to investigate usage patterns, optimize costs, improve performance, and analyze the agent's behavior.

## What Gets Tracked

For **each LLM call**, the system captures:

### ⏱️ Timing Metrics
- **start_time** / **end_time**: Unix timestamps
- **latency_ms**: Total time for the API call in milliseconds
- **tokens_per_second**: Throughput (tokens processed per second)

### 💰 Cost Metrics
- **prompt_tokens**: Number of input tokens
- **completion_tokens**: Number of output tokens  
- **total_tokens**: Sum of input + output tokens
- **input_cost**: Cost of input tokens (USD)
- **output_cost**: Cost of output tokens (USD)
- **total_cost**: Total cost for the call (USD)

### 📊 Content Metrics
- **prompt_length**: Character count of the prompt
- **response_length**: Character count of the response
- **prompt_preview**: First 300 characters of the prompt
- **response_preview**: First 300 characters of the response

### 🏷️ Identification
- **call_id**: Unique UUID for the call
- **stage**: Name of the workflow stage (e.g., "schema_search", "generate_sql")
- **model**: Model name used
- **provider**: Provider name ("openai", "groq", etc.)
- **temperature**: Temperature parameter used

### ✅ Quality Metrics
- **success**: Whether the call succeeded
- **error**: Error message (if any)

## Example Output

```
================================================================================
LLM USAGE METRICS REPORT
================================================================================

Total Calls: 8
Total Tokens: 5,234 (2,341 input, 2,893 output)
Total Cost: $0.012345 USD
Total Latency: 2,854.30ms
Avg Latency/Call: 356.79ms
Throughput: 1.83 tokens/second

--------------------------------------------------------------------------------
BREAKDOWN BY STAGE:
--------------------------------------------------------------------------------

SCHEMA_SEARCH:
  Calls: 2
  Tokens: 1.2K
  Cost: $0.002145
  Avg Latency: 289.45ms

PLAN_SQL:
  Calls: 1
  Tokens: 892
  Cost: $0.001234
  Avg Latency: 234.12ms

GENERATE_SQL:
  Calls: 3
  Tokens: 2.1K
  Cost: $0.006789
  Avg Latency: 412.34ms

REPAIR_SQL:
  Calls: 2
  Tokens: 1.0K
  Cost: $0.002177
  Avg Latency: 345.67ms

================================================================================
```

## Using the Metrics System

### 1. Basic Usage - Access Metrics Automatically

```python
from text2sql_agent.agent.orchestrator import Text2SQLOrchestrator
from text2sql_agent.db.connector import DatabaseConnector

# Create and run orchestrator
connector = DatabaseConnector(db_type="sqlite", db_path="mydb.db")
orchestrator = Text2SQLOrchestrator(connector)
result = orchestrator.run(question="...", db_id="...")

# Metrics are automatically tracked in the result
metrics = result["llm_metrics"]  # LLMMetricsCollector object
print(metrics.get_detailed_report())
```

### 2. Print Summary Report

```python
from text2sql_agent.agent.metrics_reporter import MetricsReporter

MetricsReporter.print_summary(metrics)
```

### 3. Print Efficiency Report with Recommendations

```python
MetricsReporter.print_efficiency_report(metrics)
```

This generates:
- Cost analysis
- Performance metrics
- Optimization recommendations
- Token distribution by stage

### 4. Export to JSON

```python
MetricsReporter.save_json(metrics, "llm_metrics.json")
```

### 5. Get Cost Breakdown by Stage

```python
costs = MetricsReporter.get_cost_breakdown(metrics)
# Returns: {"by_stage": {...}, "total_cost": 0.012345, "most_expensive_stage": "generate_sql"}
```

### 6. Get Performance Metrics

```python
perf = MetricsReporter.get_performance_metrics(metrics)
# Returns: {"avg_latency_ms": 356.79, "max_latency_ms": 412.34, "success_rate": 0.95, ...}
```

### 7. Get Efficiency Scores

```python
eff = MetricsReporter.get_efficiency_scores(metrics)
# Returns: {"cost_per_token_micro_usd": 2.35, "tokens_per_second": 1.83, "recommendations": [...]}
```

### 8. Access Individual Call Details

```python
for call in metrics.calls:
    print(f"Stage: {call.stage}")
    print(f"Tokens: {call.total_tokens}")
    print(f"Cost: ${call.total_cost:.6f}")
    print(f"Latency: {call.latency_ms:.2f}ms")
```

### 9. Query Metrics Programmatically

```python
summary = metrics.get_summary()
print(f"Total calls: {summary['total_calls']}")
print(f"Total cost: ${summary['total_cost_usd']:.6f}")
print(f"Throughput: {summary['tokens_per_second']:.2f} tokens/sec")

# Access stage-specific metrics
for stage, stats in summary['by_stage'].items():
    print(f"{stage}: {stats['tokens']} tokens, ${stats['cost']:.6f}")
```

## Optimization Recommendations

The system automatically generates recommendations based on your metrics:

### High Cost Per Token
- **Problem**: Your cost per token is high
- **Solution**: Consider using a cheaper model (e.g., gpt-3.5-turbo instead of gpt-4)

### Low Throughput
- **Problem**: Latency is high or tokens/second is low
- **Solution**: Consider using a faster provider (e.g., Groq) or optimizing prompts

### High Input Token Ratio
- **Problem**: You're using too many input tokens relative to output
- **Solution**: Summarize prompts, use prompt templates, or implement prompt caching

## Metrics Schema

### LLMCallMetrics (Individual Call)

```python
@dataclass
class LLMCallMetrics:
    call_id: str              # Unique ID (UUID)
    stage: str                # Workflow stage name
    model: str                # Model name
    provider: str             # Provider ("openai", "groq", ...)
    
    start_time: float         # Unix timestamp
    end_time: Optional[float] # Unix timestamp
    
    prompt_tokens: int        # Input token count
    completion_tokens: int    # Output token count
    total_tokens: int         # Total token count
    
    prompt_length: int        # Character count
    response_length: int      # Character count
    prompt_preview: Optional[str]    # First 300 chars
    response_preview: Optional[str]  # First 300 chars
    
    input_cost: float         # Cost in USD
    output_cost: float        # Cost in USD
    total_cost: float         # Total cost in USD
    
    temperature: float        # Temperature parameter
    success: bool             # Whether call succeeded
    error: Optional[str]      # Error message
    
    latency_ms: float         # Latency in milliseconds
    tokens_per_second: float  # Throughput
```

### LLMMetricsCollector (Aggregated)

```python
@dataclass
class LLMMetricsCollector:
    calls: List[LLMCallMetrics]  # All individual calls
    
    # Aggregated totals
    total_prompt_tokens: int
    total_completion_tokens: int
    total_tokens: int
    total_cost: float
    
    # Methods
    get_summary() -> Dict        # Get aggregated summary
    get_detailed_report() -> str # Get formatted report
    to_dict() -> Dict           # Export as dictionary
```

## Supported Models and Pricing

The system includes pricing data for popular models. Add your own:

```python
from text2sql_agent.agent.llm_metrics import TOKEN_PRICING

TOKEN_PRICING["my-model"] = {"input": 0.001, "output": 0.002}  # per 1K tokens
```

Currently supported:
- **OpenAI**: gpt-4o, gpt-4o-mini, gpt-4-turbo, gpt-4, gpt-3.5-turbo
- **Groq**: openai/gpt-oss-120b, llama-3.1-70b-versatile, llama-3.1-8b-instant

## Integration with Workflow

Metrics are automatically tracked at each stage:

1. **schema_search**: Finding relevant tables/columns
2. **rerank_columns**: LLM-based column ranking
3. **plan_sql**: Creating structured SQL plan
4. **generate_sql**: Generating SQL candidates
5. **repair_sql**: Fixing invalid SQL

Access metrics after each stage:

```python
state.llm_metrics.get_summary()
```

## Monitoring in Production

For production deployments, export metrics regularly:

```python
import json
from datetime import datetime

# After each workflow run
timestamp = datetime.now().isoformat()
filename = f"metrics_{timestamp}.json"
MetricsReporter.save_json(metrics, filename)

# Aggregate metrics from multiple runs
all_metrics = []
for metrics_file in pathlib.Path("metrics").glob("*.json"):
    with open(metrics_file) as f:
        all_metrics.append(json.load(f))

# Analyze trends
```

## Best Practices

1. **Monitor Cost**: Check cost_per_token regularly
2. **Track Latency**: Monitor avg_latency_ms for performance degradation
3. **Watch Success Rate**: Failures indicate potential issues
4. **Compare Models**: Use metrics to choose optimal models
5. **Export Regularly**: Save metrics for historical analysis
6. **Set Alerts**: Alert if cost exceeds budget or latency spikes

## Next Steps

- Check [METRICS_USAGE.md](./METRICS_USAGE.md) for code examples
- Run `orchestrator.run()` and use `MetricsReporter` to analyze
- Export metrics to JSON for external analysis
- Build dashboards using the exported data

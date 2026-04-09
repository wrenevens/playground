# LLM Metrics - Quick Reference Guide

## 30-Second Usage

```python
# Run your workflow normally
result = orchestrator.run(question="...", db_id="...")

# Get metrics (automatically tracked!)
metrics = result["llm_metrics"]

# View report
from text2sql_agent.agent import MetricsReporter
MetricsReporter.print_efficiency_report(metrics)
```

## What Gets Tracked

| Metric | Type | Example | Use Case |
|--------|------|---------|----------|
| **call_id** | UUID | `a1b2c3d4-...` | Trace specific calls |
| **stage** | str | `"generate_sql"` | Identify which stage |
| **model** | str | `"gpt-4o-mini"` | Track model selection |
| **provider** | str | `"openai"` | Compare providers |
| **prompt_tokens** | int | `2,341` | Track input size |
| **completion_tokens** | int | `2,893` | Track output size |
| **total_tokens** | int | `5,234` | Calculate cost |
| **latency_ms** | float | `356.79` | Monitor speed |
| **input_cost** | float | `0.000351` | Track expenses |
| **output_cost** | float | `0.001734` | Track expenses |
| **total_cost** | float | `0.002085` | Budget tracking |
| **tokens_per_second** | float | `14.67` | Performance metric |
| **success** | bool | `true` | Error tracking |
| **error** | str/None | `null` | Debugging |
| **temperature** | float | `0.3` | Parameter tracking |
| **prompt_length** | int | `1,234` | Complexity analysis |
| **response_length** | int | `567` | Output analysis |

## Report Types

### 1. Summary Report (3 seconds to read)
```python
MetricsReporter.print_summary(metrics)
```
Shows: Total calls, tokens, cost, latency, stage breakdown

### 2. Efficiency Report (5 seconds + optionally actionable)
```python
MetricsReporter.print_efficiency_report(metrics)
```
Shows: Cost analysis, performance, recommendations for optimization

### 3. Cost Breakdown (by stage)
```python
costs = MetricsReporter.get_cost_breakdown(metrics)
print(costs["most_expensive_stage"])  # "generate_sql"
```

### 4. Performance Metrics
```python
perf = MetricsReporter.get_performance_metrics(metrics)
print(f"Avg latency: {perf['avg_latency_ms']:.2f}ms")
print(f"Success rate: {perf['success_rate']*100:.1f}%")
```

### 5. Efficiency Scores
```python
eff = MetricsReporter.get_efficiency_scores(metrics)
print(f"Cost/token: {eff['cost_per_token_micro_usd']:.2f} µUSD")
print(f"Recommendations: {eff['recommendations']}")
```

## Common Queries

### How much did this workflow cost?
```python
summary = metrics.get_summary()
print(f"${summary['total_cost_usd']:.6f}")
```

### Which stage is most expensive?
```python
costs = MetricsReporter.get_cost_breakdown(metrics)
most_expensive = costs["most_expensive_stage"]
print(most_expensive)  # "generate_sql"
```

### Which stage is slowest?
```python
summary = metrics.get_summary()
slowest = max(summary['by_stage'].items(), key=lambda x: x[1]['avg_latency_ms'])
print(slowest[0])  # stage name
```

### How many tokens total?
```python
summary = metrics.get_summary()
print(f"Input: {summary['prompt_tokens']:,}")
print(f"Output: {summary['completion_tokens']:,}")
print(f"Total: {summary['total_tokens']:,}")
```

### What's the throughput?
```python
summary = metrics.get_summary()
print(f"{summary['tokens_per_second']:.2f} tokens/sec")
```

### What stages were called?
```python
summary = metrics.get_summary()
for stage in summary['by_stage'].keys():
    print(f"- {stage}")
```

### Were there any errors?
```python
errors = [call for call in metrics.calls if not call.success]
for error in errors:
    print(f"{error.stage}: {error.error}")
```

### Details of specific call
```python
for call in metrics.calls:
    if call.stage == "generate_sql":
        print(f"Model: {call.model}")
        print(f"Tokens: {call.total_tokens}")
        print(f"Cost: ${call.total_cost:.6f}")
        print(f"Time: {call.latency_ms:.0f}ms")
        print(f"Success: {call.success}")
```

### Compare models
```python
by_model = {}
for call in metrics.calls:
    if call.model not in by_model:
        by_model[call.model] = {"calls": 0, "cost": 0}
    by_model[call.model]["calls"] += 1
    by_model[call.model]["cost"] += call.total_cost

for model, stats in by_model.items():
    print(f"{model}: {stats['calls']} calls, ${stats['cost']:.6f}")
```

## Export & Storage

### Save to JSON
```python
MetricsReporter.save_json(metrics, "metrics.json")
```

### Load from JSON
```python
import json
with open("metrics.json") as f:
    data = json.load(f)
```

### Append to CSV (for aggregation)
```python
import csv
summary = metrics.get_summary()
with open("metrics.csv", "a") as f:
    writer = csv.DictWriter(f, fieldnames=summary.keys())
    writer.writerow(summary)
```

## Pricing Reference

| Model | Input | Output | Cost per 1K tokens |
|-------|-------|--------|-------------------|
| gpt-4o-mini | $0.00015 | $0.0006 | Cheapest OpenAI |
| gpt-3.5-turbo | $0.0005 | $0.0015 | Legacy, slower |
| gpt-4o | $0.0025 | $0.01 | Balanced |
| gpt-4-turbo | $0.01 | $0.03 | Fast |
| gpt-4 | $0.03 | $0.06 | Premium |

## Optimization Checklist

- [ ] Review efficiency report recommendations
- [ ] Identify most expensive stage
- [ ] Check if switching model would save 50%+
- [ ] Look for high error rates
- [ ] Monitor cost per query over time
- [ ] Compare latency across providers
- [ ] Set cost/latency alerts
- [ ] Track trends weekly

## Pro Tips

1. **Track Over Time**: Save metrics from each run for trend analysis
2. **Set Budgets**: Alert if cost > $X per query
3. **A/B Test Models**: Compare gpt-4o vs gpt-3.5-turbo
4. **Monitor Success Rate**: Watch for degradation
5. **Cache Expensive Calls**: Use metrics to identify candidates
6. **Batch Similar Stages**: Combine multiple small calls
7. **Compare Providers**: Run same query on Groq vs OpenAI

## Troubleshooting

### No metrics showing?
- Check that `result["llm_metrics"]` exists
- Verify orchestrator ran without errors
- Ensure `connect_with_metrics` is being called

### Cost seems wrong?
- Check TOKEN_PRICING dict has your model
- Verify token counts match API responses
- Review rate in pricing table above

### Latency unexpectedly high?
- Network issue? Check provider status
- Rate limit? Check error messages
- Temperature too high? (Lower = faster)

### Need custom reporting?
```python
# Access raw metrics
for call in metrics.calls:
    print(call.to_dict())

# Or export everything
data = metrics.to_dict()
```

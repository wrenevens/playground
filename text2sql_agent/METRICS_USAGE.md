"""
Example: Using LLM Metrics Tracking
====================================

This example demonstrates how to use the comprehensive LLM metrics tracking
system to monitor, analyze, and optimize your text-to-SQL agent's performance.
"""

from text2sql_agent.agent.orchestrator import Text2SQLOrchestrator
from text2sql_agent.agent.metrics_reporter import MetricsReporter
from text2sql_agent.db.connector import DatabaseConnector
import json


def example_with_metrics():
    """Run the text-to-SQL agent and analyze metrics."""
    
    # Initialize your database connector
    connector = DatabaseConnector(
        db_type="sqlite",
        db_path="path/to/your/database.db"
    )
    
    # Create orchestrator
    orchestrator = Text2SQLOrchestrator(
        connector=connector,
        llm_provider="openai",  # or "groq", "anthropic", etc.
        llm_model="gpt-4o-mini"
    )
    
    # Example question
    question = "How many customers made purchases over $1000 last month?"
    db_id = "your_database"
    
    # Run the workflow - metrics are automatically tracked
    result = orchestrator.run(question=question, db_id=db_id)
    
    # Access the metrics collector from the state
    metrics_collector = result["llm_metrics"]  # This is a LLMMetricsCollector object
    
    # ========== EXAMPLE 1: Print summary report ==========
    print("\n" + "="*80)
    print("APPROACH 1: Print Summary Report")
    print("="*80)
    MetricsReporter.print_summary(metrics_collector)
    
    # ========== EXAMPLE 2: Print efficiency report with recommendations ==========
    print("\n" + "="*80)
    print("APPROACH 2: Print Efficiency Report")
    print("="*80)
    MetricsReporter.print_efficiency_report(metrics_collector)
    
    # ========== EXAMPLE 3: Get cost breakdown by stage ==========
    print("\n" + "="*80)
    print("APPROACH 3: Cost Breakdown by Stage")
    print("="*80)
    costs = MetricsReporter.get_cost_breakdown(metrics_collector)
    print(json.dumps(costs, indent=2))
    
    # ========== EXAMPLE 4: Get performance metrics ==========
    print("\n" + "="*80)
    print("APPROACH 4: Performance Metrics")
    print("="*80)
    perf = MetricsReporter.get_performance_metrics(metrics_collector)
    print(json.dumps(perf, indent=2, default=str))
    
    # ========== EXAMPLE 5: Get efficiency scores ==========
    print("\n" + "="*80)
    print("APPROACH 5: Efficiency Scores & Recommendations")
    print("="*80)
    eff = MetricsReporter.get_efficiency_scores(metrics_collector)
    print(json.dumps(eff, indent=2, default=str))
    
    # ========== EXAMPLE 6: Save to JSON ==========
    print("\n" + "="*80)
    print("APPROACH 6: Export to JSON")
    print("="*80)
    MetricsReporter.save_json(metrics_collector, "llm_metrics.json")
    print("✓ Metrics saved to llm_metrics.json")
    
    # ========== EXAMPLE 7: Access individual call metrics ==========
    print("\n" + "="*80)
    print("APPROACH 7: Individual Call Details")
    print("="*80)
    for i, call in enumerate(metrics_collector.calls):
        print(f"\nCall {i+1}: {call.stage}")
        print(f"  Model: {call.model}")
        print(f"  Provider: {call.provider}")
        print(f"  Tokens: {call.prompt_tokens} (input) + {call.completion_tokens} (output) = {call.total_tokens} (total)")
        print(f"  Latency: {call.latency_ms:.2f} ms")
        print(f"  Cost: ${call.total_cost:.6f}")
        print(f"  Success: {call.success}")
        if call.error:
            print(f"  Error: {call.error}")
    
    # ========== EXAMPLE 8: Query metrics programmatically ==========
    print("\n" + "="*80)
    print("APPROACH 8: Programmatic Queries")
    print("="*80)
    summary = metrics_collector.get_summary()
    print(f"Total Calls: {summary['total_calls']}")
    print(f"Total Tokens: {summary['total_tokens']:,}")
    print(f"Total Cost: ${summary['total_cost_usd']:.6f}")
    print(f"Total Latency: {summary['total_latency_ms']:.2f} ms")
    print(f"Throughput: {summary['tokens_per_second']:.2f} tokens/sec")
    
    # ========== EXAMPLE 9: Compare different models ==========
    print("\n" + "="*80)
    print("APPROACH 9: Compare Calls by Model")
    print("="*80)
    by_model = {}
    for call in metrics_collector.calls:
        if call.model not in by_model:
            by_model[call.model] = {
                "calls": 0,
                "tokens": 0,
                "cost": 0.0,
                "latency": 0.0
            }
        by_model[call.model]["calls"] += 1
        by_model[call.model]["tokens"] += call.total_tokens
        by_model[call.model]["cost"] += call.total_cost
        by_model[call.model]["latency"] += call.latency_ms
    
    for model, stats in by_model.items():
        print(f"\n{model}:")
        print(f"  Calls: {stats['calls']}")
        print(f"  Tokens: {stats['tokens']:,}")
        print(f"  Cost: ${stats['cost']:.6f}")
        print(f"  Total Latency: {stats['latency']:.2f} ms")
    
    # ========== Analyze the workflow result ==========
    print("\n" + "="*80)
    print("WORKFLOW RESULT")
    print("="*80)
    print(f"Question: {result['question']}")
    print(f"Final SQL: {result['final_sql']}")
    print(f"Execution Result: {result['execution_result']}")
    print(f"Errors: {result['errors']}")
    
    return result


if __name__ == "__main__":
    example_with_metrics()

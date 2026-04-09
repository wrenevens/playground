"""
LLM Metrics Reporting and Analysis.
Provides tools to view, analyze, and export LLM usage metrics.
"""

import logging
from typing import Dict, Any, List
import json
from datetime import datetime

from .llm_metrics import LLMMetricsCollector


logger = logging.getLogger(__name__)


class MetricsReporter:
    """Generate various reports from LLM metrics."""
    
    @staticmethod
    def print_summary(collector: LLMMetricsCollector):
        """Print a concise summary of LLM metrics."""
        print(collector.get_detailed_report())
    
    @staticmethod
    def save_json(collector: LLMMetricsCollector, filepath: str):
        """Save metrics to a JSON file."""
        data = collector.to_dict()
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        logger.info(f"Metrics saved to {filepath}")
    
    @staticmethod
    def get_cost_breakdown(collector: LLMMetricsCollector) -> Dict[str, Any]:
        """Get a cost breakdown by stage."""
        breakdown = {}
        for call in collector.calls:
            stage = call.stage
            if stage not in breakdown:
                breakdown[stage] = {"cost": 0.0, "calls": 0}
            breakdown[stage]["cost"] += call.total_cost
            breakdown[stage]["calls"] += 1
        
        return {
            "by_stage": breakdown,
            "total_cost": collector.total_cost,
            "most_expensive_stage": max(
                breakdown.items(), 
                key=lambda x: x[1]["cost"]
            )[0] if breakdown else None
        }
    
    @staticmethod
    def get_performance_metrics(collector: LLMMetricsCollector) -> Dict[str, Any]:
        """Get performance metrics."""
        if not collector.calls:
            return {}
        
        latencies = [call.latency_ms for call in collector.calls]
        tokens_per_second = [
            call.tokens_per_second for call in collector.calls 
            if call.tokens_per_second > 0
        ]
        
        return {
            "avg_latency_ms": sum(latencies) / len(latencies),
            "min_latency_ms": min(latencies),
            "max_latency_ms": max(latencies),
            "avg_tokens_per_second": sum(tokens_per_second) / len(tokens_per_second) if tokens_per_second else 0,
            "total_calls": len(collector.calls),
            "success_rate": sum(1 for call in collector.calls if call.success) / len(collector.calls) if collector.calls else 0,
        }
    
    @staticmethod
    def get_efficiency_scores(collector: LLMMetricsCollector) -> Dict[str, Any]:
        """Calculate efficiency scores for optimization."""
        if not collector.calls:
            return {}
        
        total_cost = collector.total_cost
        total_tokens = collector.total_tokens
        
        # Cost per token (lower is better)
        cost_per_token = (total_cost * 1000000) / total_tokens if total_tokens > 0 else 0
        
        # Tokens per second (higher is better)
        total_latency = sum(call.latency_ms for call in collector.calls) / 1000
        throughput = total_tokens / total_latency if total_latency > 0 else 0
        
        # Input vs output ratio
        input_ratio = collector.total_prompt_tokens / total_tokens if total_tokens > 0 else 0
        output_ratio = collector.total_completion_tokens / total_tokens if total_tokens > 0 else 0
        
        return {
            "cost_per_token_micro_usd": cost_per_token,
            "tokens_per_second": throughput,
            "input_ratio": input_ratio,
            "output_ratio": output_ratio,
            "recommendations": MetricsReporter._generate_recommendations(
                cost_per_token, throughput, input_ratio
            )
        }
    
    @staticmethod
    def _generate_recommendations(cost_per_token: float, throughput: float, input_ratio: float) -> List[str]:
        """Generate optimization recommendations."""
        recommendations = []
        
        if cost_per_token > 1.0:
            recommendations.append("High cost per token - consider using a cheaper model")
        
        if throughput < 50:
            recommendations.append("Low throughput - consider using a faster model or provider (e.g., Groq)")
        
        if input_ratio > 0.7:
            recommendations.append("High input token ratio - consider summarizing prompts or using prompt caching")
        
        if not recommendations:
            recommendations.append("Metrics look optimized!")
        
        return recommendations
    
    @staticmethod
    def print_efficiency_report(collector: LLMMetricsCollector):
        """Print an efficiency report with recommendations."""
        summary = collector.get_summary()
        costs = MetricsReporter.get_cost_breakdown(collector)
        perf = MetricsReporter.get_performance_metrics(collector)
        eff = MetricsReporter.get_efficiency_scores(collector)
        
        print("\n" + "=" * 80)
        print("LLM EFFICIENCY REPORT")
        print("=" * 80)
        
        print("\n📊 COST ANALYSIS:")
        print(f"  Total Cost: ${costs['total_cost']:.6f}")
        print(f"  Cost per Token: {eff.get('cost_per_token_micro_usd', 0):.4f} µ USD")
        if costs.get('most_expensive_stage'):
            print(f"  Most Expensive Stage: {costs['most_expensive_stage']}")
        
        print("\n⚡ PERFORMANCE:")
        print(f"  Avg Latency: {perf.get('avg_latency_ms', 0):.2f} ms")
        print(f"  Min/Max Latency: {perf.get('min_latency_ms', 0):.2f} / {perf.get('max_latency_ms', 0):.2f} ms")
        print(f"  Throughput: {perf.get('avg_tokens_per_second', 0):.2f} tokens/sec")
        print(f"  Success Rate: {perf.get('success_rate', 0)*100:.1f}%")
        
        print("\n💡 OPTIMIZATION RECOMMENDATIONS:")
        for rec in eff.get('recommendations', []):
            print(f"  • {rec}")
        
        print("\n📈 TOKEN DISTRIBUTION:")
        for stage, stats in sorted(summary.get('by_stage', {}).items()):
            print(f"  {stage}: {stats['tokens']:,} tokens ({stats['calls']} calls, ${stats['cost']:.6f})")
        
        print("\n" + "=" * 80)

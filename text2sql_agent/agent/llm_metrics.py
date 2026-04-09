"""
LLM Usage Metrics Tracking.
Tracks tokens, timing, costs, and other analytics for every LLM call.
"""

import logging
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List


logger = logging.getLogger(__name__)


TOKEN_PRICING = {
    "gpt-4o": {"input": 0.0025, "output": 0.01},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    "gpt-4": {"input": 0.03, "output": 0.06},
    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
    "openai/gpt-oss-120b": {"input": 0.0005, "output": 0.0015},
    "llama-3.1-70b-versatile": {"input": 0.0005, "output": 0.0015},
    "llama-3.1-8b-instant": {"input": 0.00005, "output": 0.00015},
}


@dataclass
class LLMCallMetrics:
    """Metrics for a single LLM call."""

    call_id: str
    stage: str
    model: str
    provider: str

    start_time: float
    end_time: Optional[float] = None

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    prompt_length: int = 0
    response_length: int = 0
    prompt_text: Optional[str] = None
    response_text: Optional[str] = None

    input_cost: float = 0.0
    output_cost: float = 0.0
    total_cost: float = 0.0

    temperature: float = 0.3
    success: bool = False
    error: Optional[str] = None

    latency_ms: float = 0.0
    tokens_per_second: float = 0.0

    def __post_init__(self):
        if self.end_time and self.start_time and not self.latency_ms:
            self.latency_ms = (self.end_time - self.start_time) * 1000
        if self.latency_ms > 0 and not self.tokens_per_second:
            self.tokens_per_second = (self.total_tokens / self.latency_ms) * 1000

    @property
    def prompt_preview(self) -> Optional[str]:
        return self.prompt_text

    @property
    def response_preview(self) -> Optional[str]:
        return self.response_text

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LLMMetricsCollector:
    """Collects and aggregates metrics across multiple LLM calls."""

    calls: List[LLMCallMetrics] = field(default_factory=list)
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0

    def add_call(self, metrics: LLMCallMetrics):
        self.calls.append(metrics)
        self.total_prompt_tokens += metrics.prompt_tokens
        self.total_completion_tokens += metrics.completion_tokens
        self.total_tokens += metrics.total_tokens
        self.total_cost += metrics.total_cost
        logger.debug(
            "Added metrics for %s: %s+%s tokens, $%.6f cost, %.0fms latency",
            metrics.stage,
            metrics.prompt_tokens,
            metrics.completion_tokens,
            metrics.total_cost,
            metrics.latency_ms,
        )

    def get_summary(self) -> Dict[str, Any]:
        if not self.calls:
            return {"total_calls": 0, "total_tokens": 0, "total_cost": 0.0}

        stats_by_stage: Dict[str, Dict[str, Any]] = {}
        for call in self.calls:
            stage_stats = stats_by_stage.setdefault(
                call.stage,
                {"calls": 0, "tokens": 0, "cost": 0.0, "avg_latency_ms": 0.0, "latencies": []},
            )
            stage_stats["calls"] += 1
            stage_stats["tokens"] += call.total_tokens
            stage_stats["cost"] += call.total_cost
            stage_stats["latencies"].append(call.latency_ms)

        for stats in stats_by_stage.values():
            if stats["latencies"]:
                stats["avg_latency_ms"] = sum(stats["latencies"]) / len(stats["latencies"])
            stats.pop("latencies", None)

        total_latency_ms = sum(call.latency_ms for call in self.calls)
        return {
            "total_calls": len(self.calls),
            "total_tokens": self.total_tokens,
            "prompt_tokens": self.total_prompt_tokens,
            "completion_tokens": self.total_completion_tokens,
            "total_cost_usd": round(self.total_cost, 6),
            "total_latency_ms": total_latency_ms,
            "avg_latency_ms_per_call": total_latency_ms / len(self.calls),
            "tokens_per_second": (self.total_tokens / total_latency_ms * 1000) if total_latency_ms > 0 else 0,
            "by_stage": stats_by_stage,
        }

    def get_detailed_report(self) -> str:
        summary = self.get_summary()
        if summary["total_calls"] == 0:
            return "No LLM calls made."

        lines = [
            "=" * 80,
            "LLM USAGE METRICS REPORT",
            "=" * 80,
            f"\nTotal Calls: {summary['total_calls']}",
            f"Total Tokens: {format_tokens_display(summary['total_tokens'])} ({format_tokens_display(summary['prompt_tokens'])} input, {format_tokens_display(summary['completion_tokens'])} output)",
            f"Total Cost: {format_cost_display(summary['total_cost_usd'])} USD",
            f"Total Latency: {summary['total_latency_ms']:.2f}ms",
            f"Avg Latency/Call: {summary['avg_latency_ms_per_call']:.2f}ms",
            f"Throughput: {summary['tokens_per_second']:.2f} tokens/second",
            "\n" + "-" * 80,
            "BREAKDOWN BY STAGE:",
            "-" * 80,
        ]

        for stage, stats in sorted(summary["by_stage"].items()):
            lines.extend([
                f"\n{stage.upper()}:",
                f"  Calls: {stats['calls']}",
                f"  Tokens: {format_tokens_display(stats['tokens'])}",
                f"  Cost: {format_cost_display(stats['cost'])}",
                f"  Avg Latency: {stats['avg_latency_ms']:.2f}ms",
            ])

        lines.append("\n" + "=" * 80)
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {"calls": [call.to_dict() for call in self.calls], "summary": self.get_summary()}


def calculate_cost(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    provider: Optional[str] = None,
) -> tuple:
    pricing = TOKEN_PRICING.get(model, {"input": 0.0, "output": 0.0})
    input_cost = (prompt_tokens / 1000) * pricing["input"]
    output_cost = (completion_tokens / 1000) * pricing["output"]
    total_cost = input_cost + output_cost
    return input_cost, output_cost, total_cost


def format_tokens_display(tokens: int) -> str:
    if tokens >= 1_000_000:
        return f"{tokens / 1_000_000:.1f}M"
    if tokens >= 1_000:
        return f"{tokens / 1_000:.1f}K"
    return str(tokens)


def format_cost_display(cost: float) -> str:
    if cost == 0:
        return "$0"
    if cost < 0.001:
        return f"${cost*1000:.3f}m"
    if cost < 0.1:
        return f"${cost*1000:.2f}m"
    return f"${cost:.4f}"

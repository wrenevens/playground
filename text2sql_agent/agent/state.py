"""
State management for Text-to-SQL agent.
Tracks all information throughout the agent workflow.
"""

from dataclasses import dataclass, field
from typing import Any, Optional
from datetime import datetime

from .llm_metrics import LLMMetricsCollector


@dataclass
class Text2SQLState:
    """
    Central state object for the text-to-SQL workflow.
    
    Tracks all inputs, intermediate results, and outputs
    for debugging, improvement, and evaluation.
    """
    
    # === INPUT ===
    question: str
    db_id: str
    evidence: Optional[str] = None
    
    # === NORMALIZED ===
    normalized_question: str = ""
    
    # === RETRIEVAL ===
    schema_context: dict = field(default_factory=dict)
    value_context: dict = field(default_factory=dict)
    
    # === PLANNING ===
    plan: dict = field(default_factory=dict)
    
    # === GENERATION ===
    candidates: list[str] = field(default_factory=list)
    candidate_confidence: list[float] = field(default_factory=list)
    
    # === VALIDATION ===
    validation_results: list[dict] = field(default_factory=list)
    best_valid_sql: Optional[str] = None
    
    # === REPAIR ===
    repair_attempts: int = 0
    repaired_sql: Optional[str] = None
    
    # === EXECUTION ===
    final_sql: Optional[str] = None
    execution_result: Optional[dict] = None
    
    # === LLM METRICS ===
    llm_metrics: LLMMetricsCollector = field(default_factory=LLMMetricsCollector)
    
    # === METADATA ===
    logs: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def add_log(self, stage: str, message: str, data: Optional[dict] = None):
        """Record a log entry for this stage."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "stage": stage,
            "message": message,
            "data": data or {}
        }
        self.logs.append(log_entry)
    
    def add_error(self, error: str):
        """Record an error."""
        self.errors.append(error)
        self.add_log("error", error)
    
    def to_dict(self) -> dict:
        """Convert state to dictionary for logging/serialization."""
        return {
            "question": self.question,
            "db_id": self.db_id,
            "evidence": self.evidence,
            "normalized_question": self.normalized_question,
            "schema_context": self.schema_context,
            "value_context": self.value_context,
            "plan": self.plan,
            "candidates": self.candidates,
            "candidate_confidence": self.candidate_confidence,
            "validation_results": self.validation_results,
            "best_valid_sql": self.best_valid_sql,
            "repair_attempts": self.repair_attempts,
            "repaired_sql": self.repaired_sql,
            "final_sql": self.final_sql,
            "execution_result": self.execution_result,
            "logs": self.logs,
            "errors": self.errors,
            "timestamp": self.timestamp,
            "llm_metrics": self.llm_metrics.to_dict()
        }

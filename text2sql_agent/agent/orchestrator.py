"""
Main orchestrator for the text-to-SQL workflow.
Coordinates all stages and manages the state machine.
"""

import logging
import json
from typing import Optional, Dict, Any
from .state import Text2SQLState
from .tools import ToolSet
from ..db.connector import DatabaseConnector
from ..db.schema_loader import SchemaLoader


logger = logging.getLogger(__name__)


class Text2SQLOrchestrator:
    """
    Main orchestrator that runs the 6-stage text-to-SQL workflow.

    Stages:
    1. Input normalization
    2. Schema retrieval
    3. SQL planning
    4. SQL generation
    5. SQL validation and repair
    6. Execution and return results
    """

    def __init__(self, connector: DatabaseConnector, llm_provider: str = "openai", llm_model: Optional[str] = None):
        self.connector = connector
        self.schema_loader = SchemaLoader(connector)
        self.tools = ToolSet(self.schema_loader, connector,
                             llm_provider=llm_provider, llm_model=llm_model)

        # Configuration
        self.max_generation_attempts = 3
        self.max_repair_attempts = 2
        self.max_candidates = 1

    def run(self, question: str, db_id: str, evidence: Optional[str] = None) -> Dict[str, Any]:
        """
        Run the complete text-to-SQL workflow.

        Args:
            question: Natural language question
            db_id: Database identifier
            evidence: Optional external evidence

        Returns:
            Final state dict with all logs and results
        """
        # Initialize state
        state = Text2SQLState(
            question=question,
            db_id=db_id,
            evidence=evidence
        )

        state.add_log("start", "Text-to-SQL workflow started")
        logger.info(f"Starting text-to-SQL for: {question}")

        try:
            # Stage A: Normalize input
            self._stage_normalize(state)

            # Stage B: Retrieve schema
            self._stage_schema_retrieval(state)

            # Stage C: Plan SQL
            self._stage_planning(state)

            # Stage D: Generate SQL
            self._stage_generation(state)

            # Stage E: Validate and repair
            self._stage_validation_and_repair(state)

            # Stage F: Execute and return
            self._stage_execution(state)

            state.add_log("complete", "Workflow completed successfully")
            logger.info("Workflow completed successfully")

        except Exception as e:
            state.add_error(f"Workflow failed: {str(e)}")
            logger.error(f"Workflow error: {e}", exc_info=True)

        return state.to_dict()

    def _stage_normalize(self, state: Text2SQLState):
        """Stage A: Normalize the input."""
        logger.info("Stage A: Normalizing input")

        # Simple normalization - remove extra whitespace
        normalized = " ".join(state.question.split())
        state.normalized_question = normalized

        state.add_log("normalize", "Input normalized",
                      {"original_len": len(state.question), "normalized_len": len(normalized)})

    def _stage_schema_retrieval(self, state: Text2SQLState):
        """Stage B: Retrieve schema context."""
        logger.info("Stage B: Retrieving schema")

        # Load schema if not already loaded
        self.schema_loader.load_schema()

        # Find relevant tables and columns
        self.tools.schema_search(state)

        if not state.schema_context:
            state.add_error("Failed to retrieve schema context")
            raise RuntimeError("Schema retrieval failed")

        # Also retrieve sample values
        self.tools.value_search(state)

        logger.info(f"Schema retrieved: {
                    len(state.schema_context.get('tables', []))} tables")

    def _stage_planning(self, state: Text2SQLState):
        """Stage C: Plan the SQL."""
        logger.info("Stage C: Planning SQL")

        if not state.schema_context:
            state.add_error("No schema context for planning")
            raise RuntimeError("Schema context required for planning")

        self.tools.plan_sql(state)

        if not state.plan:
            state.add_error("Failed to create SQL plan")
            raise RuntimeError("Planning failed")

        logger.info("SQL plan created")

    def _stage_generation(self, state: Text2SQLState):
        """Stage D: Generate SQL candidates."""
        logger.info(f"Stage D: Generating SQL ({
                    self.max_candidates} candidates)")

        if not state.plan:
            state.add_error("No plan for generation")
            raise RuntimeError("Plan required for generation")

        candidates = self.tools.generate_sql(
            state, num_candidates=self.max_candidates)

        if not candidates:
            state.add_error("Failed to generate SQL candidates")
            raise RuntimeError("SQL generation failed")

        logger.info(f"Generated {len(candidates)} candidates")

    def _stage_validation_and_repair(self, state: Text2SQLState):
        """Stage E: Validate and repair SQL."""
        logger.info("Stage E: Validating and repairing SQL")

        if not state.candidates:
            state.add_error("No candidates to validate")
            raise RuntimeError("No SQL candidates")

        best_valid_sql = None

        for idx, sql in enumerate(state.candidates):
            logger.info(f"Validating candidate {
                        idx + 1}/{len(state.candidates)}")

            # Try to validate
            validation = self.tools.validate_sql(state, sql)
            state.validation_results.append(validation)

            if validation["valid"]:
                best_valid_sql = sql
                logger.info(f"Candidate {idx + 1} is valid")
                break

            # If invalid, try to repair
            if state.repair_attempts < self.max_repair_attempts:
                logger.info(f"Attempting to repair candidate {idx + 1}")
                error = validation.get("error", "Unknown error")

                repaired = self.tools.repair_sql(state, sql, error)

                if repaired:
                    # Validate the repaired SQL
                    repair_validation = self.tools.validate_sql(
                        state, repaired)
                    state.validation_results.append(repair_validation)

                    if repair_validation["valid"]:
                        best_valid_sql = repaired
                        logger.info("Repaired SQL is valid")
                        break

        if best_valid_sql:
            state.best_valid_sql = best_valid_sql
            logger.info("Found valid SQL for execution")
        else:
            state.add_error("Failed to find or generate valid SQL")
            logger.warning("Could not find valid SQL")

    def _stage_execution(self, state: Text2SQLState):
        """Stage F: Execute the final SQL."""
        logger.info("Stage F: Executing SQL")

        if not state.best_valid_sql:
            state.add_error("No valid SQL to execute")
            state.execution_result = {"ok": False, "error": "No valid SQL"}
            return

        self.tools.execute_sql(state, state.best_valid_sql)

        if state.execution_result and state.execution_result.get("ok"):
            logger.info(f"Execution successful: {
                        state.execution_result['row_count']} rows")
        else:
            logger.warning(f"Execution failed: {state.execution_result}")

    def get_summary(self, state_dict: Dict) -> str:
        """
        Generate a human-readable summary of the workflow results.
        """
        execution_result = state_dict.get("execution_result") or {}
        summary = f"""
=== Text-to-SQL Summary ===
Question: {state_dict['question']}
Database: {state_dict['db_id']}

Final SQL: {state_dict.get('final_sql', 'N/A')}

    Execution Status: {'SUCCESS' if execution_result.get('ok') else 'FAILED'}
    Result Rows: {execution_result.get('row_count', 0)}

Errors: {len(state_dict.get('errors', []))}
Logs: {len(state_dict.get('logs', []))}

Full trace saved for debugging.
"""
        return summary

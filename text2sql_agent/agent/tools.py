"""
Tool implementations for the text-to-SQL agent.
Each tool focuses on one specific task in the workflow.
"""

import logging
import json
import re
from typing import Any, Dict, List, Optional, Tuple
from .llm_provider import call_llm
from .prompts import (
    SCHEMA_SEARCH_PROMPT, PLAN_SQL_PROMPT, GENERATE_SQL_PROMPT,
    REPAIR_SQL_PROMPT, VALIDATE_PROMPT
)
from .state import Text2SQLState
from ..db.schema_loader import SchemaLoader
from ..db.connector import DatabaseConnector


logger = logging.getLogger(__name__)


class ToolSet:
    """Collection of tools for the text-to-SQL agent."""
    
    def __init__(
        self,
        schema_loader: SchemaLoader,
        connector: DatabaseConnector,
        llm_provider: str = "openai",
        llm_model: Optional[str] = None
    ):
        self.schema_loader = schema_loader
        self.connector = connector
        self.llm_provider = llm_provider
        self.llm_model = llm_model
    
    # ===== TOOL 1: Schema Search =====
    def schema_search(self, state: Text2SQLState) -> Dict[str, Any]:
        """
        Find relevant tables and columns for the question.
        Uses LLM to understand which schema elements are needed.
        """
        logger.info(f"Schema search for: {state.question}")
        
        schema_str = self.schema_loader.get_full_schema_string()
        
        prompt = f"""Question: {state.question}

{schema_str}

Identify the most relevant tables and columns from the above schema that are needed to answer this question."""
        
        response = call_llm(SCHEMA_SEARCH_PROMPT, prompt, provider=self.llm_provider, model=self.llm_model)
        
        if not response:
            state.add_error("Schema search failed")
            return {}
        
        # Parse response to extract tables and columns
        schema_context = {
            "raw_response": response,
            "tables": self._extract_table_names(response),
            "columns": self._extract_column_names(response),
            "notes": []
        }
        
        state.schema_context = schema_context
        state.add_log("schema_search", "Schema context retrieved", schema_context)
        
        return schema_context
    
    # ===== TOOL 2: Value Search =====
    def value_search(self, state: Text2SQLState) -> Dict[str, Any]:
        """
        Find relevant sample values or business terms.
        Helps with WHERE clause construction.
        """
        logger.info("Value search")
        
        if not state.schema_context:
            state.add_error("No schema context for value search")
            return {}
        
        tables = state.schema_context.get("tables", [])
        
        # Try to find sample values from the tables mentioned
        matched_values = {}
        
        for table in tables[:3]:  # Limit to first 3 tables
            try:
                query = f"SELECT * FROM {table} LIMIT 3"
                rows, error = self.connector.execute_query(query)
                if error:
                    continue
                
                if rows:
                    matched_values[table] = {
                        "sample_rows": rows[:2]
                    }
            except Exception as e:
                logger.warning(f"Could not sample values from {table}: {e}")
                continue
        
        value_context = {
            "matched_values": matched_values
        }
        
        state.value_context = value_context
        state.add_log("value_search", "Value context retrieved", {"num_tables_sampled": len(matched_values)})
        
        return value_context
    
    # ===== TOOL 3: SQL Planning =====
    def plan_sql(self, state: Text2SQLState) -> Dict[str, Any]:
        """
        Create a structured plan for SQL generation.
        Forces reasoning before actual SQL writing.
        """
        logger.info("SQL planning")
        
        schema_info = f"Relevant tables: {', '.join(state.schema_context.get('tables', []))}"
        
        prompt = f"""Question: {state.question}

{schema_info}

Create a step-by-step plan to generate the SQL query. Include:
1. Tables to join
2. Join conditions
3. WHERE filters
4. Grouping/Aggregation
5. Sorting
6. Limits"""
        
        response = call_llm(PLAN_SQL_PROMPT, prompt, provider=self.llm_provider, model=self.llm_model)
        
        if not response:
            state.add_error("SQL planning failed")
            return {}
        
        plan = {
            "raw_plan": response,
            "steps": response.split("\n")
        }
        
        state.plan = plan
        state.add_log("plan_sql", "SQL plan created", plan)
        
        return plan
    
    # ===== TOOL 4: SQL Generation =====
    def generate_sql(self, state: Text2SQLState, num_candidates: int = 3) -> List[str]:
        """
        Generate one or more candidate SQL queries.
        """
        logger.info(f"SQL generation ({num_candidates} candidates)")
        
        schema_str = self.schema_loader.get_full_schema_string()
        plan_str = "\n".join(state.plan.get("steps", []))
        
        prompt = f"""Question: {state.question}

Plan:
{plan_str}

Schema:
{schema_str}

Generate {num_candidates} alternative SQL queries that answer this question.
Return each query on a separate line starting with 'SELECT'.
Only return SQL, no explanations."""
        
        response = call_llm(GENERATE_SQL_PROMPT, prompt, provider=self.llm_provider, model=self.llm_model)
        
        if not response:
            state.add_error("SQL generation failed")
            return []
        
        # Extract SQL queries
        candidates = self._extract_sql_queries(response)
        
        if not candidates:
            # Fallback: treat entire response as single SQL
            candidates = [response.strip()]
        
        state.candidates = candidates
        state.add_log("generate_sql", f"Generated {len(candidates)} candidates", 
                     {"num_candidates": len(candidates)})
        
        return candidates
    
    # ===== TOOL 5: SQL Validation =====
    def validate_sql(self, state: Text2SQLState, sql: str) -> Dict[str, Any]:
        """
        Validate a SQL query for syntax and correctness.
        """
        logger.info(f"Validating SQL: {sql[:50]}...")
        
        validation_result = {
            "sql": sql,
            "valid": False,
            "error": None,
            "execution_preview": []
        }
        
        # Check 1: Basic syntax and table/column existence
        syntax_ok, syntax_error = self._check_syntax(sql, state)
        if not syntax_ok:
            validation_result["error"] = syntax_error
            state.add_log("validate_sql", "Syntax check failed", {"error": syntax_error})
            return validation_result
        
        # Check 2: Try to execute on actual database
        rows, exec_error = self.connector.execute_query(sql)
        if exec_error:
            validation_result["error"] = f"Execution error: {exec_error}"
            state.add_log("validate_sql", "Execution failed", {"error": exec_error})
            return validation_result
        
        # All checks passed
        validation_result["valid"] = True
        validation_result["execution_preview"] = rows[:3] if rows else []
        
        state.add_log("validate_sql", "Validation passed", 
                     {"num_rows": len(rows)})
        
        return validation_result
    
    # ===== TOOL 6: SQL Repair =====
    def repair_sql(self, state: Text2SQLState, sql: str, error: str) -> Optional[str]:
        """
        Attempt to fix invalid SQL based on error message.
        """
        logger.info(f"Attempting SQL repair")
        
        schema_str = self.schema_loader.get_full_schema_string()
        
        repair_prompt = REPAIR_SQL_PROMPT.format(
            question=state.question,
            original_sql=sql,
            error=error,
            schema=schema_str
        )
        
        response = call_llm(REPAIR_SQL_PROMPT, repair_prompt, provider=self.llm_provider, model=self.llm_model)
        
        if not response:
            state.add_error("SQL repair failed")
            return None
        
        repaired = self._extract_sql_from_response(response)
        
        state.repair_attempts += 1
        state.repaired_sql = repaired
        state.add_log("repair_sql", "SQL repaired", 
                     {"original_error": error, "attempts": state.repair_attempts})
        
        return repaired
    
    # ===== TOOL 7: SQL Execution =====
    def execute_sql(self, state: Text2SQLState, sql: str) -> Dict[str, Any]:
        """
        Execute SQL and return results safely.
        """
        logger.info(f"Executing SQL")
        
        rows, error = self.connector.execute_query(sql)
        
        execution_result = {
            "ok": error is None,
            "rows": rows,
            "row_count": len(rows) if rows else 0,
            "error": error
        }
        
        state.execution_result = execution_result
        state.final_sql = sql
        
        state.add_log("execute_sql", "SQL executed", 
                     {"row_count": execution_result["row_count"], "error": error})
        
        return execution_result
    
    # ===== Helper methods =====
    
    def _extract_table_names(self, text: str) -> List[str]:
        """Extract table names from LLM response."""
        tables = self.schema_loader.get_table_names()
        mentioned_tables = []
        for table in tables:
            if table.lower() in text.lower():
                mentioned_tables.append(table)
        return mentioned_tables
    
    def _extract_column_names(self, text: str) -> List[str]:
        """Extract column references from LLM response."""
        columns = []
        for table in self.schema_loader.get_table_names():
            table_columns = self.schema_loader.get_column_names(table)
            for col in table_columns:
                if col.lower() in text.lower():
                    columns.append(f"{table}.{col}")
        return columns
    
    def _extract_sql_queries(self, text: str) -> List[str]:
        """Extract SQL queries from LLM response."""
        # Find all lines starting with SELECT
        queries = []
        lines = text.split("\n")
        current_query = []
        
        for line in lines:
            line = line.strip()
            if line.upper().startswith("SELECT"):
                if current_query:
                    queries.append(" ".join(current_query))
                current_query = [line]
            elif current_query:
                current_query.append(line)
        
        if current_query:
            queries.append(" ".join(current_query))
        
        return [q for q in queries if q.strip()]
    
    def _extract_sql_from_response(self, text: str) -> str:
        """Extract SQL from LLM response."""
        lines = text.split("\n")
        for line in lines:
            if line.strip().upper().startswith("SELECT"):
                return line.strip()
        return text.strip()
    
    def _check_syntax(self, sql: str, state: Text2SQLState) -> Tuple[bool, Optional[str]]:
        """
        Check basic SQL syntax and schema references.
        """
        sql_upper = sql.upper()
        
        # Check for required keywords
        if not any(sql_upper.startswith(kw) for kw in ["SELECT", "WITH"]):
            return False, "Query must start with SELECT or WITH"
        
        # Check for common mistakes
        if "SELECT *" in sql_upper and "FROM" not in sql_upper:
            return False, "SELECT * without FROM clause"
        
        # Extract mentioned tables
        mentioned_tables = self._extract_table_references(sql)
        all_tables = self.schema_loader.get_table_names()
        
        for table in mentioned_tables:
            if table not in all_tables:
                return False, f"Table '{table}' not found in schema"
        
        return True, None
    
    def _extract_table_references(self, sql: str) -> List[str]:
        """Extract table names referenced in SQL."""
        tables = []
        
        # Simple regex to find table names after FROM and JOIN
        import re
        from_matches = re.findall(r'\bFROM\s+(\w+)', sql, re.IGNORECASE)
        join_matches = re.findall(r'\bJOIN\s+(\w+)', sql, re.IGNORECASE)
        
        tables.extend(from_matches)
        tables.extend(join_matches)
        
        return list(set(tables))  # Remove duplicates

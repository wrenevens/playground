"""
Tool implementations for the text-to-SQL agent.
Each tool focuses on one specific task in the workflow.
"""

import logging
import json
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple
from .llm_provider import call_llm, call_llm_with_metrics
from .prompts import (
    SCHEMA_SEARCH_PROMPT, PLAN_SQL_PROMPT, GENERATE_SQL_PROMPT,
    REPAIR_SQL_PROMPT, VALIDATE_PROMPT
)
from .state import Text2SQLState
from ..db.schema_loader import SchemaLoader
from ..db.connector import DatabaseConnector
from ..configs.default import (
    SCHEMA_TOP_K_TABLES,
    SCHEMA_TOP_K_COLUMNS,
    SCHEMA_RERANK_CANDIDATES,
    SCHEMA_GRAPH_HOPS,
    SCHEMA_SAMPLE_ROW_LIMIT,
)


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
        Uses query-aware ranking plus graph connectivity to keep join keys.
        """
        logger.info(f"Schema search for: {state.question}")
        
        enriched_schema = self.schema_loader.build_enriched_schema(
            question=state.normalized_question or state.question,
            sample_limit=SCHEMA_SAMPLE_ROW_LIMIT,
        )
        state.add_log(
            "grast_sql.schema_enricher",
            "Built enriched schema and FD-style graph",
            {
                "num_tables": len(enriched_schema.get("tables", [])),
                "num_columns": len(enriched_schema.get("columns", [])),
                "num_graph_edges": len(enriched_schema.get("graph", {}).get("edges", [])),
            },
        )

        scored_columns = self._rank_columns(state.question, enriched_schema.get("columns", []))
        state.add_log(
            "grast_sql.query_aware_column_encoder",
            "Computed query-aware column relevance scores",
            {
                "top_candidates": [
                    {
                        "column": column.get("qualified_name"),
                        "score": round(float(column.get("score", 0.0)), 3),
                    }
                    for column in scored_columns[:SCHEMA_RERANK_CANDIDATES]
                ],
            },
        )

        rerank_candidates = scored_columns[:SCHEMA_RERANK_CANDIDATES]
        reranked_columns = self._llm_rerank_columns(state, rerank_candidates) or rerank_candidates
        state.add_log(
            "grast_sql.graph_based_reranker",
            "Reranked top columns with structural priors",
            {
                "input_candidates": [c.get("qualified_name") for c in rerank_candidates],
                "reranked_candidates": [c.get("qualified_name") for c in reranked_columns],
            },
        )

        selected_columns = reranked_columns[:SCHEMA_TOP_K_COLUMNS]

        selected_column_names = [column["qualified_name"] for column in selected_columns]
        connected_column_names = self.schema_loader.get_connected_columns(
            selected_column_names,
            max_hops=SCHEMA_GRAPH_HOPS,
        )
        state.add_log(
            "grast_sql.steiner_tree_spanner",
            "Expanded selected columns to preserve join connectivity",
            {
                "selected_columns": selected_column_names,
                "connected_columns": connected_column_names,
                "added_columns": [
                    col for col in connected_column_names if col not in set(selected_column_names)
                ],
                "max_hops": SCHEMA_GRAPH_HOPS,
            },
        )

        column_records = self._resolve_column_records(
            connected_column_names,
            enriched_schema,
        )
        selected_tables = self._rank_tables_from_columns(column_records)
        table_names = [table["table"] for table in selected_tables[:SCHEMA_TOP_K_TABLES]]

        compact_schema = self._build_compact_schema_text(selected_tables, column_records)
        join_paths = self._build_join_paths(column_records, enriched_schema.get("graph", {}))

        schema_context = {
            "tables": table_names,
            "selected_tables": selected_tables[:SCHEMA_TOP_K_TABLES],
            "columns": column_records,
            "selected_columns": selected_columns,
            "graph": enriched_schema.get("graph", {}),
            "join_paths": join_paths,
            "compact_schema": compact_schema,
            "grast_sql": {
                "stage_names": [
                    "schema_enricher",
                    "query_aware_column_encoder",
                    "graph_based_reranker",
                    "steiner_tree_spanner",
                ],
                "ranked_top_k": [col.get("qualified_name") for col in reranked_columns[:SCHEMA_TOP_K_COLUMNS]],
                "connected_top_k": connected_column_names,
            },
            "notes": [
                "Columns ranked by query relevance and boosted by schema structure.",
                "Key columns were retained to preserve valid join paths.",
            ],
        }

        state.schema_context = schema_context
        state.add_log(
            "schema_search",
            "Schema context retrieved",
            {
                "tables": table_names,
                "selected_columns": selected_column_names,
                "connected_columns": connected_column_names,
                "join_paths": join_paths,
            },
        )

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
        
        schema_info = state.schema_context.get("compact_schema") or f"Relevant tables: {', '.join(state.schema_context.get('tables', []))}"
        
        prompt = f"""Question: {state.question}

{schema_info}

Create a step-by-step plan to generate the SQL query. Include:
1. Tables to join
2. Join conditions
3. WHERE filters
4. Grouping/Aggregation
5. Sorting
6. Limits"""
        
        from .llm_metrics import LLMCallMetrics
        response, metrics = call_llm_with_metrics(
            PLAN_SQL_PROMPT, prompt, 
            provider=self.llm_provider, 
            model=self.llm_model, 
            stage="plan_sql"
        )
        
        if metrics:
            call_obj = LLMCallMetrics(**metrics)
            state.llm_metrics.add_call(call_obj)
        
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
        
        from .llm_metrics import LLMCallMetrics
        
        schema_str = state.schema_context.get("compact_schema") or self.schema_loader.get_full_schema_string()
        plan_str = "\n".join(state.plan.get("steps", []))
        
        prompt = f"""Question: {state.question}

Plan:
{plan_str}

Schema:
{schema_str}

Generate {num_candidates} alternative SQL queries that answer this question.
Return each query on a separate line starting with 'SELECT'.
Only return SQL, no explanations."""
        
        response, metrics = call_llm_with_metrics(
            GENERATE_SQL_PROMPT, prompt, 
            provider=self.llm_provider, 
            model=self.llm_model, 
            stage="generate_sql"
        )
        
        if metrics:
            call_obj = LLMCallMetrics(**metrics)
            state.llm_metrics.add_call(call_obj)
        
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
        
        from .llm_metrics import LLMCallMetrics
        
        schema_str = self.schema_loader.get_full_schema_string()
        
        repair_prompt = REPAIR_SQL_PROMPT.format(
            question=state.question,
            original_sql=sql,
            error=error,
            schema=schema_str
        )
        
        response, metrics = call_llm_with_metrics(
            REPAIR_SQL_PROMPT, repair_prompt, 
            provider=self.llm_provider, 
            model=self.llm_model, 
            stage="repair_sql"
        )
        
        if metrics:
            call_obj = LLMCallMetrics(**metrics)
            state.llm_metrics.add_call(call_obj)
        
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

    def _rank_columns(self, question: str, columns: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Score columns by lexical relevance, descriptions, and structural importance."""
        question_tokens = self._tokenize_text(question)
        ranked = []

        for column in columns:
            score = float(column.get("score", 0.0))
            evidence = []
            table_name = column.get("table", "")
            column_name = column.get("column", "")
            description = column.get("description", "")
            sample_values = " ".join(column.get("sample_values", []))
            search_space = f"{table_name} {column_name} {description} {sample_values}".lower()

            for token in question_tokens:
                if token in column_name.lower():
                    score += 4.0
                    evidence.append(f"column:{token}")
                elif token in table_name.lower():
                    score += 2.5
                    evidence.append(f"table:{token}")
                elif token in search_space:
                    score += 1.0
                    evidence.append(f"text:{token}")

            if column.get("is_primary_key"):
                score += 1.5
            if column.get("is_foreign_key"):
                score += 1.2
            if column.get("key_type") == "table_key":
                score += 0.75

            ranked.append({**column, "score": score, "evidence": sorted(set(evidence))})

        return sorted(ranked, key=lambda item: item["score"], reverse=True)

    def _llm_rerank_columns(self, state: Text2SQLState, candidates: List[Dict[str, Any]]) -> Optional[List[Dict[str, Any]]]:
        """Ask the LLM to rerank the top candidates while preserving structure-aware candidates."""
        if not candidates:
            return None

        from .llm_metrics import LLMCallMetrics

        payload = [
            {
                "qualified_name": column["qualified_name"],
                "description": column.get("description", ""),
                "sample_values": column.get("sample_values", []),
                "is_primary_key": column.get("is_primary_key", False),
                "is_foreign_key": column.get("is_foreign_key", False),
                "score": column.get("score", 0.0),
            }
            for column in candidates
        ]

        prompt = f"""Question: {state.question}

Candidate columns:
{json.dumps(payload, indent=2)}

Return JSON only in this format:
{{
  "ranked_columns": ["table.column", "table.column", ...]
}}

Keep key columns that are required for valid joins even if they are not lexically obvious."""

        response, metrics = call_llm_with_metrics(
            SCHEMA_SEARCH_PROMPT, prompt, 
            provider=self.llm_provider, 
            model=self.llm_model, 
            stage="rerank_columns"
        )
        
        if metrics:
            call_obj = LLMCallMetrics(**metrics)
            state.llm_metrics.add_call(call_obj)
        
        if not response:
            return None

        parsed = self._extract_json_object(response)
        if not parsed:
            return None

        ranked_names = parsed.get("ranked_columns") or parsed.get("columns")
        if not isinstance(ranked_names, list):
            return None

        candidate_map = {column["qualified_name"]: column for column in candidates}
        reranked = [candidate_map[name] for name in ranked_names if name in candidate_map]
        return reranked or None

    def _resolve_column_records(self, qualified_names: List[str], enriched_schema: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Map qualified column names back to their enriched column records."""
        candidate_map = {column["qualified_name"]: column for column in enriched_schema.get("columns", [])}
        resolved = []
        for qualified_name in qualified_names:
            column = candidate_map.get(qualified_name)
            if column:
                resolved.append(column)
        return resolved

    def _rank_tables_from_columns(self, columns: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Aggregate column scores into table scores."""
        table_scores = defaultdict(lambda: {"table": "", "score": 0.0, "columns": []})
        for column in columns:
            table_name = column.get("table", "")
            entry = table_scores[table_name]
            entry["table"] = table_name
            entry["score"] = max(entry["score"], float(column.get("score", 0.0)))
            entry["columns"].append(column)

        return sorted(table_scores.values(), key=lambda item: item["score"], reverse=True)

    def _build_compact_schema_text(self, tables: List[Dict[str, Any]], columns: List[Dict[str, Any]]) -> str:
        """Build a compact schema snippet for planning and generation prompts."""
        lines = ["RELEVANT SCHEMA:"]
        table_to_columns: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for column in columns:
            table_to_columns[column.get("table", "")].append(column)

        for table in tables:
            table_name = table.get("table", "")
            lines.append(f"Table: {table_name}")
            relevant_columns = sorted(
                table_to_columns.get(table_name, []),
                key=lambda item: item.get("score", 0.0),
                reverse=True,
            )
            for column in relevant_columns:
                flags = []
                if column.get("is_primary_key"):
                    flags.append("PK")
                if column.get("is_foreign_key"):
                    flags.append("FK")
                flag_text = f" [{', '.join(flags)}]" if flags else ""
                sample_values = column.get("sample_values", [])
                sample_text = f" Sample: {', '.join(sample_values[:3])}." if sample_values else ""
                lines.append(
                    f"  - {column.get('column')} ({column.get('type', '')}){flag_text}: {column.get('description', '')}{sample_text}"
                )
            lines.append("")

        return "\n".join(lines).strip()

    def _build_join_paths(self, columns: List[Dict[str, Any]], graph: Dict[str, Any]) -> List[str]:
        """Summarize likely join paths from the selected columns and graph edges."""
        edges = graph.get("edges", [])
        involved_tables = {column.get("table") for column in columns if column.get("table")}
        join_clauses = []

        for edge in edges:
            source_table = edge["source"].split(".", 1)[0]
            target_table = edge["target"].split(".", 1)[0]
            if source_table in involved_tables and target_table in involved_tables and source_table != target_table:
                join_clauses.append(f"{edge['source']} -> {edge['target']} ({edge['type']})")

        return sorted(set(join_clauses))

    def _extract_json_object(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract a JSON object from model output, even if wrapped in markdown fences."""
        candidates = []
        stripped = text.strip()

        if stripped.startswith("{") and stripped.endswith("}"):
            candidates.append(stripped)

        fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
        if fence_match:
            candidates.append(fence_match.group(1))

        brace_match = re.search(r"\{.*\}", text, re.DOTALL)
        if brace_match:
            candidates.append(brace_match.group(0))

        for candidate in candidates:
            try:
                return json.loads(candidate)
            except Exception:
                continue
        return None

    def _tokenize_text(self, text: str) -> List[str]:
        """Tokenize text into useful lowercase query terms."""
        return [token for token in re.findall(r"[a-z0-9_]+", text.lower()) if len(token) > 1]
    
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

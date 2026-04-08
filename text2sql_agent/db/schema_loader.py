"""
Schema loading and caching for databases.
Loads and indexes table/column information.
"""

import logging
import re
from collections import defaultdict, deque
from typing import Dict, List, Optional, Tuple, Any
from .connector import DatabaseConnector


logger = logging.getLogger(__name__)


class SchemaLoader:
    """Load and cache database schema information."""
    
    def __init__(self, connector: DatabaseConnector):
        self.connector = connector
        self._schema_cache = {}
        self._enriched_cache = {}
        self._tables_cache = None
    
    def load_schema(self, force_refresh: bool = False) -> Dict:
        """
        Load full schema from database.
        
        Args:
            force_refresh: if True, ignore cache and reload
        
        Returns:
            Schema dict with tables and columns
        """
        if self._schema_cache and not force_refresh:
            return self._schema_cache
        
        schema = {
            "tables": {},
            "table_names": [],
            "primary_keys": {},
            "foreign_keys": {},
            "graph": {"nodes": {}, "edges": []}
        }
        
        try:
            tables = self.connector.get_table_names()
            schema["table_names"] = tables
            
            for table_name in tables:
                columns = self.connector.get_columns(table_name)
                primary_keys = self._get_primary_keys(table_name, columns)
                foreign_keys = self._get_foreign_keys(table_name, columns, tables)
                samples = self._get_sample_rows(table_name)

                schema["tables"][table_name] = {
                    "columns": columns,
                    "column_names": [col["name"] for col in columns],
                    "primary_keys": primary_keys,
                    "foreign_keys": foreign_keys,
                    "sample_rows": samples,
                    "description": self._generate_table_description(table_name, columns, samples)
                }

                schema["primary_keys"][table_name] = primary_keys
                schema["foreign_keys"][table_name] = foreign_keys

            schema["graph"] = self._build_fd_graph(schema)
            
            self._schema_cache = schema
            self._enriched_cache = {}
            logger.info(f"Loaded schema with {len(tables)} tables")
            return schema
        
        except Exception as e:
            logger.error(f"Error loading schema: {e}")
            raise
    
    def get_table_names(self) -> List[str]:
        """Get all table names."""
        if not self._schema_cache:
            self.load_schema()
        return self._schema_cache.get("table_names", [])
    
    def get_table_columns(self, table_name: str) -> List[Dict]:
        """Get columns for a specific table."""
        if not self._schema_cache:
            self.load_schema()
        
        tables = self._schema_cache.get("tables", {})
        if table_name in tables:
            return tables[table_name]["columns"]
        return []
    
    def get_column_names(self, table_name: str) -> List[str]:
        """Get column names for a specific table."""
        if not self._schema_cache:
            self.load_schema()
        
        tables = self._schema_cache.get("tables", {})
        if table_name in tables:
            return tables[table_name]["column_names"]
        return []
    
    def column_exists(self, table_name: str, column_name: str) -> bool:
        """Check if a column exists in a table."""
        columns = self.get_column_names(table_name)
        return column_name in columns
    
    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists."""
        return table_name in self.get_table_names()
    
    def get_full_schema_string(self) -> str:
        """
        Get a formatted string representation of the schema.
        Useful for passing to LLM.
        """
        if not self._schema_cache:
            self.load_schema()
        
        schema_str = "DATABASE SCHEMA:\n\n"
        
        for table_name in self._schema_cache.get("table_names", []):
            schema_str += f"Table: {table_name}\n"
            table_info = self._schema_cache.get("tables", {}).get(table_name, {})
            if table_info.get("description"):
                schema_str += f"  Description: {table_info['description']}\n"
            if table_info.get("primary_keys"):
                schema_str += f"  Primary keys: {', '.join(table_info['primary_keys'])}\n"
            columns = self.get_table_columns(table_name)
            for col in columns:
                col_name = col['name']
                col_type = col.get('type', '')
                column_description = self._generate_column_description(
                    table_name,
                    col_name,
                    col_type,
                    table_info.get("sample_rows", [])
                )
                suffix = []
                if col_name in table_info.get("primary_keys", []):
                    suffix.append("PK")
                if self._column_is_foreign_key(table_name, col_name, table_info.get("foreign_keys", [])):
                    suffix.append("FK")
                suffix_text = f" [{', '.join(suffix)}]" if suffix else ""
                schema_str += f"  - {col_name} ({col_type}){suffix_text}: {column_description}\n"
            schema_str += "\n"
        
        return schema_str

    def build_enriched_schema(self, question: Optional[str] = None, sample_limit: int = 3) -> Dict[str, Any]:
        """
        Build an enriched schema view with table/column metadata and a dependency graph.
        Cached per question so repeated retrieval is cheap.
        """
        cache_key = question or "__no_question__"
        if cache_key in self._enriched_cache:
            return self._enriched_cache[cache_key]

        if not self._schema_cache:
            self.load_schema()

        question_tokens = self._tokenize_question(question or "")
        tables = self._schema_cache.get("table_names", [])
        enriched_columns = []

        for table_name in tables:
            table_info = self._schema_cache["tables"].get(table_name, {})
            columns = table_info.get("columns", [])
            sample_rows = table_info.get("sample_rows", [])[:sample_limit]
            primary_keys = set(table_info.get("primary_keys", []))
            foreign_keys = table_info.get("foreign_keys", [])

            for column in columns:
                column_name = column["name"]
                column_type = column.get("type", "")
                sample_values = self._sample_values_from_rows(sample_rows, column_name)
                description = self._generate_column_description(
                    table_name,
                    column_name,
                    column_type,
                    sample_rows
                )
                key_type = self._classify_key(table_name, column_name, primary_keys, foreign_keys)
                lexical_score = self._lexical_score(
                    question_tokens,
                    table_name,
                    column_name,
                    description,
                    sample_values,
                    key_type,
                )

                enriched_columns.append({
                    "table": table_name,
                    "column": column_name,
                    "qualified_name": f"{table_name}.{column_name}",
                    "type": column_type,
                    "description": description,
                    "sample_values": sample_values,
                    "is_primary_key": column_name in primary_keys,
                    "is_foreign_key": self._column_is_foreign_key(table_name, column_name, foreign_keys),
                    "key_type": key_type,
                    "score": lexical_score,
                })

        graph = self._schema_cache.get("graph", {"nodes": {}, "edges": []})
        enriched_schema = {
            "tables": tables,
            "table_info": self._schema_cache.get("tables", {}),
            "columns": enriched_columns,
            "graph": graph,
        }

        self._enriched_cache[cache_key] = enriched_schema
        return enriched_schema

    def get_connected_columns(self, selected_columns: List[str], max_hops: int = 2) -> List[str]:
        """
        Expand a set of selected columns to a connected subset using the FD graph.
        This plays the role of a Steiner-style spanner by inserting key columns
        needed to preserve join connectivity.
        """
        if not selected_columns:
            return []

        if not self._schema_cache:
            self.load_schema()

        graph = self._schema_cache.get("graph", {"nodes": {}, "edges": []})
        adjacency = self._build_adjacency(graph)
        selected = [column for column in selected_columns if column in graph.get("nodes", {})]

        if not selected:
            return []

        connected = set(selected)
        terminal_tables = {column.split(".", 1)[0] for column in selected}

        # Always keep key columns from selected tables.
        for column_name, node in graph.get("nodes", {}).items():
            if node.get("table") in terminal_tables and node.get("key_type") in {"primary_key", "foreign_key"}:
                connected.add(column_name)

        # Connect terminals with shortest paths through the graph.
        for source in selected:
            for target in selected:
                if source == target:
                    continue
                for node in self._shortest_path(adjacency, source, target, max_hops=max_hops):
                    connected.add(node)

        return sorted(connected)

    def get_column_record(self, table_name: str, column_name: str) -> Dict[str, Any]:
        """Return a rich column record for a table/column pair."""
        if not self._schema_cache:
            self.load_schema()

        table_info = self._schema_cache.get("tables", {}).get(table_name, {})
        for column in table_info.get("columns", []):
            if column.get("name") == column_name:
                return {
                    "table": table_name,
                    "column": column_name,
                    "type": column.get("type", ""),
                    "description": self._generate_column_description(
                        table_name,
                        column_name,
                        column.get("type", ""),
                        table_info.get("sample_rows", []),
                    ),
                    "sample_values": self._sample_values_from_rows(table_info.get("sample_rows", []), column_name),
                    "is_primary_key": column_name in table_info.get("primary_keys", []),
                    "is_foreign_key": self._column_is_foreign_key(table_name, column_name, table_info.get("foreign_keys", [])),
                }
        return {}

    def _get_sample_rows(self, table_name: str, limit: int = 3) -> List[Dict[str, Any]]:
        """Fetch a small set of sample rows for metadata enrichment."""
        try:
            rows, error = self.connector.execute_query(f"SELECT * FROM {table_name} LIMIT {int(limit)}")
            return rows if not error else []
        except Exception:
            return []

    def _get_primary_keys(self, table_name: str, columns: Optional[List[Dict[str, Any]]] = None) -> List[str]:
        """Get declared or inferred primary keys for a table."""
        keys: List[str] = []
        try:
            if hasattr(self.connector, "connection") and self.connector.connection:
                cursor = self.connector.connection.cursor()
                if self.connector.__class__.__name__ == "SQLiteConnector":
                    cursor.execute(f"PRAGMA table_info({table_name})")
                    keys = [row[1] for row in cursor.fetchall() if row[5]]
                else:
                    cursor.execute(
                        """
                        SELECT kcu.column_name
                        FROM information_schema.table_constraints tc
                        JOIN information_schema.key_column_usage kcu
                          ON tc.constraint_name = kcu.constraint_name
                         AND tc.table_schema = kcu.table_schema
                        WHERE tc.constraint_type = 'PRIMARY KEY'
                          AND tc.table_name = %s
                        ORDER BY kcu.ordinal_position
                        """,
                        (table_name,),
                    )
                    keys = [row[0] for row in cursor.fetchall()]
                cursor.close()
        except Exception:
            keys = []

        if not keys:
            keys = self._infer_primary_keys(table_name, column_names=[col.get("name", "") for col in (columns or [])])
        return keys

    def _get_foreign_keys(
        self,
        table_name: str,
        columns: Optional[List[Dict[str, Any]]] = None,
        all_tables: Optional[List[str]] = None,
    ) -> List[Dict[str, str]]:
        """Get declared or inferred foreign keys for a table."""
        foreign_keys: List[Dict[str, str]] = []
        try:
            if hasattr(self.connector, "connection") and self.connector.connection:
                cursor = self.connector.connection.cursor()
                if self.connector.__class__.__name__ == "SQLiteConnector":
                    cursor.execute(f"PRAGMA foreign_key_list({table_name})")
                    for row in cursor.fetchall():
                        foreign_keys.append({"column": row[3], "ref_table": row[2], "ref_column": row[4]})
                else:
                    cursor.execute(
                        """
                        SELECT kcu.column_name, ccu.table_name AS foreign_table_name, ccu.column_name AS foreign_column_name
                        FROM information_schema.table_constraints tc
                        JOIN information_schema.key_column_usage kcu
                          ON tc.constraint_name = kcu.constraint_name
                         AND tc.table_schema = kcu.table_schema
                        JOIN information_schema.constraint_column_usage ccu
                          ON ccu.constraint_name = tc.constraint_name
                         AND ccu.table_schema = tc.table_schema
                        WHERE tc.constraint_type = 'FOREIGN KEY'
                          AND tc.table_name = %s
                        """,
                        (table_name,),
                    )
                    for row in cursor.fetchall():
                        foreign_keys.append({"column": row[0], "ref_table": row[1], "ref_column": row[2]})
                cursor.close()
        except Exception:
            foreign_keys = []

        if not foreign_keys:
            foreign_keys = self._infer_foreign_keys(
                table_name,
                column_names=[col.get("name", "") for col in (columns or [])],
                all_tables=all_tables,
            )
        return foreign_keys

    def _infer_primary_keys(self, table_name: str, column_names: Optional[List[str]] = None) -> List[str]:
        """Infer a primary key from naming conventions if one is not declared."""
        if column_names is None:
            column_names = [column.get("name", "") for column in self.connector.get_columns(table_name)]
        if not column_names:
            return []

        preferred = [
            f"{table_name}_id",
            f"{self._singularize(table_name)}_id",
            "id",
        ]
        for candidate in preferred:
            if candidate in column_names:
                return [candidate]

        for column_name in column_names:
            if column_name.endswith("_id"):
                return [column_name]

        return [column_names[0]]

    def _infer_foreign_keys(
        self,
        table_name: str,
        column_names: Optional[List[str]] = None,
        all_tables: Optional[List[str]] = None,
    ) -> List[Dict[str, str]]:
        """Infer likely foreign keys from naming conventions."""
        if column_names is None:
            column_names = [column.get("name", "") for column in self.connector.get_columns(table_name)]
        if all_tables is None:
            all_tables = self.connector.get_table_names()
        all_tables = set(all_tables)
        inferred: List[Dict[str, str]] = []

        for column_name in column_names:
            if not column_name.endswith("_id"):
                continue
            if column_name in self._infer_primary_keys(table_name, column_names):
                continue

            base = column_name[:-3]
            candidates = [base, self._singularize(base), f"{base}s", f"{base}_table"]
            for candidate in candidates:
                if candidate in all_tables:
                    ref_keys = self._infer_primary_keys(candidate)
                    if ref_keys:
                        inferred.append({"column": column_name, "ref_table": candidate, "ref_column": ref_keys[0], "inferred": True})
                        break

        return inferred

    def _build_fd_graph(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Build a functional-dependency-style graph over columns."""
        nodes: Dict[str, Dict[str, Any]] = {}
        edges: List[Dict[str, Any]] = []

        for table_name in schema.get("table_names", []):
            table_info = schema.get("tables", {}).get(table_name, {})
            primary_keys = set(table_info.get("primary_keys", []))
            foreign_keys = table_info.get("foreign_keys", [])
            columns = table_info.get("columns", [])

            for column in columns:
                qualified_name = f"{table_name}.{column['name']}"
                key_type = self._classify_key(table_name, column["name"], primary_keys, foreign_keys)
                nodes[qualified_name] = {
                    "table": table_name,
                    "column": column["name"],
                    "type": column.get("type", ""),
                    "key_type": key_type,
                }

            for fk in foreign_keys:
                src = f"{table_name}.{fk['column']}"
                dst = f"{fk['ref_table']}.{fk['ref_column']}"
                if src in nodes and dst in nodes:
                    edges.append({"source": src, "target": dst, "type": "foreign_key", "weight": 0})
                    edges.append({"source": dst, "target": src, "type": "foreign_key_reverse", "weight": 0})

            pk_candidates = list(primary_keys) or self._infer_primary_keys(table_name)
            pk = pk_candidates[0] if pk_candidates else None
            if pk:
                pk_node = f"{table_name}.{pk}"
                for column in columns:
                    qualified_name = f"{table_name}.{column['name']}"
                    if qualified_name == pk_node:
                        continue
                    edge_type = "column_to_primary_key"
                    if self._column_is_foreign_key(table_name, column["name"], foreign_keys):
                        edge_type = "column_to_foreign_key"
                    edges.append({"source": qualified_name, "target": pk_node, "type": edge_type, "weight": 1})
                    edges.append({"source": pk_node, "target": qualified_name, "type": f"{edge_type}_reverse", "weight": 1})

        return {"nodes": nodes, "edges": edges}

    def _build_adjacency(self, graph: Dict[str, Any]) -> Dict[str, List[str]]:
        adjacency: Dict[str, List[str]] = defaultdict(list)
        for edge in graph.get("edges", []):
            adjacency[edge["source"]].append(edge["target"])
        return adjacency

    def _shortest_path(self, adjacency: Dict[str, List[str]], source: str, target: str, max_hops: int = 2) -> List[str]:
        if source == target:
            return [source]

        queue = deque([(source, [source])])
        visited = {source}

        while queue:
            node, path = queue.popleft()
            if len(path) - 1 > max_hops:
                continue
            for neighbor in adjacency.get(node, []):
                if neighbor in visited:
                    continue
                next_path = path + [neighbor]
                if neighbor == target:
                    return next_path
                visited.add(neighbor)
                queue.append((neighbor, next_path))

        return []

    def _tokenize_question(self, question: str) -> List[str]:
        return [token for token in re.findall(r"[a-z0-9_]+", question.lower()) if len(token) > 1]

    def _lexical_score(
        self,
        question_tokens: List[str],
        table_name: str,
        column_name: str,
        description: str,
        sample_values: List[str],
        key_type: str,
    ) -> float:
        score = 0.0
        text = " ".join([table_name, column_name, description, " ".join(sample_values)]).lower()
        table_tokens = set(re.findall(r"[a-z0-9_]+", table_name.lower()))
        column_tokens = set(re.findall(r"[a-z0-9_]+", column_name.lower()))

        for token in question_tokens:
            if token in column_tokens:
                score += 4.0
            elif token in table_tokens:
                score += 2.0
            elif token in text:
                score += 1.0

        if column_name.endswith("_id"):
            score += 0.5
        if key_type == "primary_key":
            score += 1.5
        elif key_type == "foreign_key":
            score += 1.25
        elif key_type == "table_key":
            score += 0.5

        return score

    def _classify_key(
        self,
        table_name: str,
        column_name: str,
        primary_keys: set,
        foreign_keys: List[Dict[str, str]],
    ) -> str:
        if column_name in primary_keys:
            return "primary_key"
        if self._column_is_foreign_key(table_name, column_name, foreign_keys):
            return "foreign_key"
        if column_name.endswith("_id") or column_name == "id":
            return "table_key"
        return "regular"

    def _column_is_foreign_key(self, table_name: str, column_name: str, foreign_keys: List[Dict[str, str]]) -> bool:
        return any(fk.get("column") == column_name for fk in foreign_keys)

    def _sample_values_from_rows(self, rows: List[Dict[str, Any]], column_name: str, limit: int = 3) -> List[str]:
        values: List[str] = []
        for row in rows:
            if column_name not in row:
                continue
            value = row.get(column_name)
            if value is None:
                continue
            text = str(value)
            if text not in values:
                values.append(text)
            if len(values) >= limit:
                break
        return values

    def _generate_table_description(self, table_name: str, columns: List[Dict[str, Any]], sample_rows: List[Dict[str, Any]]) -> str:
        column_summary = ", ".join(col.get("name", "") for col in columns[:6])
        sample_hint = ""
        if sample_rows:
            first_row = sample_rows[0]
            pairs = [f"{key}={value}" for key, value in list(first_row.items())[:3]]
            sample_hint = f" Sample row includes {', '.join(pairs)}."
        return f"Table {table_name.replace('_', ' ')} with columns {column_summary}.{sample_hint}".strip()

    def _generate_column_description(self, table_name: str, column_name: str, column_type: str, sample_rows: List[Dict[str, Any]]) -> str:
        sample_values = self._sample_values_from_rows(sample_rows, column_name)
        sample_text = f" Sample values: {', '.join(sample_values)}." if sample_values else ""
        return f"{table_name}.{column_name} ({column_type}) likely stores {column_name.replace('_', ' ')}.{sample_text}".strip()

    def _singularize(self, name: str) -> str:
        if name.endswith("ies"):
            return name[:-3] + "y"
        if name.endswith("ses"):
            return name[:-2]
        if name.endswith("s") and len(name) > 1:
            return name[:-1]
        return name

"""
Schema loading and caching for databases.
Loads and indexes table/column information.
"""

import logging
from typing import Dict, List, Optional
from .connector import DatabaseConnector


logger = logging.getLogger(__name__)


class SchemaLoader:
    """Load and cache database schema information."""
    
    def __init__(self, connector: DatabaseConnector):
        self.connector = connector
        self._schema_cache = {}
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
            "table_names": []
        }
        
        try:
            tables = self.connector.get_table_names()
            schema["table_names"] = tables
            
            for table_name in tables:
                columns = self.connector.get_columns(table_name)
                schema["tables"][table_name] = {
                    "columns": columns,
                    "column_names": [col["name"] for col in columns]
                }
            
            self._schema_cache = schema
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
            columns = self.get_table_columns(table_name)
            for col in columns:
                schema_str += f"  - {col['name']} ({col['type']})\n"
            schema_str += "\n"
        
        return schema_str

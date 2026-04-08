"""
Database connector for custom databases.
Supports SQLite, PostgreSQL, MySQL, and other SQL databases.
"""

import sqlite3
import logging
from typing import Any, List, Dict, Optional, Tuple
from abc import ABC, abstractmethod
import importlib


logger = logging.getLogger(__name__)


class DatabaseConnector(ABC):
    """Abstract base class for database connections."""
    
    @abstractmethod
    def connect(self):
        """Establish connection to database."""
        pass
    
    @abstractmethod
    def disconnect(self):
        """Close database connection."""
        pass
    
    @abstractmethod
    def execute_query(self, sql: str) -> Tuple[List[Dict], Optional[str]]:
        """
        Execute SQL query and return results.
        Returns: (list of result rows as dicts, error message if any)
        """
        pass
    
    @abstractmethod
    def get_table_names(self) -> List[str]:
        """Get all table names in the database."""
        pass
    
    @abstractmethod
    def get_columns(self, table_name: str) -> List[Dict[str, str]]:
        """
        Get columns for a table.
        Returns: list of dicts with 'name' and 'type' keys.
        """
        pass


class SQLiteConnector(DatabaseConnector):
    """SQLite database connector."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.connection = None
    
    def connect(self):
        """Establish SQLite connection."""
        try:
            self.connection = sqlite3.connect(self.db_path)
            self.connection.row_factory = sqlite3.Row
            logger.info(f"Connected to SQLite database: {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to connect to SQLite: {e}")
            raise
    
    def disconnect(self):
        """Close SQLite connection."""
        if self.connection:
            self.connection.close()
            logger.info("SQLite connection closed")
    
    def execute_query(self, sql: str) -> Tuple[List[Dict], Optional[str]]:
        """Execute SQL query and return results."""
        try:
            cursor = self.connection.cursor()
            cursor.execute(sql)
            
            # Fetch results
            rows = cursor.fetchall()
            result_list = [dict(row) for row in rows]
            
            cursor.close()
            return result_list, None
        
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Query execution error: {error_msg}\nSQL: {sql}")
            return [], error_msg
    
    def get_table_names(self) -> List[str]:
        """Get all table names from SQLite."""
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
            )
            tables = [row[0] for row in cursor.fetchall()]
            cursor.close()
            return tables
        except Exception as e:
            logger.error(f"Error getting table names: {e}")
            return []
    
    def get_columns(self, table_name: str) -> List[Dict[str, str]]:
        """Get columns for a table in SQLite."""
        try:
            cursor = self.connection.cursor()
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = []
            for row in cursor.fetchall():
                columns.append({
                    "name": row[1],
                    "type": row[2]
                })
            cursor.close()
            return columns
        except Exception as e:
            logger.error(f"Error getting columns for {table_name}: {e}")
            return []


class PostgreSQLConnector(DatabaseConnector):
    """PostgreSQL database connector."""
    
    def __init__(self, host: str, port: int, database: str, user: str, password: str):
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.connection = None
    
    def connect(self):
        """Establish PostgreSQL connection."""
        try:
            pg = importlib.import_module("psycopg2")
            self.connection = pg.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password
            )
            logger.info(f"Connected to PostgreSQL: {self.host}:{self.port}/{self.database}")
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            raise
    
    def disconnect(self):
        """Close PostgreSQL connection."""
        if self.connection:
            self.connection.close()
            logger.info("PostgreSQL connection closed")
    
    def execute_query(self, sql: str) -> Tuple[List[Dict], Optional[str]]:
        """Execute SQL query and return results."""
        try:
            cursor = self.connection.cursor()
            cursor.execute(sql)
            
            # Get column names
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            
            # Fetch results
            rows = cursor.fetchall()
            result_list = [dict(zip(columns, row)) for row in rows]
            
            cursor.close()
            return result_list, None
        
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Query execution error: {error_msg}\nSQL: {sql}")
            return [], error_msg
    
    def get_table_names(self) -> List[str]:
        """Get all table names from PostgreSQL."""
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='public';"
            )
            tables = [row[0] for row in cursor.fetchall()]
            cursor.close()
            return tables
        except Exception as e:
            logger.error(f"Error getting table names: {e}")
            return []
    
    def get_columns(self, table_name: str) -> List[Dict[str, str]]:
        """Get columns for a table in PostgreSQL."""
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = %s;",
                (table_name,)
            )
            columns = [
                {"name": row[0], "type": row[1]}
                for row in cursor.fetchall()
            ]
            cursor.close()
            return columns
        except Exception as e:
            logger.error(f"Error getting columns for {table_name}: {e}")
            return []


def get_connector(db_type: str, **kwargs) -> DatabaseConnector:
    """
    Factory function to get the appropriate database connector.
    
    Args:
        db_type: 'sqlite', 'postgresql', 'mysql', etc.
        **kwargs: database-specific parameters
    
    Returns:
        DatabaseConnector instance
    """
    if db_type.lower() == "sqlite":
        return SQLiteConnector(kwargs.get("db_path"))
    elif db_type.lower() in ("postgresql", "postgres"):
        return PostgreSQLConnector(
            host=kwargs.get("host", "localhost"),
            port=kwargs.get("port", 5432),
            database=kwargs.get("database"),
            user=kwargs.get("user"),
            password=kwargs.get("password")
        )
    else:
        raise ValueError(f"Unsupported database type: {db_type}")

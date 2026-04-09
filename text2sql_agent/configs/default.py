"""
Configuration file for text-to-SQL agent.
"""

# LLM Configuration
DEFAULT_LLM_PROVIDER = "openai"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_GROQ_MODEL = "llama-3.1-8b-instant"
LLM_TEMPERATURE = 0.3

# Schema Retrieval Configuration
SCHEMA_TOP_K_TABLES = 5
SCHEMA_TOP_K_COLUMNS = 12
SCHEMA_RERANK_CANDIDATES = 8
SCHEMA_GRAPH_HOPS = 2
SCHEMA_SAMPLE_ROW_LIMIT = 3

# Workflow Configuration
MAX_GENERATION_ATTEMPTS = 3
MAX_REPAIR_ATTEMPTS = 2
MAX_CANDIDATES = 5

# Database Configuration (defaults)
DEFAULT_DB_TYPE = "sqlite"
DEFAULT_DB_PATH = "database.db"

# Logging Configuration
LOG_LEVEL = "INFO"  # INFO, DEBUG, WARNING
SAVE_LOGS = True
LOG_DIR = "./logs"

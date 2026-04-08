# Text-to-SQL Agent for Custom Databases

A modular, pure Python text-to-SQL agent that converts natural language questions to SQL queries on custom databases.

## Features

- **6-stage pipeline**: Normalize → Retrieve Schema → Plan → Generate → Validate → Execute
- **Modular tool system**: Each stage has independent, testable tools
- **Multi-LLM support**: OpenAI (GPT-3.5, GPT-4), Groq (Mixtral, Llama), easily extensible
- **Error recovery**: Automatic SQL repair and retry logic
- **Custom database support**: SQLite, PostgreSQL, easily extensible to others
- **Full trace logging**: Every step is logged for debugging and improvement
- **Spider2-lite evaluation**: Built-in evaluator for benchmarking

## Project Structure

```
text2sql_agent/
├── agent/
│   ├── state.py           # State management
│   ├── orchestrator.py    # Main workflow
│   ├── tools.py           # 8 core tools
│   ├── llm_provider.py    # LLM interface
│   └── prompts.py        # System prompts
├── db/
│   ├── connector.py       # Database connections
│   └── schema_loader.py  # Schema management
├── evaluation/
│   └── run_spider2lite.py # Spider2-lite evaluation
├── configs/
│   └── default.py        # Configuration
├── logs/                  # Output logs (auto-created)
├── main.py               # CLI entry point
└── requirements.txt
```

## Installation

```bash
# Clone or download the project
cd text2sql_agent

# Install dependencies
pip install -r requirements.txt

# Set API key (choose one)
export OPENAI_API_KEY="your-key-here"
# or
export GROQ_API_KEY="your-groq-key-here"

# Optional: configure default model names for entire codebase
export OPENAI_MODEL="gpt-4o-mini"
export GROQ_MODEL="openai/gpt-oss-120b"
```

## Quick Start

### 1. Simple CLI Usage

Query a SQLite database:

```bash
python main.py \
  --db-type sqlite \
  --db-path ./my_database.db \
  --question "How many orders were placed in 2023?" \
  --db-id my_db
```

Query a PostgreSQL database:

```bash
python main.py \
  --db-type postgresql \
  --db-host localhost \
  --db-port 5432 \
  --db-name mydb \
  --db-user postgres \
  --db-password mypassword \
  --question "Show top 10 customers by revenue" \
  --db-id production_db
```

### 2. Programmatic Usage

```python
from agent.orchestrator import Text2SQLOrchestrator
from db.connector import get_connector

# Connect to database
connector = get_connector(
    db_type="sqlite",
    db_path="./database.db"
)
connector.connect()

# Create orchestrator
orchestrator = Text2SQLOrchestrator(connector)

# Run workflow
result = orchestrator.run(
    question="Show me customers with more than 5 orders",
    db_id="my_database"
)

# Results
print(f"SQL: {result['final_sql']}")
print(f"Rows: {result['execution_result']['row_count']}")
print(f"Logs: {len(result['logs'])} steps")

connector.disconnect()
```

### 3. Spider2-lite Evaluation

Evaluate on Spider2-lite dataset:

```bash
python evaluation/run_spider2lite.py \
  --spider-data /path/to/spider2lite.json \
  --db-type sqlite \
  --db-path /path/to/spider2lite.db \
  --limit 100 \
  --output ./eval_results
```

Results saved to:
- `eval_results/results.json` - Individual query results
- `eval_results/metrics.json` - Summary metrics

### 4. Using Groq (Faster & Cheaper)

Groq provides fast, affordable LLM inference perfect for SQL generation:

```bash
# Query with Groq (recommended)
python main.py \
  --db-type sqlite \
  --db-path ./database.db \
  --question "Your question" \
  --llm-provider groq \
  --llm-model openai/gpt-oss-120b

# Use different Groq models
--llm-model gpt-oss-20b                # Faster
--llm-model openai/gpt-oss-120b        # Default
# or configure once globally:
# export GROQ_MODEL="openai/gpt-oss-120b"

# Evaluate on Spider2-lite with Groq
python evaluation/run_spider2lite.py \
  --spider-data /path/to/spider2lite.json \
  --db-path /path/to/spider2lite.db \
  --llm-provider groq \
  --llm-model openai/gpt-oss-120b
```

**Setup**: `export GROQ_API_KEY="gsk_..."` (get free key at https://console.groq.com)

**Benefits**: ⚡ Faster, 💰 Cheaper, 🔓 Open-source models

See [GROQ_SETUP.md](GROQ_SETUP.md) for detailed guide.

## Workflow Stages

### Stage A: Normalize
- Standardize question format
- Remove redundant whitespace

### Stage B: Schema Retrieval
- Identify relevant tables (using LLM)
- Identify relevant columns
- Retrieve sample values

### Stage C: Planning
- Generate logical plan (not SQL)
- Specify joins, filters, grouping

### Stage D: Generation
- Generate 3-5 candidate SQL queries
- Use LLM with plan and schema context

### Stage E: Validation & Repair
- Validate syntax and schema references
- Try to execute queries
- Auto-repair invalid ones
- Retry up to 2 times

### Stage F: Execution
- Execute best valid SQL
- Return rows and metadata
- Save complete trace

## Configuration

Edit `configs/default.py` to customize:

- LLM model (gpt-3.5-turbo, gpt-4)
- Retry limits (generation, repair)
- Number of candidate queries
- Logging level

## Logs and Debugging

Every run creates detailed logs:

```json
{
  "question": "...",
  "db_id": "...",
  "logs": [
    {
      "timestamp": "2024-01-01T12:00:00",
      "stage": "schema_search",
      "message": "Schema context retrieved",
      "data": {...}
    },
    ...
  ],
  "errors": ["..."],
  "final_sql": "...",
  "execution_result": {...}
}
```

Pass `--output result.json` to save the complete trace.

## Customization

### Add a New Database Type

```python
from db.connector import DatabaseConnector

class MyDatabaseConnector(DatabaseConnector):
    def connect(self):
        # Connect logic
        pass
    
    def execute_query(self, sql: str):
        # Execution logic
        pass
    
    # ... implement other required methods

# Register in get_connector() factory
```

### Add New LLM Provider

```python
from agent.llm_provider import LLMProvider

class MyLLMProvider(LLMProvider):
    """Example: Add Claude/Anthropic support"""
    
    def __init__(self, model: str = "claude-3-sonnet", temperature: float = 0.3):
        super().__init__(model, temperature)
    
    def initialize(self):
        """Initialize your LLM client."""
        try:
            from anthropic import Anthropic
            self.client = Anthropic()
            logger.info(f"Initialized Anthropic with model: {self.model}")
        except ImportError:
            logger.error("Anthropic client not available. Install: pip install anthropic")
            raise
    
    def call(self, system_prompt: str, user_message: str) -> Optional[str]:
        """Call your LLM."""
        if not self.client:
            self.initialize()
        
        try:
            response = self.client.messages.create(
                model=self.model,
                temperature=self.temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}]
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"API call failed: {e}")
            return None

# Register in get_llm() factory
if provider == "anthropic":
    _llm_instances[cache_key] = MyLLMProvider(model=model)
```

Then use it:
```bash
python main.py --db-type sqlite --db-path db.db --question "..." --llm-provider anthropic
```
```

### Customize Prompts

Edit `agent/prompts.py` to adjust system prompts for each stage.

## Limitations & Future Work

- **LLM dependent**: Quality depends on LLM model and prompts
- **No semantic equivalence checking**: Doesn't check if generated SQL returns same results as gold
- **Limited to deterministic SQL**: Assumes deterministic queries
- **No multi-modal context**: Text only; can be extended to use images, etc.

## Development

Run tests (when available):

```bash
pytest tests/
```

Check code style:

```bash
black text2sql_agent/
flake8 text2sql_agent/
```

## License

MIT

## Support

For issues or questions, check:
1. Logs in `./logs/`
2. Saved traces in JSON output
3. Detailed error messages in stdout

Trace every run for improvement and debugging.

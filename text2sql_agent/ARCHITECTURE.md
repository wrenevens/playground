# Text-to-SQL Agent - Architecture Document

## Overview

This is a production-grade text-to-SQL agent built in pure Python for custom databases. It follows a 6-stage modular pipeline with clear separation of concerns and extensive logging.

## Core Design Principles

1. **Modularity**: Each stage is independent and can be tested/customized separately
2. **Determinism**: Uses LLM only for interpretation; all validation is deterministic code
3. **Observability**: Every step is logged for debugging and improvement
4. **Extensibility**: Easy to add new database types, LLM providers, or tools
5. **Robustness**: Includes error recovery and retry logic

## 6-Stage Pipeline

### Stage 1: Input Normalization
**File**: `agent/orchestrator.py::_stage_normalize()`

```
User Question → Normalize → Cleaned Question
```

- Remove extra whitespace
- Standardize format
- Prepare for downstream stages

**Output**: `Text2SQLState.normalized_question`

---

### Stage 2: Schema Retrieval
**Files**: `agent/tools.py::schema_search()`, `db/schema_loader.py`

```
Normalized Question + Full Schema → LLM → Relevant Tables/Columns
```

- Load full database schema using `SchemaLoader`
- Use LLM to identify relevant tables and columns
- Retrieve sample values for filtering hints

**Tools Used**:
- `schema_search()` - LLM-based table/column relevance
- `value_search()` - Sample data retrieval

**Output**: `Text2SQLState.schema_context` + `Text2SQLState.value_context`

---

### Stage 3: SQL Planning
**File**: `agent/tools.py::plan_sql()`

```
Question + Schema Context → LLM → Logical Plan (not SQL)
```

- Force reasoning before generation
- Create structured plan with:
  - Tables to join
  - Filter conditions
  - Grouping/aggregation
  - Ordering and limits

**Purpose**: Reduces hallucinated SQL by planning first

**Output**: `Text2SQLState.plan`

---

### Stage 4: SQL Generation
**File**: `agent/tools.py::generate_sql()`

```
Question + Plan + Schema → LLM → 3-5 Candidate SQL Queries
```

- Generate multiple candidates for redundancy
- Use LLM with rich context from previous stages
- Extract SQL from LLM response

**Parameters**:
- `num_candidates`: Number of alternative queries (default: 3-5)

**Output**: `Text2SQLState.candidates`

---

### Stage 5: Validation & Repair
**Files**: `agent/tools.py::validate_sql()`, `agent/tools.py::repair_sql()`

```
Candidate SQL →┬→ Check Syntax/Schema
               ├→ Try Execution
               └→ Repair if Failed →┬→ Validate Again
                                    └→ Repeat (max 2 times)
```

**Validation Steps**:
1. Syntax check (regex-based)
2. Schema validation (table/column existence)
3. Execution attempt (try on real database)
4. If failed, LLM attempts repair
5. Retry up to 2 times

**Output**: `Text2SQLState.best_valid_sql`

---

### Stage 6: Execution
**File**: `agent/tools.py::execute_sql()`

```
Best Valid SQL → Execute on Database → Rows + Metadata
```

- Execute using `DatabaseConnector`
- Return rows and execution metadata
- Save trace for logging

**Output**: `Text2SQLState.execution_result`

---

## Key Components

### 1. State Management (`agent/state.py`)

Central state object that flows through the pipeline:

```python
Text2SQLState:
  - Input: question, db_id, evidence
  - Intermediate: normalized_question, schema_context, plan, candidates
  - Validation: validation_results, best_valid_sql, repair_attempts
  - Output: final_sql, execution_result
  - Metadata: logs, errors, timestamp
```

**Key Methods**:
- `add_log()` - Record a step with contextual data
- `add_error()` - Record errors
- `to_dict()` - Serialize for JSON output

---

### 2. Orchestrator (`agent/orchestrator.py`)

Coordinates all stages and manages error handling:

```python
Text2SQLOrchestrator:
  - __init__(connector)
  - run(question, db_id, evidence) → state_dict
  - _stage_A() through _stage_F()
```

**Error Handling**:
- Catches exceptions at each stage
- Logs errors and continues
- Returns final state with error details

**Configuration**:
- `max_generation_attempts`
- `max_repair_attempts`
- `max_candidates`

---

### 3. Tool Set (`agent/tools.py`)

Collection of 8 focused tools:

```
1. schema_search()     - Find relevant schema
2. value_search()      - Get sample values
3. plan_sql()          - Create logical plan
4. generate_sql()      - Generate candidates
5. validate_sql()      - Check validity
6. repair_sql()        - Fix invalid SQL
7. execute_sql()       - Run on database
8. (Helper methods)    - Extract/parse utils
```

Each tool:
- Takes state as input
- Updates state in place
- Returns structured result
- Logs all actions

---

### 4. Database Connectors (`db/connector.py`)

Abstract interface + implementations:

```python
DatabaseConnector (ABC):
  - connect()
  - disconnect()
  - execute_query(sql) → (rows, error)
  - get_table_names() → [str]
  - get_columns(table) → [{"name": str, "type": str}]

SQLiteConnector(DatabaseConnector)
PostgreSQLConnector(DatabaseConnector)
```

**Extensibility**: Implement interface for new database types

---

### 5. Schema Loader (`db/schema_loader.py`)

Caches and manages database schema:

```python
SchemaLoader:
  - load_schema(force_refresh=False)
  - get_table_names() → [str]
  - get_table_columns(table) → [dict]
  - column_exists(table, column) → bool
  - table_exists(table) → bool
  - get_full_schema_string() → str
```

**Features**:
- In-memory caching
- Formatted output for LLM
- Validation utilities

---

### 6. LLM Provider (`agent/llm_provider.py`)

Abstracts LLM interactions:

```python
LLMProvider:
  - initialize()
  - call(system_prompt, user_message) → response_text
  
get_llm() → LLMProvider (global singleton)
call_llm(system, user) → response (convenience function)
```

**Easy Customization**:
- Swap OpenAI for another provider
- Change model or temperature
- Add custom prompt preprocessing

---

### 7. System Prompts (`agent/prompts.py`)

Unified prompt management:

```
SCHEMA_SEARCH_PROMPT    - Find relevant schema
PLAN_SQL_PROMPT         - Create logical plan
GENERATE_SQL_PROMPT     - Generate SQL
REPAIR_SQL_PROMPT       - Fix broken SQL
VALIDATE_PROMPT         - Check validity
```

**Easy Customization**: Edit strings to tune behavior

---

## Data Flow

```
┌─────────────────────────────────────────────────────────┐
│                   User Question                          │
└──────────────────┬──────────────────────────────────────┘
                   │
         ┌─────────▼──────────┐
         │  Stage A: Normalize │
         └─────────┬──────────┘
                   │
      ┌────────────▼────────────┐
      │ Stage B: Schema Retrieval│ ◄─── SchemaLoader
      └────────────┬────────────┘       DatabaseConnector
                   │
         ┌─────────▼──────────┐
         │   Stage C: Planning  │ ◄─── LLMProvider
         └─────────┬──────────┘
                   │
        ┌──────────▼──────────┐
        │ Stage D: Generation  │ ◄─── LLMProvider
        └──────────┬──────────┘
                   │
    ┌──────────────▼──────────────┐
    │ Stage E: Validation & Repair │ ◄─── DatabaseConnector
    └──────────────┬──────────────┘       LLMProvider
                   │
         ┌─────────▼──────────┐
         │  Stage F: Execution  │ ◄─── DatabaseConnector
         └─────────┬──────────┘
                   │
      ┌────────────▼────────────┐
      │     Result + Trace       │
      │  (JSON serializable)     │
      └──────────────────────────┘
```

---

## State Transitions

```
New Question
    ↓
[State: Input only]
    ↓ Stage A
[State: normalized_question]
    ↓ Stage B
[State: + schema_context, value_context]
    ↓ Stage C
[State: + plan]
    ↓ Stage D
[State: + candidates]
    ↓ Stage E
[State: + validation_results, best_valid_sql]
    ↓ Stage F
[State: + final_sql, execution_result]
    ↓
[Final Output: to_dict()]
```

---

## Error Handling Strategy

### Errors are Recorded, Not Terminating

```python
try:
    result = self.tools.validate_sql(state, sql)
except Exception as e:
    state.add_error(str(e))
    # Continue to next candidate
    continue
```

### Retry Logic

```
For each candidate:
  - Try validation
  - If fails: attempt repair (up to 2 times)
  - If still fails: move to next candidate
  
If all candidates fail:
  - Set best_valid_sql to None
  - Record summary in errors
  - Return partial result
```

### Logging

Every error is logged with context:

```json
{
  "timestamp": "2024-01-01T12:00:00",
  "stage": "validate_sql",
  "message": "Syntax check failed",
  "data": {
    "error": "no such column",
    "sql": "SELECT invalid_col FROM orders"
  }
}
```

---

## Configuration

Edit `configs/default.py`:

```python
LLM_MODEL = "gpt-3.5-turbo"  # or "gpt-4"
LLM_TEMPERATURE = 0.3        # 0-1, lower = more deterministic

MAX_GENERATION_ATTEMPTS = 3
MAX_REPAIR_ATTEMPTS = 2
MAX_CANDIDATES = 5

LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR
SAVE_LOGS = True
LOG_DIR = "./logs"
```

---

## Testing & Debugging

### 1. Run Example Queries

```bash
python example.py
```

### 2. Test Single Query

```bash
python main.py \
  --db-type sqlite \
  --db-path ./test.db \
  --question "Your question" \
  --output result.json \
  --verbose
```

### 3. Inspect Logs

```bash
cat result.json | jq '.logs'
cat result.json | jq '.errors'
cat result.json | jq '.final_sql'
```

### 4. Evaluate on Spider2-lite

```bash
python evaluation/run_spider2lite.py \
  --spider-data test.json \
  --limit 10 \
  --output results \
  --verbose
```

---

## Extensibility

### Add New Database Type

```python
# In db/connector.py
class MongoDBConnector(DatabaseConnector):
    def connect(self): ...
    def execute_query(self, sql): ...
    # ...

# In db/connector.py get_connector()
if db_type == "mongodb":
    return MongoDBConnector(**kwargs)
```

### Add New Tool

```python
# In agent/tools.py
def new_tool(self, state: Text2SQLState) -> Dict:
    # Your logic
    state.add_log("new_tool", "Description")
    return result

# In agent/orchestrator.py
def _stage_new(self, state: Text2SQLState):
    self.tools.new_tool(state)
```

### Use Different LLM

```python
# In agent/llm_provider.py
class AnthropicLLM(LLMProvider):
    def call(self, system_prompt, user_message):
        # Use Claude API
        pass
```

### Tune Prompts

Edit `agent/prompts.py` strings to adjust:
- System instructions
- Output format expectations
- Specific guidance per stage

---

## Performance Considerations

### Bottlenecks

1. **LLM calls**: Most time spent here
   - Minimize number of candidates
   - Use faster models (gpt-3.5 vs gpt-4)
   - Batch if possible

2. **Database queries**: Schema loading and validation
   - Cache schema (`SchemaLoader`)
   - Limit sample rows

3. **Repair loops**: Multiple retries
   - Tune prompts to reduce errors
   - Set reasonable retry limits

### Optimizations

- Schema caching reduces retrieval time
- Parallel candidate validation (future)
- Model quantization for local LLMs
- Cache of successful patterns

---

## Monitoring & Improvement

### Metrics to Track

From evaluation runner:
- Success rate: % of queries that execute
- Error distribution: Types of failures
- Repair rate: % fixed by repair tool
- Avg steps per query: Workflow efficiency

### Improvement Loop

1. Run on dataset
2. Analyze failures
3. Categorize errors
4. Tune prompts/config
5. Re-run and compare
6. Iterate

---

## Future Enhancements

- [ ] Semantic SQL equivalence checking
- [ ] Multi-turn conversational refinement
- [ ] Query result verification
- [ ] Schema context ranking
- [ ] Few-shot example selection
- [ ] Custom database-specific prompts
- [ ] Parallel candidate evaluation
- [ ] Result formatting templates
- [ ] Custom metric definitions
- [ ] Fine-tuned models for SQL

---

## Files Reference

| File | Purpose |
|------|---------|
| `state.py` | Central state dataclass |
| `orchestrator.py` | Main workflow coordinator |
| `tools.py` | 8 core tools |
| `llm_provider.py` | LLM interface |
| `prompts.py` | System prompts |
| `connector.py` | Database connections |
| `schema_loader.py` | Schema management |
| `main.py` | CLI entry point |
| `example.py` | Example usage |
| `run_spider2lite.py` | Evaluation runner |

---

End of Architecture Document

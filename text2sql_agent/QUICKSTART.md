# Getting Started - 5 Minutes to Your First Query

## 1. Prerequisites

```bash
# Check Python version (3.7+)
python --version

# Set OpenAI API key
export OPENAI_API_KEY="sk-..."
```

## 2. Install

```bash
# Install dependencies
pip install -r requirements.txt
```

## 3. Run Example

```bash
# This creates a sample database and runs 5 queries
python quickstart.py
```

Expected output:
```
[Query 1/5] How many customers are from the USA?
Generated SQL:
  SELECT COUNT(*) FROM customers WHERE country = 'USA'
  
Results (1 rows):
  {'COUNT(*)': 1}
...
```

## 4. Query Your Own Database

### SQLite

```bash
python main.py \
  --db-type sqlite \
  --db-path ./my_database.db \
  --question "How many orders in total?" \
  --db-id my_db
```

### PostgreSQL

```bash
python main.py \
  --db-type postgresql \
  --db-host localhost \
  --db-port 5432 \
  --db-name mydb \
  --db-user postgres \
  --db-password password \
  --question "Show top 10 customers by revenue" \
  --db-id production
```

## 5. Save Results

```bash
python main.py \
  --db-type sqlite \
  --db-path ./database.db \
  --question "Your question" \
  --output result.json
```

View results:
```bash
# View final SQL
jq '.final_sql' result.json

# View execution status
jq '.execution_result' result.json

# View complete workflow steps
jq '.logs' result.json
```

## 6. Evaluate on Dataset

```bash
python evaluation/run_spider2lite.py \
  --spider-data spider2lite.json \
  --db-path spider2lite.db \
  --limit 50
```

Results saved to `./evaluation_results/`

## Troubleshooting

### OpenAI API Error
```
Error: 'NoneType' object is not subscriptable
```
→ Check your `OPENAI_API_KEY` is set correctly

### Database Connection Error
```
Error: no such file or directory: 'database.db'
```
→ Check `--db-path` points to correct file

### SQL Generation Failure
→ Check logs with `--verbose` flag
→ Adjust prompts in `agent/prompts.py`

## Next Steps

- **Read [README.md](README.md)** for full documentation
- **Read [ARCHITECTURE.md](ARCHITECTURE.md)** for system design
- **Edit [agent/prompts.py](agent/prompts.py)** to customize
- **Extend [db/connector.py](db/connector.py)** for new databases

## Key Files

| File | What to do |
|------|-----------|
| `main.py` | Run on custom databases |
| `example.py` | See example usage |
| `agent/prompts.py` | Tune prompts |
| `agent/orchestrator.py` | Understand workflow |
| `evaluation/run_spider2lite.py` | Benchmark agent |

**Happy querying!** 🚀

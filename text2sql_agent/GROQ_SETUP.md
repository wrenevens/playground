# Using Groq with Text-to-SQL Agent

Groq is a fast LLM inference platform perfect for the SQL generation task. It's often faster and cheaper than OpenAI while maintaining quality.

## Quick Setup

### 1. Get a Groq API Key

```bash
# Sign up for free at https://console.groq.com
# Copy your API key
export GROQ_API_KEY="gsk_..."
```

### 2. Install Groq Client

```bash
pip install groq>=0.4.0
```

### 3. Use with Agent

**Option A: Command Line**

```bash
python main.py \
  --db-type sqlite \
  --db-path ./database.db \
  --question "Show me all customers" \
  --llm-provider groq \
  --llm-model openai/gpt-oss-120b
```

**Option B: Python Code**

```python
from agent.orchestrator import Text2SQLOrchestrator
from db.connector import get_connector

connector = get_connector(db_type="sqlite", db_path="db.db")
connector.connect()

orchestrator = Text2SQLOrchestrator(
    connector,
    llm_provider="groq",
  llm_model="openai/gpt-oss-120b"
)

result = orchestrator.run(question="Your question", db_id="my_db")

print(f"SQL: {result['final_sql']}")
print(f"Rows: {result['execution_result']['row_count']}")
```

**Option C: Example Script**

```bash
python example.py
# The script auto-detects your GROQ_API_KEY and uses it
```

## Available Groq Models

| Model | Speed | Quality | Context | Cost | Use Case |
|-------|-------|---------|---------|------|----------|
| `gpt-oss-20b` | ⚡⚡⚡ Very Fast | Good | Provider-defined | Low | Quick queries, testing |
| `openai/gpt-oss-120b` | ⚡⚡ Fast | Excellent | Provider-defined | Low | **Recommended for SQL** |
| `llama-3-70b-8192` | ⚡ Fast | Best | 8K | Medium | Complex queries |
| `llama-2-70b-4096` | ⚡ Fast | Good | 4K | Low | Legacy support |

**Recommendation for SQL**: Use `openai/gpt-oss-120b` (current default in this codebase)

## Groq vs OpenAI Comparison

| Feature | Groq | OpenAI |
|---------|------|--------|
| **Speed** | ⚡ Very Fast (100+ tok/sec) | Medium (50-80 tok/sec) |
| **Cost** | Lower | Higher |
| **Quality** | Excellent for SQL | Excellent for SQL |
| **Context Window** | 32K |  128K (GPT-4 Turbo) |
| **Availability** | Low rate limits (free tier) | Higher limits |
| **Setup** | Simple | Simple |

## Example: Spider2-lite Evaluation with Groq

```bash
python evaluation/run_spider2lite.py \
  --spider-data spider2lite.json \
  --db-path spider2lite.db \
  --llm-provider groq \
  --llm-model openai/gpt-oss-120b \
  --limit 100
```

## Comparison: Run Same Query on Both

```bash
# With OpenAI (GPT-3.5)
python main.py \
  --db-type sqlite \
  --db-path db.db \
  --question "Top 10 products by revenue" \
  --llm-provider openai \
  --output openai_result.json

# With Groq (GPT-OSS)
python main.py \
  --db-type sqlite \
  --db-path db.db \
  --question "Top 10 products by revenue" \
  --llm-provider groq \
  --llm-model openai/gpt-oss-120b \
  --output groq_result.json

# Compare results
diff <(jq '.final_sql' openai_result.json) <(jq '.final_sql' groq_result.json)
```

## Switching Between Providers

The agent abstracts away the provider, so switching is just one argument:

```python
# Same code, different deployment
llm_provider = "groq"  # or "openai"

orchestrator = Text2SQLOrchestrator(
    connector,
    llm_provider=llm_provider,
    llm_model=model
)
```

## Troubleshooting Groq

### "Groq client not available"
```bash
pip install groq>=0.4.0
```

### "GROQ_API_KEY not set"
```bash
export GROQ_API_KEY="gsk_..."
echo $GROQ_API_KEY  # Verify it's set
```

### Slow Responses
- Groq is very fast by default
- If slow, check your API key rate limits at https://console.groq.com
- Free tier has rate limits; consider upgrading for production

### Different Results from OpenAI
- Different models produce different SQL
- Both can be valid
- If concerned, compare results file-by-file and pick the better output

## Benefits of Groq

✅ **Faster** - Perfect for real-time SQL generation  
✅ **Cheaper** - Lower cost per token  
✅ **Open** - Use open-source models (Mistral, Llama)  
✅ **Simple** - Same API, same parameter names as OpenAI  
✅ **Reliable** - Consistent, predictable performance  

## Production Recommendations

For production use of the SQL agent with Groq:

1. **Model Choice**: Use `openai/gpt-oss-120b` for best SQL generation
2. **Error Handling**: Keep retry logic (2 repair attempts) enabled
3. **Caching**: Cache schema once at startup
4. **Monitoring**: Log all failures for improvement
5. **Evaluation**: Test on your actual database before deployment

## Further Reading

- [Groq Official Docs](https://console.groq.com/docs)
- [Groq Pricing](https://console.groq.com/pricing)
- [Agent Architecture](ARCHITECTURE.md)
- [Main README](README.md)

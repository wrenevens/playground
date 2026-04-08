#!/usr/bin/env python3
"""
Quick start guide for the Text-to-SQL Agent.
Run this script to see the agent in action.
"""

import sys
import os
from pathlib import Path

# Add parent directory to path so imports work
sys.path.insert(0, str(Path(__file__).parent.parent))

from text2sql_agent.example import run_example_queries
from text2sql_agent.configs.default import DEFAULT_OPENAI_MODEL, DEFAULT_GROQ_MODEL



if __name__ == "__main__":
    print(f"""
╔════════════════════════════════════════════════════════════════════════════╗
║                    TEXT-TO-SQL AGENT - QUICK START                         ║
╚════════════════════════════════════════════════════════════════════════════╝

This script will:
1. Create a sample SQLite database with customers, orders, and products
2. Run 5 example natural language questions
3. Show the generated SQL and results

Prerequisites - Choose ONE:
  Option A: OpenAI API
    - Set OPENAI_API_KEY: export OPENAI_API_KEY="sk-..."
    - Optional model override: export OPENAI_MODEL="{DEFAULT_OPENAI_MODEL}"
  
  Option B: Groq API (RECOMMENDED - faster & cheaper)
    - Set GROQ_API_KEY: export GROQ_API_KEY="gsk_..."
    - Optional model override: export GROQ_MODEL="{DEFAULT_GROQ_MODEL}"
    - Sign up free at: https://console.groq.com

Running example with default (OpenAI):
""")
    
    # Detect which provider to use
    provider = "openai"
    model = None
    
    if os.getenv("GROQ_API_KEY"):
        provider = "groq"
        model = os.getenv("GROQ_MODEL")
        selected_model = model or DEFAULT_GROQ_MODEL
        print(f"(Detected Groq API key - using Groq model: {selected_model})\n")
    elif os.getenv("OPENAI_API_KEY"):
      selected_model = os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
      print(f"(Using OpenAI model: {selected_model})\n")
    
    run_example_queries(llm_provider=provider, llm_model=model)
    
    print("""
╔════════════════════════════════════════════════════════════════════════════╗
║                              NEXT STEPS                                    ║
╚════════════════════════════════════════════════════════════════════════════╝

1. USE WITH YOUR OWN DATABASE (OpenAI):
   python main.py \\
     --db-type sqlite \\
     --db-path ./your_database.db \\
     --question "Your question here" \\
     --llm-provider openai

2. USE WITH GROQ (faster & cheaper):
   python main.py \\
     --db-type sqlite \\
     --db-path ./your_database.db \\
     --question "Your question here" \\
     --llm-provider groq \\
     --llm-model {DEFAULT_GROQ_MODEL}

3. EVALUATE ON SPIDER2-LITE:
   python evaluation/run_spider2lite.py \\
     --spider-data /path/to/spider2lite.json \\
     --db-path /path/to/spider2lite.db

4. USE DIFFERENT GROQ MODELS:
  - gpt-oss-20b (faster)
  - {DEFAULT_GROQ_MODEL} (default)
  - or set GROQ_MODEL in your shell

5. CUSTOMIZE THE AGENT:
   - Edit prompts in agent/prompts.py
   - Adjust config in configs/default.py
   - Add new LLM providers in agent/llm_provider.py

6. READ THE DOCUMENTATION:
   - README.md - Full documentation
   - QUICKSTART.md - 5-minute guide
   - ARCHITECTURE.md - System design
   - agent/llm_provider.py - LLM providers

Happy querying! 🚀
""")

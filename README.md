# Text-to-SQL Agent

This is a lightweight, pure-Python text-to-SQL agent designed for evaluating the Spider2-lite benchmark. The codebase follows a modular structure and is minimally dependent on external libraries.

## Directory Structure

```
playground/
│
├── main.py
├── config.py
├── types.py
├── orchestrator.py
├── prompts.py
├── tools/
│   ├── schema_retriever.py
│   ├── value_retriever.py
│   ├── sql_generator.py
│   ├── sql_validator.py
│   ├── sql_executor.py
│   └── sql_repair.py
├── db/
│   ├── schema_loader.py
│   └── sqlite_executor.py
├── evaluation/
│   └── run_spider2lite.py
└── utils/
```

## How to Run

1. Ensure you have Python 3.x installed.
2. Clone the repository:
   ```
   git clone https://github.com/wrenevens/playground.git
   ```
3. Navigate to the directory:
   ```
   cd playground
   ```
4. Install the required dependencies (if any).
5. Run the main application:
   ```
   python main.py
   ```

## Folder Descriptions

- **main.py**: Entry point of the application.
- **config.py**: Configuration settings for the agent.
- **types.py**: Definition of various types used in the application.
- **orchestrator.py**: Contains the main orchestrator workflow for the agent.
- **prompts.py**: Placeholder for text generation prompts.
- **tools/**: Contains utility modules for schema retrieval, value retrieval, SQL generation, validation, repair, and execution.
- **db/**: Functions related to database schema loading and SQLite execution.
- **evaluation/**: Contains the evaluation runner for Spider2-lite.
- **utils/**: Helper functions used throughout the codebase.

### Placeholder for LLM Integration

The structure is designed to allow for easy integration of LLMs in the future. Relevant placeholders can be found in `prompts.py` and inside appropriate tools where LLM functionality may be needed.

GrastSql reference:
@article{hoang2025scaling,
  title={Scaling Text2SQL via LLM-efficient Schema Filtering with Functional Dependency Graph Rerankers},
  author={Hoang, Thanh Dat and Nguyen, Thanh Tam and Huynh, Thanh Trung and Yin, Hongzhi and Nguyen, Quoc Viet Hung},
  journal={arXiv preprint arXiv:2512.16083},
  year={2025}
}
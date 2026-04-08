"""
Main entry point for the Text-to-SQL agent.
Simple CLI interface for running queries on custom databases.
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# Add parent directory to path to properly resolve package imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from text2sql_agent.agent.orchestrator import Text2SQLOrchestrator
from text2sql_agent.db.connector import get_connector


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


def main():
    """Main CLI interface."""
    parser = argparse.ArgumentParser(description="Text-to-SQL Agent")
    
    # Database config
    parser.add_argument("--db-type", required=True, help="Database type (sqlite, postgresql)")
    parser.add_argument("--db-path", help="Path to SQLite database file")
    parser.add_argument("--db-host", default="localhost", help="Database host")
    parser.add_argument("--db-port", type=int, default=5432, help="Database port")
    parser.add_argument("--db-name", help="Database name")
    parser.add_argument("--db-user", help="Database user")
    parser.add_argument("--db-password", help="Database password")
    
    # Query config
    parser.add_argument("--question", required=True, help="Natural language question")
    parser.add_argument("--db-id", default="custom_db", help="Database identifier")
    parser.add_argument("--evidence", default=None, help="Optional evidence/context")
    
    # LLM config
    parser.add_argument("--llm-provider", default="openai", choices=["openai", "groq"], help="LLM provider (openai, groq)")
    parser.add_argument("--llm-model", default=None, help="Specific model name (uses provider default if not specified)")
    
    # Output config
    parser.add_argument("--output", help="Path to save JSON results")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    # Setup logging
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    logger.info("Text-to-SQL Agent starting")
    
    try:
        # Connect to database
        db_config = {
            "db_type": args.db_type,
        }
        
        if args.db_type.lower() == "sqlite":
            db_config["db_path"] = args.db_path or "database.db"
        else:  # postgresql
            db_config.update({
                "host": args.db_host,
                "port": args.db_port,
                "database": args.db_name,
                "user": args.db_user,
                "password": args.db_password
            })
        
        connector = get_connector(**db_config)
        connector.connect()
        
        # Create orchestrator with specified LLM provider
        orchestrator = Text2SQLOrchestrator(
            connector,
            llm_provider=args.llm_provider,
            llm_model=args.llm_model
        )
        
        # Run workflow
        logger.info(f"Processing question: {args.question}")
        result = orchestrator.run(
            question=args.question,
            db_id=args.db_id,
            evidence=args.evidence
        )
        execution_result = result.get("execution_result") or {}
        
        # Display results
        print("\n" + "="*60)
        print(orchestrator.get_summary(result))
        print("="*60)
        
        if result.get("final_sql"):
            print(f"\nFinal SQL:\n{result['final_sql']}\n")
        
        if execution_result.get("ok"):
            rows = execution_result.get("rows", [])
            print(f"Results ({len(rows)} rows):")
            for row in rows[:5]:
                print(f"  {row}")
            if len(rows) > 5:
                print(f"  ... and {len(rows) - 5} more rows")
        
        # Save results if requested
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w") as f:
                json.dump(result, f, indent=2, default=str)
            logger.info(f"Results saved to {args.output}")
        
        connector.disconnect()
        logger.info("Workflow completed")
        
        return 0 if execution_result.get("ok") else 1
    
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        print(f"\nError: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

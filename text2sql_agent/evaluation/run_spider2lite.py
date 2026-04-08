"""Spider2-lite evaluation runner."""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any
import argparse
from datetime import datetime

import sys

# Add parent directory to path to properly resolve package imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from text2sql_agent.agent.orchestrator import Text2SQLOrchestrator
from text2sql_agent.db.connector import get_connector


logger = logging.getLogger(__name__)


class Spider2LiteEvaluator:
    """Evaluate the agent on Spider2-lite dataset."""
    
    def __init__(self, db_config: Dict[str, Any], llm_provider: str = "openai", llm_model: str = None):
        self.db_config = db_config
        self.llm_provider = llm_provider
        self.llm_model = llm_model
        self.results = []
        self.metrics = {}
    
    def load_spider2_data(self, json_path: str) -> List[Dict]:
        """Load Spider2-lite JSON file."""
        with open(json_path, "r") as f:
            return json.load(f)
    
    def run_on_dataset(self, data: List[Dict], limit: int = None, db_type: str = "sqlite") -> Dict:
        """
        Run agent on all items in Spider2-lite dataset.
        
        Args:
            data: List of Spider2-lite records
            limit: Maximum number of records to process
            db_type: Type of database
        
        Returns:
            Evaluation metrics and results
        """
        processed = 0
        succeeded = 0
        failed = 0
        
        for idx, record in enumerate(data):
            if limit and idx >= limit:
                break
            
            logger.info(f"Processing {idx + 1}/{min(len(data), limit or len(data))}")
            
            try:
                result = self.process_one(record, db_type)
                self.results.append(result)
                
                if result.get("execution_success"):
                    succeeded += 1
                else:
                    failed += 1
                
                processed += 1
            
            except Exception as e:
                logger.error(f"Error processing record {idx}: {e}")
                failed += 1
                processed += 1
        
        # Calculate metrics
        self.metrics = {
            "total_processed": processed,
            "succeeded": succeeded,
            "failed": failed,
            "success_rate": succeeded / processed if processed > 0 else 0,
            "timestamp": datetime.now().isoformat()
        }
        
        return self.metrics
    
    def process_one(self, record: Dict, db_type: str = "sqlite") -> Dict:
        """
        Process a single Spider2-lite record.
        
        Returns:
            Result dict with success status and details
        """
        question = record.get("question", "")
        db_id = record.get("db_id", "unknown")
        gold_sql = record.get("sql", "")
        
        logger.info(f"Q: {question[:60]}... DB: {db_id}")
        
        try:
            # Connect to database
            connector = get_connector(db_type=db_type, **self.db_config)
            connector.connect()
            
            # Run orchestrator with specified LLM provider
            orchestrator = Text2SQLOrchestrator(
                connector,
                llm_provider=self.llm_provider,
                llm_model=self.llm_model
            )
            state_result = orchestrator.run(question, db_id)
            execution_result = state_result.get("execution_result") or {}
            
            connector.disconnect()
            
            # Evaluate
            execution_success = execution_result.get("ok", False)
            final_sql = state_result.get("final_sql")
            
            return {
                "question": question,
                "db_id": db_id,
                "gold_sql": gold_sql,
                "generated_sql": final_sql,
                "execution_success": execution_success,
                "num_rows": execution_result.get("row_count", 0),
                "num_errors": len(state_result.get("errors", [])),
                "full_trace": state_result
            }
        
        except Exception as e:
            logger.error(f"Failed to process: {e}")
            return {
                "question": question,
                "db_id": db_id,
                "gold_sql": gold_sql,
                "generated_sql": None,
                "execution_success": False,
                "error": str(e),
                "num_rows": 0,
                "num_errors": 1
            }
    
    def save_results(self, output_dir: str):
        """Save results to JSON files."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Save results
        results_file = output_path / "results.json"
        with open(results_file, "w") as f:
            json.dump(self.results, f, indent=2, default=str)
        
        # Save metrics
        metrics_file = output_path / "metrics.json"
        with open(metrics_file, "w") as f:
            json.dump(self.metrics, f, indent=2)
        
        logger.info(f"Results saved to {output_path}")
    
    def print_summary(self):
        """Print evaluation summary."""
        print("\n" + "="*60)
        print("SPIDER2-LITE EVALUATION SUMMARY")
        print("="*60)
        print(f"Total Processed: {self.metrics['total_processed']}")
        print(f"Succeeded: {self.metrics['succeeded']}")
        print(f"Failed: {self.metrics['failed']}")
        print(f"Success Rate: {self.metrics['success_rate']:.1%}")
        print("="*60 + "\n")


def main():
    """CLI for Spider2-lite evaluation."""
    parser = argparse.ArgumentParser(description="Spider2-lite Evaluation")
    
    # Dataset
    parser.add_argument("--spider-data", required=True, help="Path to Spider2-lite JSON")
    
    # Database
    parser.add_argument("--db-type", default="sqlite", help="Database type")
    parser.add_argument("--db-path", default="spider2lite.db", help="SQLite path")
    parser.add_argument("--db-host", default="localhost")
    parser.add_argument("--db-port", type=int, default=5432)
    parser.add_argument("--db-name", default="spider2lite")
    parser.add_argument("--db-user", default="postgres")
    parser.add_argument("--db-password", default="")
    
    # Evaluation
    parser.add_argument("--limit", type=int, help="Limit number of records to process")
    parser.add_argument("--output", default="./evaluation_results", help="Output directory")
    parser.add_argument("--verbose", action="store_true")
    
    # LLM config
    parser.add_argument("--llm-provider", default="openai", choices=["openai", "groq"], help="LLM provider (openai, groq)")
    parser.add_argument("--llm-model", default=None, help="Specific model name (uses provider default if not specified)")
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Load dataset
    logger.info(f"Loading Spider2-lite data from {args.spider_data}")
    data = json.load(open(args.spider_data))
    
    # Create evaluator
    db_config = {"db_path": args.db_path} if args.db_type == "sqlite" else {
        "host": args.db_host,
        "port": args.db_port,
        "database": args.db_name,
        "user": args.db_user,
        "password": args.db_password
    }
    
    evaluator = Spider2LiteEvaluator(
        db_config,
        llm_provider=args.llm_provider,
        llm_model=args.llm_model
    )
    
    # Run evaluation
    metrics = evaluator.run_on_dataset(data, limit=args.limit, db_type=args.db_type)
    
    # Save and print results
    evaluator.save_results(args.output)
    evaluator.print_summary()


if __name__ == "__main__":
    main()

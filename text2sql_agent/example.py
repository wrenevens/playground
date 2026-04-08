"""
Example script showing how to use the text-to-SQL agent.
Creates a sample SQLite database and runs queries.
"""

import sys
import sqlite3
from pathlib import Path

# Add parent directory to path to properly resolve package imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from text2sql_agent.agent.orchestrator import Text2SQLOrchestrator
from text2sql_agent.db.connector import get_connector


def create_sample_database(db_path: str = "sample.db"):
    """Create a sample database with some tables."""
    # Remove existing database
    Path(db_path).unlink(missing_ok=True)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create tables
    cursor.execute("""
        CREATE TABLE customers (
            customer_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT,
            city TEXT,
            country TEXT,
            signup_date DATE
        )
    """)
    
    cursor.execute("""
        CREATE TABLE orders (
            order_id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            order_date DATE,
            total_amount DECIMAL(10, 2),
            status TEXT,
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE products (
            product_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT,
            price DECIMAL(10, 2),
            stock INTEGER
        )
    """)
    
    cursor.execute("""
        CREATE TABLE order_items (
            order_item_id INTEGER PRIMARY KEY,
            order_id INTEGER,
            product_id INTEGER,
            quantity INTEGER,
            unit_price DECIMAL(10, 2),
            FOREIGN KEY (order_id) REFERENCES orders(order_id),
            FOREIGN KEY (product_id) REFERENCES products(product_id)
        )
    """)
    
    # Insert sample data
    customers = [
        (1, "Alice Smith", "alice@example.com", "New York", "USA", "2023-01-15"),
        (2, "Bob Johnson", "bob@example.com", "Los Angeles", "USA", "2023-02-20"),
        (3, "Carol White", "carol@example.com", "London", "UK", "2023-03-10"),
        (4, "David Brown", "david@example.com", "Paris", "France", "2023-04-05"),
        (5, "Eve Wilson", "eve@example.com", "Tokyo", "Japan", "2023-05-12"),
    ]
    cursor.executemany("INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?)", customers)
    
    products = [
        (1, "Laptop", "Electronics", 999.99, 15),
        (2, "Mouse", "Electronics", 29.99, 100),
        (3, "Keyboard", "Electronics", 79.99, 50),
        (4, "Monitor", "Electronics", 299.99, 25),
        (5, "USB Cable", "Accessories", 9.99, 200),
    ]
    cursor.executemany("INSERT INTO products VALUES (?, ?, ?, ?, ?)", products)
    
    orders = [
        (1, 1, "2023-06-01", 1269.97, "completed"),
        (2, 2, "2023-06-05", 999.99, "completed"),
        (3, 1, "2023-06-10", 109.98, "completed"),
        (4, 3, "2023-06-15", 1329.96, "completed"),
        (5, 4, "2023-06-20", 59.99, "pending"),
    ]
    cursor.executemany("INSERT INTO orders VALUES (?, ?, ?, ?, ?)", orders)
    
    order_items = [
        (1, 1, 1, 1, 999.99),
        (2, 1, 2, 1, 29.99),
        (3, 1, 5, 2, 4.99),
        (4, 2, 1, 1, 999.99),
        (5, 3, 2, 2, 29.99),
        (6, 4, 1, 1, 999.99),
        (7, 4, 3, 1, 79.99),
        (8, 4, 4, 1, 249.98),
        (9, 5, 3, 1, 79.99),
    ]
    cursor.executemany("INSERT INTO order_items VALUES (?, ?, ?, ?, ?)", order_items)
    
    conn.commit()
    conn.close()
    
    print(f"✓ Sample database created: {db_path}")


def run_example_queries(llm_provider: str = "openai", llm_model: str = None):
    """
    Run example queries on the sample database.
    
    Args:
        llm_provider: "openai" or "groq"
        llm_model: Specific model name (uses provider default if None)
    """
    # Create database
    db_path = "sample.db"
    create_sample_database(db_path)
    
    # Connect
    connector = get_connector(db_type="sqlite", db_path=db_path)
    connector.connect()
    
    # Create orchestrator with specified LLM provider
    orchestrator = Text2SQLOrchestrator(
        connector,
        llm_provider=llm_provider,
        llm_model=llm_model
    )
    
    # Example queries
    questions = [
        "How many customers are from the USA?",
        "Show me the top 3 most expensive products",
        "List all orders with their customer names",
        "How much did Alice Smith spend in total?",
        "Which product has the most stock available?",
    ]
    
    print("\n" + "="*70)
    print("TEXT-TO-SQL AGENT DEMONSTRATION")
    print("="*70)
    
    for i, question in enumerate(questions, 1):
        print(f"\n[Query {i}/{len(questions)}] {question}")
        print("-" * 70)
        
        try:
            result = orchestrator.run(question=question, db_id="sample_db")
            execution_result = result.get("execution_result") or {}
            
            if result.get("final_sql"):
                print(f"Generated SQL:\n  {result['final_sql']}\n")
            
            if execution_result.get("ok"):
                rows = execution_result.get("rows", [])
                print(f"Results ({len(rows)} rows):")
                for row in rows[:3]:
                    print(f"  {row}")
                if len(rows) > 3:
                    print(f"  ... and {len(rows) - 3} more rows")
            else:
                error = execution_result.get("error") or " | ".join(result.get("errors", [])) or "Unknown error"
                print(f"❌ Execution failed: {error}")
                if "api key" in error.lower() or "invalid_api_key" in error.lower() or "401" in error:
                    if llm_provider == "openai":
                        print("   Hint: set a valid OPENAI_API_KEY or switch to Groq with GROQ_API_KEY.")
                    elif llm_provider == "groq":
                        print("   Hint: set a valid GROQ_API_KEY.")
            
            print(f"Steps: {len(result.get('logs', []))}, Errors: {len(result.get('errors', []))}")
        
        except Exception as e:
            print(f"❌ Error: {e}")
    
    connector.disconnect()
    print("\n" + "="*70)
    print("Demonstration complete!")
    print("="*70 + "\n")


if __name__ == "__main__":
    run_example_queries()

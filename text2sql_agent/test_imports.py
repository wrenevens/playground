#!/usr/bin/env python3
"""Test script to verify imports work correctly."""

import sys
from pathlib import Path

print("Testing package imports...")
print(f"Current file: {__file__}")
print(f"Parent directory: {Path(__file__).parent.parent}")

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    print("\n1. Importing text2sql_agent...")
    import text2sql_agent
    print("   ✓ text2sql_agent imported")
    
    print("\n2. Importing orchestrator...")
    from text2sql_agent.agent.orchestrator import Text2SQLOrchestrator
    print("   ✓ Text2SQLOrchestrator imported")
    
    print("\n3. Importing database connector...")
    from text2sql_agent.db.connector import get_connector
    print("   ✓ get_connector imported")
    
    print("\n4. Importing tools...")
    from text2sql_agent.agent.tools import ToolSet
    print("   ✓ ToolSet imported")
    
    print("\n5. Testing database connection (SQLite)...")
    connector = get_connector(db_type="sqlite", db_path=":memory:")
    connector.connect()
    print("   ✓ SQLite connection works")
    tables = connector.get_table_names()
    print(f"   Tables in memory DB: {tables}")
    connector.disconnect()
    
    print("\n✓ All imports working correctly!")
    sys.exit(0)
    
except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

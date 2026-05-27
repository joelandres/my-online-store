# store_mcp.py
import sqlite3
from typing import Literal
from fastmcp import FastMCP

# Initialize FastMCP server instance
mcp = FastMCP("Internal Online Store Database Gateway")

# ---------------------------------------------------------------------
# Database Mock Lab Setup (Using local SQLite for sandbox testing)
# ---------------------------------------------------------------------
def init_db():
    conn = sqlite3.connect("store_internal.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS store_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sku TEXT UNIQUE NOT NULL,
            item_name TEXT NOT NULL,
            stock_count INTEGER NOT NULL,
            price REAL NOT NULL
        )
    """)
    # Seed sample records if empty
    cursor.execute("SELECT COUNT(*) FROM store_inventory")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("""
            INSERT INTO store_inventory (sku, item_name, stock_count, price) VALUES (?, ?, ?, ?)
        """, [
            ("SKU-MUG-01", "coffee mug", 42, 15.00),
            ("SKU-STND-02", "laptop stand", 5, 45.00),
            ("SKU-CBL-03", "usb-c cable", 0, 12.50)
        ])
    conn.commit()
    conn.close()

init_db()


# ---------------------------------------------------------------------
# 2. Expose Deterministic Capabilities (Tools)
# ---------------------------------------------------------------------
@mcp.tool()
def query_product_pricing(product_name: str) -> str:
    """Retrieves the price and exact warehouse SKU code for a product by name."""
    conn = sqlite3.connect("store_internal.db")
    cursor = conn.cursor()
    
    # Query with strict parameters to entirely block SQL-injection vectors
    cursor.execute(
        "SELECT sku, price FROM store_inventory WHERE item_name = ?", 
        (product_name.lower().strip(),)
    )
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return f"Product: '{product_name}' | SKU: {row[0]} | Base Price: ${row[1]:.2f}"
    return f"Product variant '{product_name}' does not match catalog listings."


@mcp.tool()
def execute_safe_stock_mutation(sku: str, allocation_adjustment: int) -> str:
    """Adjusts warehouse stock levels. Use positive ints for additions, negative for sales orders."""
    conn = sqlite3.connect("store_internal.db")
    cursor = conn.cursor()
    
    cursor.execute("SELECT item_name, stock_count FROM store_inventory WHERE sku = ?", (sku.upper().strip(),))
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        return f"Transaction Aborted: Target identifier '{sku}' is invalid."
        
    item_name, current_stock = row
    calculated_new_total = current_stock + allocation_adjustment
    
    # Strict inventory boundary guardrail rule
    if calculated_new_total < 0:
        conn.close()
        return f"Rejected: Operation fails inventory floor constraint. Available: {current_stock} units."
        
    cursor.execute(
        "UPDATE store_inventory SET stock_count = ? WHERE sku = ?", 
        (calculated_new_total, sku.upper().strip())
    )
    conn.commit()
    conn.close()
    
    return f"Success: {item_name} ({sku}) updated from {current_stock} to {calculated_new_total} units."


# ---------------------------------------------------------------------
# 3. Expose Static/Dynamic System Read States (Resources)
# ---------------------------------------------------------------------
@mcp.resource("store://catalog/all_products")
def list_complete_catalog() -> list[dict]:
    """Provides a read-only list of the entire database catalog."""
    conn = sqlite3.connect("store_internal.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT sku, item_name, price FROM store_inventory")
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


if __name__ == "__main__":
    # Spins up standard input/output transport communication stream listener
    mcp.run()
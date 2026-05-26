from langchain_core.tools import tool

@tool("check_order_status")
def check_order_status(order_id: str) -> str:
    """Queries the database to check shipping status for a specific order ID."""
    mock_orders = {"#1001": "Shipped - In Transit", "#1002": "Processing"}
    return mock_orders.get(order_id, f"Order {order_id} not found in the transaction log.")
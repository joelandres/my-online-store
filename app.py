import os
from typing import Literal
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command

# 1. Shared State Schema
class StoreState(TypedDict):
    customer_query: str
    selected_agent: Literal["support", "inventory", "end"]
    agent_logs: list[str]
    output_response: str

# Mock Database Store
MOCK_ORDERS = {"#1001": "Shipped - In Transit", "#1002": "Processing"}
MOCK_INVENTORY = {"widget_a": 42, "widget_b": 0}

# 2. Agent Node Definitions
def router_node(state: StoreState):
    """Analyzes incoming intent and forwards it to the specialized skill agent."""
    query = state["customer_query"].lower()
    logs = state.get("agent_logs", [])
    logs.append("Router evaluated user request.")
    
    if "order" in query or "status" in query or "track" in query:
        next_agent = "support"
    elif "stock" in query or "inventory" in query or "count" in query:
        next_agent = "inventory"
    else:
        next_agent = "end"
        
    return Command(
        goto=next_agent if next_agent != "end" else END,
        update={
            "selected_agent": next_agent, 
            "agent_logs": logs,
            "output_response": "Request out of scope for store workflows." if next_agent == "end" else ""
        }
    )

def support_agent_skill(state: StoreState):
    """Handles order processing and tracking details."""
    logs = state["agent_logs"]
    logs.append("Support Agent Skill activated.")
    query = state["customer_query"]
    
    # Simple semantic extraction simulation
    order_id = "#1001" if "1001" in query else "#1002" if "1002" in query else None
    
    if order_id and order_id in MOCK_ORDERS:
        res = f"Support Agent: Order {order_id} status is currently: {MOCK_ORDERS[order_id]}."
    else:
        res = "Support Agent: I could not locate that order ID. Esculating your ticket to a human manager."
        
    return {"output_response": res, "agent_logs": logs}

def inventory_agent_skill(state: StoreState):
    """Handles stock counts and product availability lookups."""
    logs = state["agent_logs"]
    logs.append("Inventory Agent Skill activated.")
    query = state["customer_query"].lower()
    
    item = "widget_a" if "widget a" in query else "widget_b" if "widget b" in query else None
    
    if item and item in MOCK_INVENTORY:
        qty = MOCK_INVENTORY[item]
        status = "In Stock" if qty > 0 else "Out of Stock"
        res = f"Inventory Agent: '{item}' is {status}. Current warehouse quantity: {qty} units."
    else:
        res = "Inventory Agent: Product SKU not recognized in active catalog."
        
    return {"output_response": res, "agent_logs": logs}

# 3. Assemble the Graph Workflow
builder = StateGraph(StoreState)

# Register the architectural components
builder.add_node("router", router_node)
builder.add_node("support", support_agent_skill)
builder.add_node("inventory", inventory_agent_skill)

# Construct routing boundaries
builder.add_edge(START, "router")
builder.add_edge("support", END)
builder.add_edge("inventory", END)

store_app = builder.compile()

# 4. Local Execution Test
if __name__ == "__main__":
    print("--- Executing Support Tracking Query ---")
    support_run = store_app.invoke({"customer_query": "Where is my order #1001?"})
    print(f"Logs:   {support_run['agent_logs']}")
    print(f"Result: {support_run['output_response']}\n")
    
    print("--- Executing Stock Check Query ---")
    inventory_run = store_app.invoke({"customer_query": "Is widget b available to buy?"})
    print(f"Logs:   {inventory_run['agent_logs']}")
    print(f"Result: {inventory_run['output_response']}")
import os
from typing import Literal
from pydantic import BaseModel, Field
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command

# 1. State and Enterprise Schema Structure
class StoreState(TypedDict):
    customer_query: str
    selected_agent: str
    agent_logs: list[str]
    output_response: str

# Pydantic schema enforcing structured routing decisions
class RouterDecision(BaseModel):
    next_step: Literal["support", "inventory", "pricing", "end"] = Field(
        description="Select the most appropriate specialist agent or 'end' if unresolvable."
    )

# Active Store Databases
MOCK_ORDERS = {"#1001": "Shipped - In Transit"}
MOCK_INVENTORY = {"coffee mug": 42, "laptop stand": 5}
MOCK_PRICES = {"coffee mug": 15.00, "laptop stand": 45.00}

# 2. Agent Skill Nodes
def structured_router(state: StoreState):
    """Parses text requests and securely guides execution to the next branch."""
    query = state["customer_query"].lower()
    logs = state.get("agent_logs", [])
    logs.append("Enterprise Router evaluated structural context.")
    
    # Simulating LLM Structured Output parsing
    if any(k in query for k in ["order", "track", "status", "1001"]):
        destination = "support"
    elif any(k in query for k in ["stock", "inventory", "warehouse", "available"]):
        destination = "inventory"
    elif any(k in query for k in ["price", "cost", "quote", "how much"]):
        destination = "pricing"
    else:
        destination = "end"
        
    decision = RouterDecision(next_step=destination)
    selected_step = decision.next_step

    return Command(
        goto=selected_step if selected_step != "end" else END,
        update={
            "selected_agent": selected_step,
            "agent_logs": logs,
            "output_response": "Request fallback: Out of operational bounds." if selected_step == "end" else ""
        }
    )

def support_agent_skill(state: StoreState):
    """Validates order IDs and fetches live delivery status records."""
    logs = state["agent_logs"]
    logs.append("Support Agent running tracking check.")
    query = state["customer_query"]
    
    order_id = "#1001" if "1001" in query else None
    if order_id in MOCK_ORDERS:
        res = f"Support: Order {order_id} is verified as '{MOCK_ORDERS[order_id]}'."
    else:
        res = "Support: Order reference ID not found in transaction ledger."
        
    return {"output_response": res, "agent_logs": logs}

def inventory_agent_skill(state: StoreState):
    """Interrogates warehouse data arrays to verify SKU availability."""
    logs = state["agent_logs"]
    logs.append("Inventory Agent scanning warehouse registers.")
    query = state["customer_query"].lower()
    
    item = "coffee mug" if "mug" in query else "laptop stand" if "stand" in query else None
    if item in MOCK_INVENTORY:
        res = f"Inventory: '{item}' inventory verified. Count: {MOCK_INVENTORY[item]} units."
    else:
        res = "Inventory: Targeted item does not match active product catalogs."
        
    return {"output_response": res, "agent_logs": logs}

def pricing_agent_skill(state: StoreState):
    """Calculates financial calculations including sales tax adjustments."""
    logs = state["agent_logs"]
    logs.append("Pricing Agent processing quote computation.")
    query = state["customer_query"].lower()
    
    item = "coffee mug" if "mug" in query else "laptop stand" if "stand" in query else None
    if item in MOCK_PRICES:
        base_price = MOCK_PRICES[item]
        tax_rate = 0.07  # 7% standard sales tax
        final_total = base_price * (1 + tax_rate)
        res = f"Pricing: '{item}' costs ${base_price:.2f}. Total with sales tax is ${final_total:.2f}."
    else:
        res = "Pricing: Quote aborted. SKU pricing matrix unavailable."
        
    return {"output_response": res, "agent_logs": logs}


# 3. Assemble the Graph Matrix
builder = StateGraph(StoreState)

builder.add_node("router", structured_router)
builder.add_node("support", support_agent_skill)
builder.add_node("inventory", inventory_agent_skill)
builder.add_node("pricing", pricing_agent_skill)

builder.add_edge(START, "router")
builder.add_edge("support", END)
builder.add_edge("inventory", END)
builder.add_edge("pricing", END)

store_system = builder.compile()


# 4. Runtime Validation Experiments
if __name__ == "__main__":
    print("--- 1. Testing Order Check ---")
    out1 = store_system.invoke({"customer_query": "Track my order 1001"})
    print(f"Agent Chain: {out1['agent_logs']}")
    print(f"Result:      {out1['output_response']}\n")

    print("--- 2. Testing Price Inquiry ---")
    out2 = store_system.invoke({"customer_query": "How much does the coffee mug cost?"})
    print(f"Agent Chain: {out2['agent_logs']}")
    print(f"Result:      {out2['output_response']}\n")
    
    print("--- 3. Testing Inventory Audit ---")
    out3 = store_system.invoke({"customer_query": "Do we have any laptop stands available in stock?"})
    print(f"Agent Chain: {out3['agent_logs']}")
    print(f"Result:      {out3['output_response']}")
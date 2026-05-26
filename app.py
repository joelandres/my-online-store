import os
from typing import Literal
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import ToolNode, tools_condition

# =====================================================================
# 1. Mock Local Imports (Simulating your standardized Skill modules)
# =====================================================================
from langchain_core.tools import tool


def load_dotenv(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as env_file:
        for line in env_file:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


load_dotenv()

@tool("calculate_product_price")
def calculate_product_price(item_name: str, apply_discount: bool = False) -> str:
    """Calculates the total cost of a product including a 7% sales tax and optional 10% discount."""
    prices = {"coffee mug": 15.00, "laptop stand": 45.00}
    item_lower = item_name.lower()
    if item_lower not in prices:
        return f"Could not generate a quote. '{item_name}' pricing data is missing."
    price = prices[item_lower]
    if apply_discount:
        price *= 0.90
    return f"The final price for '{item_name}' (with tax) is ${price * 1.07:.2f}."

@tool("check_order_status")
def check_order_status(order_id: str) -> str:
    """Queries the database to check shipping status for a specific order ID (e.g., #1001)."""
    mock_orders = {"#1001": "Shipped - In Transit", "#1002": "Processing"}
    return mock_orders.get(order_id, f"Order {order_id} not found in the transaction log.")


# Initialize the shared underlying model core
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    raise RuntimeError("OPENAI_API_KEY must be set in .env or the environment.")

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, openai_api_key=openai_api_key)

# =====================================================================
# 2. Define the Supervisor Node (Intent Router)
# =====================================================================
class RouteSelection(BaseModel):
    next_department: Literal["pricing_agent", "support_agent", "end_conversation"] = Field(
        description="Pick pricing_agent for cost/quotes, support_agent for order updates, or end if handled."
    )

def supervisor_router(state: MessagesState):
    """Parses incoming human user text and hands control to the target specialist department node."""
    structured_llm = llm.with_structured_output(RouteSelection)
    
    system_prompt = (
        "You are the central directory router for an online storefront application.\n"
        "Evaluate the history and assign the context to the correct operational department:\n"
        "- 'pricing_agent': Product costs, checking store sales tax, quotes, or discounts.\n"
        "- 'support_agent': Order tracking updates, shipping states, or delivery lookups.\n"
        "- 'end_conversation': If the problem is resolved or the client is saying goodbye."
    )
    
    messages = [{"role": "system", "content": system_prompt}] + state["messages"]
    decision = structured_llm.invoke(messages)
    
    # We pass the instruction payload through by appending an intermediate log message
    return {"messages": [AIMessage(content=f"Routing payload context to: {decision.next_department}")]}


# =====================================================================
# 3. Define the Specialist Agent Nodes (Bound to explicit Skills)
# =====================================================================
def pricing_agent(state: MessagesState):
    """Specialist agent reading instructions from store-pricing/SKILL.md"""
    agent_llm = llm.bind_tools([calculate_product_price])
    system_prompt = "You are a retail pricing specialist. Calculate quotes using your tools if needed."
    return {"messages": [agent_llm.invoke([{"role": "system", "content": system_prompt}] + state["messages"])]}

def support_agent(state: MessagesState):
    """Customer rep agent reading instructions from order-support/SKILL.md"""
    agent_llm = llm.bind_tools([check_order_status])
    system_prompt = "You are a support agent. Check order updates using your tools if needed."
    return {"messages": [agent_llm.invoke([{"role": "system", "content": system_prompt}] + state["messages"])]}


# =====================================================================
# 4. Construct and Compile the Multi-Agent StateGraph Architecture
# =====================================================================
builder = StateGraph(MessagesState)

# Register the structural department brains
builder.add_node("supervisor", supervisor_router)
builder.add_node("pricing_agent", pricing_agent)
builder.add_node("support_agent", support_agent)

# Register the centralized Skill Executor tool node
store_skills_executor = ToolNode([calculate_product_price, check_order_status])
builder.add_node("execute_skills", store_skills_executor)

# --- Define Edge Pathways ---
builder.add_edge(START, "supervisor")

# Edge 1: Supervisor out to specialized department
def route_supervisor_decision(state: MessagesState):
    last_log = state["messages"][-1].content
    if "pricing_agent" in last_log: return "pricing_agent"
    if "support_agent" in last_log: return "support_agent"
    return END

builder.add_conditional_edges("supervisor", route_supervisor_decision)

# Edge 2: Specialist Agents out to either execute a Skill tool or wrap up and END
def determine_tool_loop(state: MessagesState):
    if state["messages"][-1].tool_calls:
        return "execute_skills"
    return END

builder.add_conditional_edges("pricing_agent", determine_tool_loop, ["execute_skills", END])
builder.add_conditional_edges("support_agent", determine_tool_loop, ["execute_skills", END])

# Edge 3: Dynamic return path tracking where to hand tool data back to
def return_tool_data_to_origin(state: MessagesState):
    for msg in reversed(state["messages"]):
        if "Routing payload context to:" in msg.content:
            if "pricing_agent" in msg.content: return "pricing_agent"
            if "support_agent" in msg.content: return "support_agent"
    return "supervisor"

builder.add_conditional_edges("execute_skills", return_tool_data_to_origin)

# Freeze structure definition into executable runnable
store_app = builder.compile()


# =====================================================================
# 5. Local Sandbox Execution Triggers
# =====================================================================
if __name__ == "__main__":
    # Test Experiment 1: Pricing Request Execution Stream
    print("--- Running Test Case: Pricing Inquiry ---")
    query_1 = "Hi, how much does a coffee mug cost here? Can you apply any discounts?"
    output_1 = store_app.invoke({"messages": [HumanMessage(content=query_1)]})
    
    for message in output_1["messages"]:
        if isinstance(message, AIMessage) and not message.tool_calls and "Routing" not in message.content:
            print(f"Store Team Output: {message.content}\n")

    # Test Experiment 2: Support Request Execution Stream
    print("--- Running Test Case: Support Tracking Inquiry ---")
    query_2 = "Can you check on my package delivery status for order #1001?"
    output_2 = store_app.invoke({"messages": [HumanMessage(content=query_2)]})
    
    for message in output_2["messages"]:
        if isinstance(message, AIMessage) and not message.tool_calls and "Routing" not in message.content:
            print(f"Store Team Output: {message.content}\n")
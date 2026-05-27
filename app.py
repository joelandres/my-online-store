import os
import asyncio
from typing import Literal
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import ToolNode
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_mcp_adapters.tools import load_mcp_tools


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

openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    raise RuntimeError("OPENAI_API_KEY must be set in .env or the environment.")

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, openai_api_key=openai_api_key)


# =====================================================================
# 1. Supervisor Node (Intent Router)
# =====================================================================
class RouteSelection(BaseModel):
    next_department: Literal["pricing_agent", "inventory_agent", "end_conversation"] = Field(
        description="Pick pricing_agent for cost/quotes, inventory_agent for stock updates, or end if handled."
    )

def supervisor_router(state: MessagesState):
    """Routes incoming requests to the correct specialist department."""
    structured_llm = llm.with_structured_output(RouteSelection)

    system_prompt = (
        "You are the central directory router for an online storefront application.\n"
        "Evaluate the history and assign the context to the correct operational department:\n"
        "- 'pricing_agent': Product costs, checking store sales tax, quotes, or discounts.\n"
        "- 'inventory_agent': Stock updates, warehouse mutations, or inventory adjustments.\n"
        "- 'end_conversation': If the problem is resolved or the client is saying goodbye."
    )

    messages = [{"role": "system", "content": system_prompt}] + state["messages"]
    decision = structured_llm.invoke(messages)
    return {"messages": [AIMessage(content=f"Routing payload context to: {decision.next_department}")]}


# =====================================================================
# 2. Build Graph (receives live MCP tools)
# =====================================================================
def build_graph(pricing_tool, inventory_tool):
    def pricing_agent(state: MessagesState):
        agent_llm = llm.bind_tools([pricing_tool])
        system_prompt = "You are a retail pricing specialist. Use your tools to look up product pricing."
        return {"messages": [agent_llm.invoke([{"role": "system", "content": system_prompt}] + state["messages"])]}

    def inventory_agent(state: MessagesState):
        agent_llm = llm.bind_tools([inventory_tool])
        system_prompt = "You are an inventory manager. Use your tools to adjust warehouse stock levels."
        return {"messages": [agent_llm.invoke([{"role": "system", "content": system_prompt}] + state["messages"])]}

    builder = StateGraph(MessagesState)
    builder.add_node("supervisor", supervisor_router)
    builder.add_node("pricing_agent", pricing_agent)
    builder.add_node("inventory_agent", inventory_agent)
    builder.add_node("execute_skills", ToolNode([pricing_tool, inventory_tool]))

    builder.add_edge(START, "supervisor")

    def route_supervisor_decision(state: MessagesState):
        last_log = state["messages"][-1].content
        if "pricing_agent" in last_log: return "pricing_agent"
        if "inventory_agent" in last_log: return "inventory_agent"
        return END

    builder.add_conditional_edges("supervisor", route_supervisor_decision)

    def determine_tool_loop(state: MessagesState):
        return "execute_skills" if state["messages"][-1].tool_calls else END

    builder.add_conditional_edges("pricing_agent", determine_tool_loop, ["execute_skills", END])
    builder.add_conditional_edges("inventory_agent", determine_tool_loop, ["execute_skills", END])

    def return_tool_data_to_origin(state: MessagesState):
        for msg in reversed(state["messages"]):
            if "Routing payload context to:" in msg.content:
                if "pricing_agent" in msg.content: return "pricing_agent"
                if "inventory_agent" in msg.content: return "inventory_agent"
        return "supervisor"

    builder.add_conditional_edges("execute_skills", return_tool_data_to_origin)

    return builder.compile()


# =====================================================================
# 3. Main Entry Point (connects to MCP server, then runs the graph)
# =====================================================================
async def run():
    server_params = StdioServerParameters(
        command="python",
        args=["/Users/joelandres/apps/my_online_store/store_mcp.py"]
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await load_mcp_tools(session)

            pricing_tool = next(t for t in tools if t.name == "query_product_pricing")
            inventory_tool = next(t for t in tools if t.name == "execute_safe_stock_mutation")

            store_app = build_graph(pricing_tool, inventory_tool)

            print("--- Running Test Case: Pricing Inquiry ---")
            query_1 = "Hi, how much does a coffee mug cost here?"
            output_1 = await store_app.ainvoke({"messages": [HumanMessage(content=query_1)]})
            for message in output_1["messages"]:
                if isinstance(message, AIMessage) and not message.tool_calls and "Routing" not in message.content:
                    print(f"Store Team Output: {message.content}\n")

            print("--- Running Test Case: Inventory Mutation ---")
            query_2 = "Please add 10 units to the stock for SKU-MUG-01."
            output_2 = await store_app.ainvoke({"messages": [HumanMessage(content=query_2)]})
            for message in output_2["messages"]:
                if isinstance(message, AIMessage) and not message.tool_calls and "Routing" not in message.content:
                    print(f"Store Team Output: {message.content}\n")


if __name__ == "__main__":
    asyncio.run(run())

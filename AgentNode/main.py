import asyncio
from langsmith import traceable
from langchain_core.messages import HumanMessage, AIMessage
from src.agent import agent

# 8. Production Invocation w/ Context + Streaming
@traceable
async def handle_customer_query(customer_id: str, query: str, context: str):
    config = {"configurable": {"thread_id": f"customer_{customer_id}"}}

    input_state = {
        "messages": [HumanMessage(content=query)],
        "customer_context": context,     # Persistent profile injection
    }

    final_message = None
    # Streaming for real-time UX
    async for event in agent.astream(input_state, config, stream_mode="values"):
        current_messages = event["messages"]
        print("--- Current State Messages ---")
        for msg in current_messages:
            print(f"[{type(msg).__name__}]: {msg.content}")
            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                print(f"  Tool calls: {msg.tool_calls}")
            if hasattr(msg, 'tool_call_id'):
                print(f"  Tool call ID: {msg.tool_call_id}")
            if hasattr(msg, 'structured_response'):
                print(f"  📊 Confidence: {msg.structured_response.confidence}")
        print("----------------------------")

        last_msg = event["messages"][-1]
        if isinstance(last_msg, AIMessage):
            print(f"🤖: {last_msg.content}")
            if hasattr(last_msg, 'structured_response'):
                print(f"  📊 Confidence: {last_msg.structured_response.confidence}")

        final_message = last_msg

    if final_message:
        return final_message
    else:
        raise ValueError("No response received from the agent.")

if __name__ == "__main__":
    # 9. Prod Usage
    asyncio.run(handle_customer_query(
        customer_id="user_456",
        query="Are there any affordable gaming laptops under $1500 currently in stock?",
        context="VIP customer, prefers gaming laptops"
    ))

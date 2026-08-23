import json
import asyncio
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage
from src.agent import agent

app = FastAPI(
    title="LangGraph Agent API",
    description="An agentic e-commerce assistant API built with LangGraph and FastAPI.",
    version="1.0.0"
)

class ChatRequest(BaseModel):
    query: str
    customer_id: str = "default_user"
    context: str = "Standard customer"

async def event_generator(query: str, customer_id: str, context: str):
    config = {"configurable": {"thread_id": f"customer_{customer_id}"}}
    input_state = {
        "messages": [HumanMessage(content=query)],
        "customer_context": context,
    }

    # Iterate over the agent's events
    async for event in agent.astream(input_state, config, stream_mode="values"):
        # We process the messages to find the new ones or just emit the state state
        # In stream_mode="values", event["messages"] is the full list.
        # Ideally, we'd filter for what's new. simpler for now: just grab the last message.
        
        messages = event.get("messages", [])
        if messages:
            last_msg = messages[-1]
            
            # Serialize based on message type
            msg_type = type(last_msg).__name__
            content = last_msg.content
            tool_calls = getattr(last_msg, 'tool_calls', None)
            structured = getattr(last_msg, 'structured_response', None)
            
            chunk = {
                "type": msg_type,
                "content": content,
            }
            if tool_calls:
                chunk["tool_calls"] = tool_calls
            if structured:
                # structured_response in AgentResponse (Pydantic model)
                chunk["structured_response"] = structured.dict() if hasattr(structured, 'dict') else structured

            yield json.dumps(chunk) + "\n"

@app.post("/stream")
async def stream_chat(request: ChatRequest):
    return StreamingResponse(
        event_generator(request.query, request.customer_id, request.context),
        media_type="application/x-ndjson"
    )

@app.get("/health")
def health():
    return {"status": "ok"}

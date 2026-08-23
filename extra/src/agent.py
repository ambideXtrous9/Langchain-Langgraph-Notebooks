from langchain.agents import create_agent
from langgraph.checkpoint.memory import MemorySaver
from .config import llm, base_system_prompt
from .tools import tools
from .models import ProdAgentState, AgentResponse
from .middleware import middleware

# 7. Create Production Agent
# Dynamically format the base system prompt string with response format instructions
# formatted_system_prompt = base_system_prompt.format(format_instructions=AgentResponse.schema_json()) # Commented out to avoid premature formatting

agent = create_agent(
    llm,
    tools,
    state_schema=ProdAgentState,     # Typed state + reducers
    response_format=AgentResponse,   # Structured output
    system_prompt=base_system_prompt,            # Pass the base_system_prompt string directly
    middleware=[],           # Temporarily disable all middleware for debugging
    checkpointer=MemorySaver(),      # Persistent threads (Postgres in prod)
    #max_iterations=8,                # Prevent loops - This argument is not supported by create_agent()
)

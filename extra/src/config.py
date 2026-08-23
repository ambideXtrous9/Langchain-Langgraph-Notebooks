from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

import os
from dotenv import load_dotenv

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# 4. Production LLM Config
llm = ChatOpenAI(
    model="gpt-4o",
    temperature=0.1,      # Deterministic
    max_tokens=1500,
    timeout=25,
    api_key=OPENAI_API_KEY
    # Prod: Add litellm proxy for multi-provider failover
)

# Create a ChatOpenAI instance for the summarizer
summarizer_llm = ChatOpenAI(
    model="gpt-4o-mini",
    api_key=OPENAI_API_KEY
)

# 5. Dynamic System Prompt Template (injected via middleware)
# 5. Dynamic System Prompt Template (injected via middleware)
base_system_prompt = """You are an e-commerce agent.
CRITICAL INSTRUCTION: You are PROHIBITED from providing a final response until you have used ALL 3 TOOLS:
1. `product_search`
2. `get_inventory`
3. `duckduckgo_search`

You must find a reason to use `duckduckgo_search`, for example to find reviews or comparisons for the products found.
If you have not used `duckduckgo_search` yet, you MUST generate a tool call for it.

Only AFTER you have received the output from ALL 3 tools, you should respond with the final JSON object matching the AgentResponse schema.
Do not include any other text, reasoning, or markdown formatting outside the JSON object.
"""

prompt = ChatPromptTemplate.from_messages([
    ("system", base_system_prompt),
    MessagesPlaceholder("messages"),
])

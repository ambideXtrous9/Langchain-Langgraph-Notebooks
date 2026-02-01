import operator
import asyncio
from typing import Annotated, List, TypedDict
from dotenv import load_dotenv

load_dotenv()

from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

# Initialize LLM
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

# 1. Define Structured Output for the Planner
class ResearchPlan(BaseModel):
    queries: List[str] = Field(description="List of 3 specific search queries")

# 2. Define the Graph State
class GlobalState(TypedDict):
    topic: str
    queries: List[str] # Added to persist plan across nodes
    findings: Annotated[List[str], operator.add] # Reducer collects findings
    report: str

# 3. Analyst Planner: Generates sub-queries
def analyst_planner(state: GlobalState):
    print(f"--- Planning research for: {state['topic']} ---")
    # Logic: Use LLM with .with_structured_output(ResearchPlan)
    planner = llm.with_structured_output(ResearchPlan)
    
    prompt = f"Generate 3 distinct search queries to research the topic: {state['topic']}."
    plan = planner.invoke(prompt)
    
    # Return the plan to update the state
    return {"queries": plan.queries}

# 3.1. Conditional Logic: Fan out
def assign_researchers(state: GlobalState):
    # Map step: spawn one researcher per query
    return [Send("researcher", {"query": q}) for q in state["queries"]]

# 4. Researcher Node: Processes a single task
def researcher(state: dict):
    print(f"--- Investigating: {state['query']} ---")
    search = DuckDuckGoSearchRun()
    try:
        # Simple retry or safe execution
        result = search.run(state["query"])
    except Exception as e:
        result = f"Error searching for {state['query']}: {e}"
        
    return {"findings": [f"Source ({state['query']}):\n{result}\n"]}

# 5. Analyst Synthesizer: Reduce step to aggregate results
def analyst_synthesizer(state: GlobalState):
    print("--- Synthesizing Report ---")
    combined_findings = "\n\n".join(state["findings"])
    
    # Logic: LLM generates final report from combined_findings
    messages = [
        SystemMessage(content="You are a senior analyst. Synthesize the following research findings into a comprehensive report."),
        HumanMessage(content=f"Topic: {state['topic']}\n\nFindings:\n{combined_findings}")
    ]
    response = llm.invoke(messages)
    return {"report": response.content}

# 6. Build the Agentic Workflow
builder = StateGraph(GlobalState)

builder.add_node("analyst_planner", analyst_planner)
builder.add_node("researcher", researcher)
builder.add_node("analyst_synthesizer", analyst_synthesizer)

# Start -> Planner
builder.add_edge(START, "analyst_planner")

# Planner -> (fan out) -> Researchers
builder.add_conditional_edges("analyst_planner", assign_researchers, ["researcher"])

# Researchers -> Synthesizer
builder.add_edge("researcher", "analyst_synthesizer")
builder.add_edge("analyst_synthesizer", END)

graph = builder.compile()

async def main():
    topic = "The Future of Indian Economy and Stock Market"
    
    # Save Graph as PNG
    try:
        print("Generating graph image...")
        png_bytes = graph.get_graph().draw_mermaid_png()
        with open("map_reduce_graph.png", "wb") as f:
            f.write(png_bytes)
        print("Graph saved to map_reduce_graph.png")
    except Exception as e:
        print(f"Failed to save graph image: {e}")

    print(f"Starting execution for topic: {topic}")
    print("-" * 50)
    
    # Run the graph in a stream
    async for event in graph.astream({"topic": topic}, stream_mode="updates"):
        for key, value in event.items():
            if key == "researcher":
                # Print a small indicator that a researcher finished
                findings = value.get("findings", [""])[0]
                snippet = findings.replace("\n", " ")[:100]
                print(f"Researcher completed: {snippet}...")
            elif key == "analyst_synthesizer":
                print("\n" + "=" * 50)
                print("FINAL REPORT")
                print("=" * 50)
                print(value["report"])

if __name__ == "__main__":
    asyncio.run(main())
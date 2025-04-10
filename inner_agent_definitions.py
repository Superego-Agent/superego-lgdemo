import os
from typing import Dict, List, Any
from langchain_core.messages import BaseMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.graph import MessagesState
from langchain_anthropic import ChatAnthropic
from config import CONFIG
from utils import shout_if_fails 

@shout_if_fails
def load_inner_agent_instructions():
    file_path = CONFIG["file_paths"]["inner_agent_instructions"]
    with open(file_path, encoding='utf-8') as f:
        return f.read()

def create_default_inner_agent_runnable(inner_model: Any):
    """Creates the default runnable chain for the inner agent."""
    inner_agent_instructions = load_inner_agent_instructions()
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", inner_agent_instructions),
        MessagesPlaceholder(variable_name="messages")
    ])
    chain = prompt_template | inner_model
    return chain

# This is the function to be used as the node in the graph
def default_inner_agent_node(state: MessagesState, inner_model: Any) -> Dict[str, List[BaseMessage]]:
    """Executes the default inner agent logic."""
    messages = state["messages"]
    # Create the runnable each time or pass it if it's stable
    chain = create_default_inner_agent_runnable(inner_model)
    response = chain.invoke({"messages": messages})
    # Ensure the response has a name for downstream processing (like history adaptation)
    response.name = "inner_agent" # Set the name attribute
    return {"messages": [response]}

# Potential future structure for pluggability:
# AVAILABLE_INNER_AGENTS = {
#     "default": default_inner_agent_node,
#     # "experimental_agent": experimental_agent_node, # Example
# }
#
# def get_inner_agent_node(agent_id: str = "default"):
#     return AVAILABLE_INNER_AGENTS.get(agent_id, default_inner_agent_node)

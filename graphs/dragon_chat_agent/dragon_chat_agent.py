"""Define the dragon_chat_agent with dynamic tools support."""

import logging

from langchain.agents import create_agent
from langchain_core.tools import tool
from graphs.dragon_chat_agent.utils.langfuse import get_callbacks
from graphs.dragon_chat_agent.context import DragonAgentContext
from graphs.dragon_chat_agent.middleware.pre_agent_middleware import (
    PreAgentMiddleware,
)
from graphs.dragon_chat_agent.middleware.dynamic_prompt import inject_dynamic_prompt
from graphs.dragon_chat_agent.middleware.trim_messages import trim_messages
from graphs.dragon_chat_agent.utils.load_model import load_chat_model

callbacks = get_callbacks()

# Load default model
default_model = load_chat_model("gpt-5-mini")


@tool
def _placeholder_dynamic_router() -> str:
    """Internal placeholder to keep the ToolNode alive."""
    return "dynamic-router"


agent = create_agent(
    model=default_model,
    tools=[_placeholder_dynamic_router],
    context_schema=DragonAgentContext,
    middleware=[inject_dynamic_prompt, PreAgentMiddleware(), trim_messages],
).with_config({"callbacks": callbacks})


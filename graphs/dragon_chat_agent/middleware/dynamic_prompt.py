from langchain.agents.middleware import ModelRequest, dynamic_prompt

from graphs.dragon_chat_agent.context import DragonAgentContext
from graphs.dragon_chat_agent.prompts import DEFAULT_SYSTEM_PROMPT
from graphs.dragon_chat_agent.utils.context_builder import (
    build_datetime_context_section,
    build_user_context_section,
)


@dynamic_prompt
def inject_dynamic_prompt(request: ModelRequest) -> str:
    """Build the final system prompt from the dynamic context."""
    ctx = getattr(request.runtime, "context", None)

    base_prompt = DEFAULT_SYSTEM_PROMPT
    user_context = ""
    
    if isinstance(ctx, DragonAgentContext):
        base_prompt = ctx.system_prompt or DEFAULT_SYSTEM_PROMPT
        if ctx.metadata:
            user_context = build_user_context_section(ctx.metadata)
    elif isinstance(ctx, dict):
        base_prompt = ctx.get("system_prompt", DEFAULT_SYSTEM_PROMPT)
        metadata = ctx.get("metadata", {})
        if metadata:
            user_context = build_user_context_section(metadata)
    
    # Add datetime context section
    datetime_context = build_datetime_context_section()
    
    return base_prompt + user_context + datetime_context

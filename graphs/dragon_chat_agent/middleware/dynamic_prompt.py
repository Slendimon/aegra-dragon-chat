from langchain.agents.middleware import ModelRequest, dynamic_prompt

from graphs.dragon_chat_agent.context import DragonAgentContext
from graphs.dragon_chat_agent.prompts import DEFAULT_SYSTEM_PROMPT
from graphs.dragon_chat_agent.utils.context_builder import (
    build_datetime_context_section,
    build_knowledge_base_instructions,
    build_user_context_section,
)


@dynamic_prompt
def inject_dynamic_prompt(request: ModelRequest) -> str:
    """Build the final system prompt from the dynamic context.

    Priority order for system prompt:
    1. system_prompt from runtime context (injected from assistant config)
    2. DEFAULT_SYSTEM_PROMPT - fallback

    Note: The system_prompt is extracted from assistant.config and injected
    into the runtime context by execute_run_async before graph execution.
    """
    ctx = getattr(request.runtime, "context", None)
    metadata = getattr(request.runtime, "metadata", None)
    print(f"Metadata: {metadata}")
    # Priority 1: Check if system_prompt exists in runtime context
    # The context receives system_prompt from assistant.config via execute_run_async
    base_prompt = None
    if isinstance(ctx, DragonAgentContext):
        base_prompt = ctx.system_prompt
    elif isinstance(ctx, dict):
        base_prompt = ctx.get("system_prompt")

    # Priority 2: Fallback to default
    if not base_prompt:
        base_prompt = DEFAULT_SYSTEM_PROMPT

    # Build user context from metadata
    user_context = ""
    if isinstance(ctx, DragonAgentContext):
        if ctx.metadata:
            user_context = build_user_context_section(ctx.metadata)
    elif isinstance(ctx, dict):
        metadata = ctx.get("metadata", {})
        if metadata:
            user_context = build_user_context_section(metadata)

    # Add datetime context section
    datetime_context = build_datetime_context_section()

    # Check if assistant has knowledge base (from metadata)
    has_knowledge_base = False
    if isinstance(ctx, DragonAgentContext):
        if ctx.metadata and isinstance(ctx.metadata, dict):
            has_knowledge_base = ctx.metadata.get("has_knowledge_base", False)
    elif isinstance(ctx, dict):
        metadata = ctx.get("metadata", {})
        if metadata and isinstance(metadata, dict):
            has_knowledge_base = metadata.get("has_knowledge_base", False)

    # Add knowledge base instructions only if assistant has KB
    knowledge_instructions = build_knowledge_base_instructions(has_knowledge_base)

    return base_prompt + user_context + datetime_context + knowledge_instructions

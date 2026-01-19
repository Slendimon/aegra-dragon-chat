from langchain.agents.middleware import ModelRequest, dynamic_prompt

import structlog

from graphs.dragon_chat_agent.context import DragonAgentContext
from graphs.dragon_chat_agent.prompts import DEFAULT_SYSTEM_PROMPT
from graphs.dragon_chat_agent.utils.context_builder import (
    build_datetime_context_section,
    build_knowledge_base_instructions,
    build_user_context_section,
)
from graphs.dragon_chat_agent.utils.datetime_utils import get_current_zulu_datetime

logger = structlog.get_logger(__name__)


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
    runtime_config = getattr(request.runtime, "config", None)
    # Note: runtime.metadata may exist, but we primarily use ctx.metadata / ctx["metadata"].
    # Priority 1: Check if system_prompt exists in runtime context
    # The context receives system_prompt from assistant.config via execute_run_async
    base_prompt = None
    prompt_source = None

    # Priority 1: system_prompt from assistant config (DB) -> runtime.config
    if isinstance(runtime_config, dict):
        prompt_cfg = runtime_config.get("prompt", {})
        if isinstance(prompt_cfg, dict) and prompt_cfg.get("system_prompt"):
            base_prompt = prompt_cfg["system_prompt"]
            prompt_source = "runtime.config.prompt.system_prompt"
        elif runtime_config.get("system_prompt"):
            base_prompt = runtime_config["system_prompt"]
            prompt_source = "runtime.config.system_prompt"

    # Priority 2: fallback to runtime context
    if isinstance(ctx, DragonAgentContext):
        base_prompt = ctx.system_prompt
        prompt_source = prompt_source or "runtime.context.system_prompt"
    elif isinstance(ctx, dict):
        base_prompt = ctx.get("system_prompt")
        prompt_source = prompt_source or "runtime.context.system_prompt"

    # Priority 2: Fallback to default
    if not base_prompt:
        base_prompt = DEFAULT_SYSTEM_PROMPT
        prompt_source = prompt_source or "default"

    # Build user context from metadata
    user_context = ""
    if isinstance(ctx, DragonAgentContext):
        if ctx.metadata:
            user_context = build_user_context_section(ctx.metadata)
    elif isinstance(ctx, dict):
        metadata = ctx.get("metadata", {})
        if metadata:
            user_context = build_user_context_section(metadata)

    # Add datetime context section (support placeholder replacement if prompt templates expect it)
    current_datetime = get_current_zulu_datetime()
    datetime_context = build_datetime_context_section(current_datetime)

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

    # Prefer replacing placeholders if present in the base prompt
    insertion_mode = "appended"
    if "{datetime_context}" in base_prompt or "{{datetime_context}}" in base_prompt:
        base_prompt = base_prompt.replace("{datetime_context}", datetime_context).replace(
            "{{datetime_context}}", datetime_context
        )
        insertion_mode = "replaced_section"

    if "{current_datetime}" in base_prompt or "{{current_datetime}}" in base_prompt:
        base_prompt = base_prompt.replace("{current_datetime}", current_datetime).replace(
            "{{current_datetime}}", current_datetime
        )
        insertion_mode = "replaced_value"

    final_prompt = base_prompt + user_context
    if insertion_mode == "appended":
        final_prompt += datetime_context
    final_prompt += knowledge_instructions

    logger.debug(
        "dynamic_prompt.built",
        prompt_source=prompt_source,
        insertion_mode=insertion_mode,
        has_user_context=bool(user_context),
        has_knowledge_instructions=bool(knowledge_instructions),
        has_runtime_context=ctx is not None,
        runtime_context_type=type(ctx).__name__ if ctx is not None else None,
    )
    return final_prompt

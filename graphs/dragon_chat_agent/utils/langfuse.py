
import os
import structlog

logger = structlog.get_logger(__name__)

default_instructions = """You are a helpful assistant that answers concisely"""

def _is_langfuse_tracing_enabled() -> bool:
    """Check if Langfuse tracing is enabled via environment variable."""
    return os.getenv("LANGFUSE_TRACING", "false").lower() in ("true", "1", "yes")

def fetch_system_prompt(prompt_id: str) -> str:
    """Fetch a system prompt from Langfuse when tracing is enabled.

    - prompt_id: required identifier to fetch.

    Returns the prompt text or the provided default.
    """

    if not prompt_id:
        raise ValueError("prompt_id is required")

    try:
        if _is_langfuse_tracing_enabled():
            from langfuse import get_client

            lf_client = get_client()
            lf_prompt = lf_client.get_prompt(prompt_id)
            if lf_prompt and getattr(lf_prompt, "prompt", None):
                return lf_prompt.prompt
            else:
                logger.debug(f"Langfuse prompt '{prompt_id}' not found or has no content.")
                return default_instructions
        else:
            logger.debug("Langfuse tracing not enabled; using default instructions.")
            return default_instructions
    except Exception:
        logger.debug("Langfuse prompt fetch failed", exc_info=True)
        return default_instructions

def get_callbacks() -> list:
    """Get a list of callback handlers based on settings.

    Returns a list of callback handlers for tracing if enabled.
    """
    callbacks = []
    if _is_langfuse_tracing_enabled():
        try:
            #TODO Switch to imports once Langfuse integration is supported in LangChain
            #TODO from langfuse.langchain import CallbackHandler
            from graphs.dragon_chat_agent.utils.langchain_langfuse import CallbackHandler
            langfuse_handler = CallbackHandler()
            callbacks.append(langfuse_handler)
        except Exception as e:
            logger.warning(f"Failed to initialize Langfuse handler: {e}")
    return callbacks

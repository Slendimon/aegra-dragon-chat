from graphs.dragon_chat_agent.core.llm import get_model

def load_chat_model(model_name: str):
    """Load a chat model by name."""
    return get_model(model_name)

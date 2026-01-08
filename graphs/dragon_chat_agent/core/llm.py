from functools import cache
from langchain_openai import ChatOpenAI

@cache
def get_model(model_name: str, /) -> ChatOpenAI:
    # No agregar temperatura para modelos gpt-5-mini o gpt5
    if "gpt-5-mini" in model_name.lower() or "gpt5" in model_name.lower():
        return ChatOpenAI(
            model=model_name,
            stream_options={"include_usage": True}
        )
    return ChatOpenAI(
        model=model_name,
        temperature=0.5,
        stream_options={"include_usage": True}
    )
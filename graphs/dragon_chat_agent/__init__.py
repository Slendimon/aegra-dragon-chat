"""Dragon Chat Agent module.

Keep imports lightweight: avoid importing the full agent graph (and its heavy
dependencies) at package import time. The `agent` is exposed via a lazy import.
"""

from typing import Any

__all__ = ["agent"]


def __getattr__(name: str) -> Any:  # pragma: no cover
    if name == "agent":
        from graphs.dragon_chat_agent.dragon_chat_agent import agent  # local import

        return agent
    raise AttributeError(name)


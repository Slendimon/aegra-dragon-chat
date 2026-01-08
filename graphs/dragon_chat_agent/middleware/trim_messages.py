from typing import Any

import structlog
from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ModelRequest, ModelResponse

logger = structlog.get_logger(__name__)

MAX_MESSAGES = 20

class TrimMessagesMiddleware(AgentMiddleware):
    """Middleware to trim messages to a maximum of 20 before calling the model."""

    def wrap_model_call(self, request: ModelRequest, handler) -> ModelResponse:
        """Trim messages just before sending them to the model."""
        if "messages" in request.state:
            messages = request.state["messages"]
            if len(messages) > MAX_MESSAGES:
                logger.info(
                    f"[TrimMessages] Trimming messages from {len(messages)} to {MAX_MESSAGES}"
                )
                trimmed_messages = messages[-MAX_MESSAGES:]
                # Update both request.state and request.messages
                updated_state = {**request.state, "messages": trimmed_messages}
                request = request.override(state=updated_state, messages=trimmed_messages)
        return handler(request)

    async def awrap_model_call(
        self, request: ModelRequest, handler
    ) -> ModelResponse:
        """Async version to trim messages just before sending them to the model."""
        if "messages" in request.state:
            messages = request.state["messages"]
            if len(messages) > MAX_MESSAGES:
                logger.info(
                    f"[TrimMessages] Trimming messages from {len(messages)} to {MAX_MESSAGES}"
                )
                trimmed_messages = messages[-MAX_MESSAGES:]
                # Update both request.state and request.messages
                updated_state = {**request.state, "messages": trimmed_messages}
                request = request.override(state=updated_state, messages=trimmed_messages)
        return await handler(request)


trim_messages = TrimMessagesMiddleware()
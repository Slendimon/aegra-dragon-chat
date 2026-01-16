import structlog
from typing import Any, Dict, Iterable, List

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ModelRequest, ModelResponse
from langchain_core.messages import ToolMessage
from langgraph.prebuilt.tool_node import msg_content_output

from graphs.dragon_chat_agent.context import DragonAgentContext
from graphs.dragon_chat_agent.utils.message_validator import validate_and_clean_messages
from graphs.dragon_chat_agent.tools import build_tool_from_config

logger = structlog.getLogger(__name__)


class PreAgentMiddleware(AgentMiddleware):
    """Middleware that builds dynamic tools from config before agent execution."""

    def _ensure_context(self, request: ModelRequest) -> DragonAgentContext:
        context = getattr(request.runtime, "context", None)
        if context is None or not isinstance(context, DragonAgentContext):
            context = DragonAgentContext()
            request.runtime.context = context
        return context

    @staticmethod
    def _extract_tool_configs(context: DragonAgentContext) -> Iterable[dict[str, Any]]:
        tools_cfg = context.tools
        if not tools_cfg:
            return []
        return tools_cfg

    @staticmethod
    def _to_llm_tool_spec(cfg: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": cfg["name"],
                "description": cfg.get("description", ""),
                "parameters": cfg.get("schema", {"type": "object", "properties": {}}),
            },
        }

    def _build_runtime_tooling(
        self, context: DragonAgentContext
    ) -> tuple[Dict[str, Any], List[dict[str, Any]]]:
        dynamic_tools: Dict[str, Any] = {}
        tool_specs: List[dict[str, Any]] = []

        for cfg in self._extract_tool_configs(context):
            try:
                tool = build_tool_from_config(cfg)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to build dynamic tool %s: %s", cfg.get("name"), exc)
                continue

            dynamic_tools[tool.name] = tool
            tool_specs.append(self._to_llm_tool_spec(cfg))

        return dynamic_tools, tool_specs

    @staticmethod
    def _should_force_tool(state: dict[str, Any], tool_names: List[str]) -> bool:
        if not tool_names:
            return False
        messages = state.get("messages", [])
        for message in reversed(messages):
            if isinstance(message, ToolMessage) and message.name in tool_names:
                return False
        return True

    def _resolve_tool_choice(
        self,
        request_state: dict[str, Any],
        tool_specs: List[dict[str, Any]],
        original_choice: Any,
    ) -> Any:
        if not tool_specs:
            return None
        tool_names = [spec["function"]["name"] for spec in tool_specs]
        if self._should_force_tool(request_state, tool_names):
            if len(tool_names) == 1:
                return {
                    "type": "function",
                    "function": {"name": tool_names[0]},
                }
            return "auto"
        return original_choice or "auto"

    def wrap_model_call(self, request: ModelRequest, handler) -> ModelResponse:
        context = self._ensure_context(request)
        dynamic_tools, tool_specs = self._build_runtime_tooling(context)
        context.dynamic_tools = dynamic_tools

        # Validate and clean messages to ensure tool_calls have corresponding ToolMessages
        if "messages" in request.state:
            cleaned_messages = validate_and_clean_messages(request.state["messages"])
            if cleaned_messages != request.state["messages"]:
                updated_state = {**request.state, "messages": cleaned_messages}
                request = request.override(state=updated_state)

        # Only override tools if there are dynamic tools to add
        # Don't override if tool_specs is empty - keep the existing static tools
        overrides = {}
        if tool_specs:
            # Combine existing tools with dynamic tools
            existing_tools = request.tools or []
            combined_tools = list(existing_tools) + tool_specs
            overrides["tools"] = combined_tools
            overrides["tool_choice"] = self._resolve_tool_choice(
                request.state, tool_specs, request.tool_choice
            )

        if overrides:
            updated_request = request.override(**overrides)
            return handler(updated_request)
        return handler(request)

    async def awrap_model_call(
        self, request: ModelRequest, handler
    ) -> ModelResponse:
        """Build dynamic tools from context and add them to the request."""
        context = self._ensure_context(request)
        dynamic_tools, tool_specs = self._build_runtime_tooling(context)
        context.dynamic_tools = dynamic_tools

        # Validate and clean messages to ensure tool_calls have corresponding ToolMessages
        if "messages" in request.state:
            cleaned_messages = validate_and_clean_messages(request.state["messages"])
            if cleaned_messages != request.state["messages"]:
                updated_state = {**request.state, "messages": cleaned_messages}
                request = request.override(state=updated_state)

        # Only override tools if there are dynamic tools to add
        # Don't override if tool_specs is empty - keep the existing static tools
        overrides = {}
        if tool_specs:
            # Combine existing tools with dynamic tools
            existing_tools = request.tools or []
            combined_tools = list(existing_tools) + tool_specs
            overrides["tools"] = combined_tools
            overrides["tool_choice"] = self._resolve_tool_choice(
                request.state, tool_specs, request.tool_choice
            )

        if overrides:
            updated_request = request.override(**overrides)
            return await handler(updated_request)
        return await handler(request)

    def _lookup_runtime_tool(self, request) -> Any | None:
        runtime_context = getattr(request.runtime, "context", None)
        tool_name = request.tool_call["name"]

        if isinstance(runtime_context, DragonAgentContext):
            return runtime_context.dynamic_tools.get(tool_name)

        if isinstance(runtime_context, dict):
            dynamic_tools = runtime_context.get("dynamic_tools") or {}
            if isinstance(dynamic_tools, dict):
                return dynamic_tools.get(tool_name)

        return None

    def _get_available_dynamic_tools(self, request) -> List[str]:
        """Get list of available dynamic tool names for debugging."""
        runtime_context = getattr(request.runtime, "context", None)

        if isinstance(runtime_context, DragonAgentContext):
            return list(runtime_context.dynamic_tools.keys())

        if isinstance(runtime_context, dict):
            dynamic_tools = runtime_context.get("dynamic_tools") or {}
            if isinstance(dynamic_tools, dict):
                return list(dynamic_tools.keys())

        return []

    def _ensure_context_from_request(self, request) -> DragonAgentContext | None:
        """Get or create DragonAgentContext from request runtime."""
        runtime_context = getattr(request.runtime, "context", None)

        if isinstance(runtime_context, DragonAgentContext):
            return runtime_context

        if isinstance(runtime_context, dict):
            # Try to convert dict to DragonAgentContext
            try:
                return DragonAgentContext(
                    system_prompt=runtime_context.get("system_prompt"),
                    tools=runtime_context.get("tools", []),
                    dynamic_tools=runtime_context.get("dynamic_tools", {}),
                    metadata=runtime_context.get("metadata", {}),
                )
            except Exception as exc:
                logger.warning("Failed to create DragonAgentContext from dict: %s", exc)
                return None

        return None

    def wrap_tool_call(self, request, handler):
        tool_name = request.tool_call["name"]
        tool_call_id = request.tool_call["id"]

        logger.info(
            "wrap_tool_call invoked for tool '%s', tool_call_id='%s'",
            tool_name,
            tool_call_id,
        )

        # First try to lookup in existing dynamic_tools
        tool = self._lookup_runtime_tool(request)
        available_tools = self._get_available_dynamic_tools(request)

        # If not found, try to rebuild dynamic tools from context
        # This handles the case where context.dynamic_tools was lost between model call and tool call
        if tool is None and not available_tools:
            logger.info("No dynamic_tools found, attempting to rebuild from context.tools")
            context = self._ensure_context_from_request(request)
            if context and context.tools:
                dynamic_tools, _ = self._build_runtime_tooling(context)
                context.dynamic_tools = dynamic_tools
                tool = dynamic_tools.get(tool_name)
                available_tools = list(dynamic_tools.keys())
                logger.info(
                    "Rebuilt dynamic_tools: found=%s, available=%s",
                    tool is not None,
                    available_tools,
                )

        logger.info(
            "Tool lookup result: found=%s, available_dynamic_tools=%s",
            tool is not None,
            available_tools,
        )

        if tool is None:
            # Try the default handler for static tools
            logger.info("Tool '%s' not in dynamic_tools, trying static handler", tool_name)
            try:
                return handler(request)
            except Exception as exc:
                # Tool not found in static tools either - return error message
                logger.error(
                    "Tool '%s' not found in dynamic_tools or static tools. "
                    "Available dynamic tools: %s. Error: %s (%s)",
                    tool_name,
                    available_tools,
                    exc,
                    type(exc).__name__,
                )
                return ToolMessage(
                    content=f"Error: Tool '{tool_name}' is not available. The tool may not be configured correctly or the context was lost.",
                    name=tool_name,
                    tool_call_id=tool_call_id,
                    status="error",
                )

        logger.info("Executing dynamic tool '%s'", tool_name)
        try:
            result = tool.invoke(request.tool_call["args"])
        except Exception as exc:  # noqa: BLE001
            logger.warning("Dynamic tool %s failed: %s", tool.name, exc)
            return ToolMessage(
                content=str(exc),
                name=tool_name,
                tool_call_id=tool_call_id,
                status="error",
            )

        logger.info("Dynamic tool '%s' completed successfully", tool_name)
        return ToolMessage(
            content=msg_content_output(result),
            name=tool_name,
            tool_call_id=tool_call_id,
        )

    async def awrap_tool_call(self, request, handler):
        tool_name = request.tool_call["name"]
        tool_call_id = request.tool_call["id"]

        logger.info(
            "awrap_tool_call invoked for tool '%s', tool_call_id='%s'",
            tool_name,
            tool_call_id,
        )

        # First try to lookup in existing dynamic_tools
        tool = self._lookup_runtime_tool(request)
        available_tools = self._get_available_dynamic_tools(request)

        # If not found, try to rebuild dynamic tools from context
        # This handles the case where context.dynamic_tools was lost between model call and tool call
        if tool is None and not available_tools:
            logger.info("No dynamic_tools found, attempting to rebuild from context.tools")
            context = self._ensure_context_from_request(request)
            if context and context.tools:
                dynamic_tools, _ = self._build_runtime_tooling(context)
                context.dynamic_tools = dynamic_tools
                tool = dynamic_tools.get(tool_name)
                available_tools = list(dynamic_tools.keys())
                logger.info(
                    "Rebuilt dynamic_tools: found=%s, available=%s",
                    tool is not None,
                    available_tools,
                )

        logger.info(
            "Tool lookup result: found=%s, available_dynamic_tools=%s",
            tool is not None,
            available_tools,
        )

        if tool is None:
            # Try the default handler for static tools
            logger.info("Tool '%s' not in dynamic_tools, trying static handler", tool_name)
            try:
                return await handler(request)
            except Exception as exc:
                # Tool not found in static tools either - return error message
                logger.error(
                    "Tool '%s' not found in dynamic_tools or static tools. "
                    "Available dynamic tools: %s. Error: %s (%s)",
                    tool_name,
                    available_tools,
                    exc,
                    type(exc).__name__,
                )
                return ToolMessage(
                    content=f"Error: Tool '{tool_name}' is not available. The tool may not be configured correctly or the context was lost.",
                    name=tool_name,
                    tool_call_id=tool_call_id,
                    status="error",
                )

        logger.info("Executing dynamic tool '%s'", tool_name)
        try:
            result = await tool.ainvoke(request.tool_call["args"])
        except Exception as exc:  # noqa: BLE001
            logger.warning("Dynamic tool %s failed: %s", tool.name, exc)
            return ToolMessage(
                content=str(exc),
                name=tool_name,
                tool_call_id=tool_call_id,
                status="error",
            )

        logger.info("Dynamic tool '%s' completed successfully", tool_name)
        return ToolMessage(
            content=msg_content_output(result),
            name=tool_name,
            tool_call_id=tool_call_id,
        )

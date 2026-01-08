"""Message validation utilities for ensuring message format compliance."""

import logging
from typing import Any, List

from langchain_core.messages import AIMessage, ToolMessage

logger = logging.getLogger(__name__)


def validate_and_clean_messages(messages: List[Any]) -> List[Any]:
    """Validate that AIMessages with tool_calls have corresponding ToolMessages.
    
    If an AIMessage has tool_calls but no corresponding ToolMessages are found,
    we add ToolMessage responses with error messages to prevent API errors.
    
    Args:
        messages: List of message objects to validate and clean
        
    Returns:
        List of messages with ToolMessage error responses added for any missing
        tool call responses
    """
    if not messages:
        return messages
    
    cleaned_messages = []
    
    for i, message in enumerate(messages):
        if isinstance(message, AIMessage) and hasattr(message, "tool_calls") and message.tool_calls:
            tool_call_info = {
                tc.get("id"): {
                    "id": tc.get("id"),
                    "name": tc.get("name", "unknown"),
                }
                for tc in message.tool_calls
                if tc.get("id")
            }
            
            if not tool_call_info:
                cleaned_messages.append(message)
                continue
            
            tool_call_ids = set(tool_call_info.keys())
            
            found_tool_call_ids = set()
            for j in range(i + 1, len(messages)):
                next_msg = messages[j]
                if isinstance(next_msg, ToolMessage):
                    tool_call_id = getattr(next_msg, "tool_call_id", None)
                    if tool_call_id in tool_call_ids:
                        found_tool_call_ids.add(tool_call_id)
                elif isinstance(next_msg, AIMessage):
                    break
            
            cleaned_messages.append(message)
            
            # Check if all tool calls have responses
            missing_tool_call_ids = tool_call_ids - found_tool_call_ids
            if missing_tool_call_ids:
                logger.warning(
                    "Found AIMessage with tool_calls but missing ToolMessage responses "
                    f"for tool_call_ids: {missing_tool_call_ids}. Adding error ToolMessages."
                )
                
                for tool_call_id in missing_tool_call_ids:
                    tool_info = tool_call_info[tool_call_id]
                    tool_name = tool_info.get("name", "unknown")
                    error_message = ToolMessage(
                        content=f"❌ Error al llamar a la herramienta '{tool_name}'. La herramienta no respondió correctamente.",
                        tool_call_id=tool_call_id,
                        name=tool_name,
                    )
                    cleaned_messages.append(error_message)
        else:
            cleaned_messages.append(message)
    
    return cleaned_messages


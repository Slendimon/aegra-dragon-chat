"""Runtime context schema for the dragon chat agent."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(kw_only=True)
class DragonAgentContext:
    """Context payload accepted by `dragon_chat_agent`."""

    system_prompt: Optional[str] = None
    tools: List[Dict[str, Any]] = field(default_factory=list)
    dynamic_tools: Dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(  
        default_factory=dict,  
        metadata={"description": "Custom metadata fields"}  
    )  



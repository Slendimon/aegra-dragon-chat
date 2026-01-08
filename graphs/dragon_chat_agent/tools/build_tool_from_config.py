import requests
from typing import Any, Dict, List

from pydantic import create_model
from langchain_core.tools import StructuredTool

def build_tool_from_config(cfg: Dict[str, Any]) -> StructuredTool:
    """Create a StructuredTool from a config that comes in request.context."""

    name = cfg["name"]
    url = cfg["url"]
    description = cfg.get("description", "")
    schema = cfg["schema"]  # JSON Schema of the arguments

    props: Dict[str, Dict[str, Any]] = schema.get("properties", {})
    required: List[str] = schema.get("required", [])

    # 1) Create a dynamic Pydantic model from the JSON Schema
    fields = {}
    for field_name, field_schema in props.items():
        default = ... if field_name in required else None
        fields[field_name] = (Any, default)

    ArgsModel = create_model(f"{name.capitalize()}Args", **fields)

    # 2) Function that will make the POST to the webhook
    def _func(**kwargs):
        # kwargs are already validated against ArgsModel by StructuredTool
        payload = kwargs

        resp = requests.post(url, json=payload, timeout=180)
        try:
            resp.raise_for_status()
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "status_code": getattr(resp, "status_code", None),
                "body": getattr(resp, "text", None),
            }

        try:
            return resp.json()
        except ValueError:
            return {
                "status": "ok",
                "status_code": resp.status_code,
                "text": resp.text,
            }

    # 3) Create the StructuredTool
    tool = StructuredTool.from_function(
        _func,
        name=name,
        description=description,
        args_schema=ArgsModel,
    )

    return tool
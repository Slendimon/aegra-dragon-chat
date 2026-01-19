import re
import time
from typing import Any, Dict, List, Tuple
from urllib.parse import urlparse

import anyio
import requests
import structlog
from langchain_core.tools import StructuredTool
from pydantic import ConfigDict, Field, create_model
from requests import RequestException

_OPENAI_TOOL_NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
logger = structlog.get_logger(__name__)


def _sanitize_tool_name(name: str) -> Tuple[str, bool]:
    """Return (sanitized_name, changed).

    OpenAI-style function/tool names must match ^[a-zA-Z0-9_-]{1,64}$.
    """
    original = (name or "").strip()
    if not original:
        return "tool", True

    sanitized = re.sub(r"[^A-Za-z0-9_-]+", "_", original)
    sanitized = sanitized.strip("_")
    if not sanitized:
        sanitized = "tool"
    sanitized = sanitized[:64]

    # Ensure it doesn't start with a dash (some providers are picky)
    if sanitized.startswith("-"):
        sanitized = f"tool{sanitized}"
        sanitized = sanitized[:64]

    changed = sanitized != original
    if not _OPENAI_TOOL_NAME_RE.match(sanitized):
        # Last resort fallback
        sanitized = "tool"
        changed = True

    return sanitized, changed


def _safe_field_name(name: str, used: set[str]) -> str:
    # Pydantic model field names must be valid identifiers.
    candidate = re.sub(r"[^A-Za-z0-9_]+", "_", name)
    if not candidate or candidate[0].isdigit():
        candidate = f"field_{candidate}"
    if not candidate.isidentifier():
        candidate = "field"

    base = candidate
    i = 2
    while candidate in used:
        candidate = f"{base}_{i}"
        i += 1
    used.add(candidate)
    return candidate


def _validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"Invalid tool url: {url!r}")

def _redact_url(url: str) -> str:
    """Redact query/fragment (webhooks may contain secrets)."""
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return url
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    except Exception:
        return url

def build_tool_from_config(cfg: Dict[str, Any]) -> StructuredTool:
    """Create a StructuredTool from a config that comes in request.context.

    Hardening goals:
    - Avoid provider-level failures due to invalid tool names.
    - Accept JSON Schema property names that are not valid Python identifiers.
    - Never raise on network failures; always return a serializable error payload.
    - Provide an async implementation to avoid blocking the event loop.
    """

    if not isinstance(cfg, dict):
        raise TypeError("Tool config must be a dict")

    raw_name = str(cfg.get("name") or "")
    name, changed = _sanitize_tool_name(raw_name)

    url = str(cfg.get("url") or "")
    logger.debug(
        "dynamic_tool.build.start",
        raw_name=raw_name or None,
        sanitized_name=name,
        name_changed=changed,
        url=_redact_url(url) if url else None,
        has_schema=bool(cfg.get("schema")),
        has_headers=isinstance(cfg.get("headers"), dict) and len(cfg.get("headers") or {}) > 0,
    )
    _validate_url(url)

    description = str(cfg.get("description") or "")
    schema = cfg.get("schema") or {"type": "object", "properties": {}}
    if not isinstance(schema, dict):
        raise TypeError("Tool schema must be a dict (JSON Schema)")

    props: Dict[str, Dict[str, Any]] = schema.get("properties", {}) or {}
    if not isinstance(props, dict):
        props = {}

    required: List[str] = schema.get("required", []) or []
    if not isinstance(required, list):
        required = []

    timeout = cfg.get("timeout", cfg.get("timeout_seconds", None))
    if isinstance(timeout, dict):
        timeout = (
            float(timeout.get("connect", 10)),
            float(timeout.get("read", 30)),
        )
    if isinstance(timeout, str):
        try:
            timeout = float(timeout)
        except ValueError:
            timeout = None
    if timeout is None:
        # keep defaults snappy so tool issues don't look like "no AI response"
        timeout = (10, 30)  # (connect, read)
    headers = cfg.get("headers") or {}
    if not isinstance(headers, dict):
        headers = {}

    logger.debug(
        "dynamic_tool.build.schema",
        tool_name=name,
        properties_count=len(props) if isinstance(props, dict) else 0,
        required_count=len(required),
        headers_count=len(headers),
        timeout=timeout,
    )

    # 1) Create a dynamic Pydantic model from the JSON Schema, using aliases
    used: set[str] = set()
    fields: Dict[str, Any] = {}
    for original_name, field_schema in props.items():
        # Required comes from original JSON Schema property names
        default = ... if original_name in required else None

        # Best-effort type mapping (fallback Any)
        json_type = None
        if isinstance(field_schema, dict):
            json_type = field_schema.get("type")
        py_type: Any = Any
        if json_type == "string":
            py_type = str
        elif json_type == "integer":
            py_type = int
        elif json_type == "number":
            py_type = float
        elif json_type == "boolean":
            py_type = bool
        elif json_type == "object":
            py_type = dict
        elif json_type == "array":
            py_type = list

        safe_name = _safe_field_name(str(original_name), used)
        fields[safe_name] = (
            py_type,
            Field(default, alias=str(original_name)),
        )

    model_cfg = ConfigDict(populate_by_name=True, extra="ignore")
    ArgsModel = create_model(f"{name.capitalize()}Args", __config__=model_cfg, **fields)

    def _do_post(payload: dict[str, Any]) -> dict[str, Any]:
        started = time.monotonic()
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
        except RequestException as exc:
            return {
                "status": "error",
                "error": str(exc),
                "error_type": type(exc).__name__,
                "url": url,
                "timeout": timeout,
                "elapsed_ms": int((time.monotonic() - started) * 1000),
            }

        elapsed_ms = int((time.monotonic() - started) * 1000)
        try:
            resp.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            return {
                "status": "error",
                "error": str(exc),
                "error_type": type(exc).__name__,
                "status_code": getattr(resp, "status_code", None),
                "body": getattr(resp, "text", None),
                "url": url,
                "elapsed_ms": elapsed_ms,
            }

        try:
            data = resp.json()
        except ValueError:
            data = {
                "status": "ok",
                "status_code": resp.status_code,
                "text": resp.text,
            }

        if isinstance(data, dict):
            data.setdefault("elapsed_ms", elapsed_ms)
            return data
        # Ensure tool output is always JSON-serializable (dict/str)
        return {"status": "ok", "data": data, "elapsed_ms": elapsed_ms}

    # 2) Functions that will make the POST to the webhook
    def _func(**kwargs):
        # kwargs are validated against ArgsModel by StructuredTool
        payload = ArgsModel(**kwargs).model_dump(by_alias=True, exclude_none=True)
        return _do_post(payload)

    async def _afunc(**kwargs):
        payload = ArgsModel(**kwargs).model_dump(by_alias=True, exclude_none=True)
        return await anyio.to_thread.run_sync(_do_post, payload)

    # 3) Create the StructuredTool (sync + async)
    tool_description = description
    if changed:
        tool_description = (
            f"{description}\n\n(Note: original tool name was {raw_name!r}; "
            f"sanitized to {name!r} for provider compatibility.)"
        ).strip()

    tool = StructuredTool.from_function(
        _func,
        coroutine=_afunc,
        name=name,
        description=tool_description,
        args_schema=ArgsModel,
    )

    # Keep originals for debugging/telemetry
    tool.metadata = {"original_name": raw_name, "url": url}
    logger.info(
        "dynamic_tool.build.succeeded",
        tool_name=name,
        raw_name=raw_name or None,
        url=_redact_url(url),
        properties_count=len(props) if isinstance(props, dict) else 0,
    )
    return tool
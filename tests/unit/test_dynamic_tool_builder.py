import types

import pytest
import requests

from graphs.dragon_chat_agent.context import DragonAgentContext
from graphs.dragon_chat_agent.middleware.pre_agent_middleware import PreAgentMiddleware
from graphs.dragon_chat_agent.tools.build_tool_from_config import build_tool_from_config


class _Resp:
    def __init__(self, status_code: int = 200, json_data=None, text: str = "ok"):
        self.status_code = status_code
        self._json_data = {} if json_data is None else json_data
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error")

    def json(self):
        return self._json_data


def test_build_tool_sanitizes_name_and_pre_agent_uses_it(monkeypatch):
    cfg = {
        "name": "Mi Tool ñ con espacios",
        "description": "desc",
        "url": "https://example.com/webhook",
        "schema": {"type": "object", "properties": {}, "required": []},
    }

    # Prevent real network calls
    monkeypatch.setattr(
        requests,
        "post",
        lambda *args, **kwargs: _Resp(200, json_data={"ok": True}),
    )

    middleware = PreAgentMiddleware()
    context = DragonAgentContext(tools=[cfg])
    dynamic_tools, tool_specs = middleware._build_runtime_tooling(context)

    assert len(dynamic_tools) == 1
    tool = next(iter(dynamic_tools.values()))
    assert tool.name != cfg["name"]
    assert tool_specs[0]["function"]["name"] == tool.name


def test_tool_accepts_non_identifier_properties_and_posts_original_keys(monkeypatch):
    captured = {}

    def _fake_post(url, json, headers=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        captured["timeout"] = timeout
        return _Resp(200, json_data={"status": "ok"})

    monkeypatch.setattr(requests, "post", _fake_post)

    tool = build_tool_from_config(
        {
            "name": "kb-search",
            "url": "https://example.com/webhook",
            "schema": {
                "type": "object",
                "properties": {"user-id": {"type": "string"}},
                "required": ["user-id"],
            },
        }
    )

    out = tool.invoke({"user-id": "abc"})
    assert isinstance(out, dict)
    assert out["status"] == "ok"
    assert captured["json"] == {"user-id": "abc"}


def test_tool_returns_serializable_error_on_timeout(monkeypatch):
    def _raise_timeout(*args, **kwargs):
        raise requests.Timeout("boom")

    monkeypatch.setattr(requests, "post", _raise_timeout)

    tool = build_tool_from_config(
        {
            "name": "t",
            "url": "https://example.com/webhook",
            "schema": {"type": "object", "properties": {}, "required": []},
        }
    )

    out = tool.invoke({})
    assert out["status"] == "error"
    assert out["error_type"] == "Timeout"


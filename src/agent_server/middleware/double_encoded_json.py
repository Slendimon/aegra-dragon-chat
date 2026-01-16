import json

import structlog
from starlette.types import ASGIApp, Receive, Scope, Send

logger = structlog.getLogger(__name__)


class DoubleEncodedJSONMiddleware:
    """Middleware to handle double-encoded JSON payloads from frontend.

    Some frontend clients may send JSON that's been stringified twice,
    resulting in payloads like '"{\"key\":\"value\"}"' instead of '{"key":"value"}'.
    This middleware detects and corrects such cases.
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    # Paths to skip - these have large payloads that shouldn't be re-processed
    SKIP_PATHS = {"/store/items", "/store/items/search"}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Skip certain paths entirely to avoid body processing issues
        path = scope.get("path", "")
        if path in self.SKIP_PATHS:
            await self.app(scope, receive, send)
            return

        method = scope["method"]
        headers = dict(scope.get("headers", []))
        content_type = headers.get(b"content-type", b"").decode("latin1")

        # Only process JSON content types for POST/PUT/PATCH
        if method in ["POST", "PUT", "PATCH"] and "application/json" in content_type:
            # First, collect the entire body
            body_parts = []
            while True:
                message = await receive()
                if message["type"] == "http.request":
                    body_parts.append(message.get("body", b""))
                    if not message.get("more_body", False):
                        break
                elif message["type"] == "http.disconnect":
                    # Client disconnected, pass through
                    await self.app(scope, receive, send)
                    return

            body = b"".join(body_parts)
            processed_body = body  # Default: unchanged

            if body:
                try:
                    decoded = body.decode("utf-8")
                    parsed = json.loads(decoded)

                    # Only re-serialize if the JSON was double-encoded
                    # (i.e., the first parse returned a string)
                    if isinstance(parsed, str):
                        # Double-encoded: parse again and re-serialize
                        inner_parsed = json.loads(parsed)
                        processed_body = json.dumps(inner_parsed).encode("utf-8")
                        logger.debug(
                            "Detected and fixed double-encoded JSON",
                            path=path,
                            original_length=len(body),
                            new_length=len(processed_body),
                        )
                except (json.JSONDecodeError, ValueError, UnicodeDecodeError) as e:
                    # Not valid JSON or not double-encoded, pass through unchanged
                    logger.debug(
                        "JSON processing skipped",
                        path=path,
                        error=str(e),
                    )

            # Update content-length header if body changed
            if processed_body != body:
                new_headers = [
                    (name, value)
                    for name, value in scope.get("headers", [])
                    if name.lower() not in (b"content-length",)
                ]
                new_headers.append(
                    (b"content-length", str(len(processed_body)).encode())
                )
                scope["headers"] = new_headers

            # Create a receive function that returns the processed body once
            body_sent = False

            async def receive_wrapper() -> dict:
                nonlocal body_sent
                if not body_sent:
                    body_sent = True
                    return {
                        "type": "http.request",
                        "body": processed_body,
                        "more_body": False,
                    }
                # After body is sent, wait for disconnect
                return await receive()

            await self.app(scope, receive_wrapper, send)
        else:
            await self.app(scope, receive, send)

"""
sse.py – Server-Sent Events generator helpers.

Converts an async token stream into the `data: ...\n\n` format
expected by the browser's EventSource API.
"""

import json
from typing import AsyncGenerator


async def token_to_sse(token_stream: AsyncGenerator[str, None]) -> AsyncGenerator[str, None]:
    """
    Wrap an async token generator in SSE format.

    Each event is:
        data: {"token": "..."}\\n\\n

    A final event signals completion:
        data: [DONE]\\n\\n
    """
    try:
        async for token in token_stream:
            payload = json.dumps({"token": token})
            yield f"data: {payload}\n\n"
    except Exception as e:
        error_payload = json.dumps({"error": str(e)})
        yield f"data: {error_payload}\n\n"
    finally:
        yield "data: [DONE]\n\n"


async def error_sse(message: str) -> AsyncGenerator[str, None]:
    """Yield a single SSE error event followed by [DONE]."""
    payload = json.dumps({"error": message})
    yield f"data: {payload}\n\n"
    yield "data: [DONE]\n\n"

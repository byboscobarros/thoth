"""OpenRouter streaming completion component."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from thoth.domain.providers import ProviderChunk, ProviderExecutionError, ProviderRequest
from thoth.providers.openrouter.components.completion import _build_headers, _serialize_messages


class OpenRouterStreamingComponent:
    """Execute streaming chat completions against OpenRouter (SSE)."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        default_model: str,
        timeout_seconds: float,
        http_referer: str | None = None,
        app_title: str | None = None,
        opener: Callable[..., Any] | None = None,
    ) -> None:
        self._api_key = api_key
        self._endpoint = base_url.rstrip("/") + "/chat/completions"
        self._default_model = default_model
        self._timeout_seconds = timeout_seconds
        self._http_referer = http_referer
        self._app_title = app_title
        self._opener = opener or urlopen

    def stream(self, request: ProviderRequest) -> list[ProviderChunk]:
        payload: dict[str, Any] = {
            "model": request.model or self._default_model,
            "messages": _serialize_messages(request.messages),
            "stream": True,
        }
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens

        http_request = Request(
            url=self._endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=_build_headers(
                api_key=self._api_key,
                http_referer=self._http_referer,
                app_title=self._app_title,
            ),
            method="POST",
        )

        chunks: list[ProviderChunk] = []
        chunk_index = 0
        done_emitted = False

        try:
            with self._opener(http_request, timeout=self._timeout_seconds) as response:
                for raw_line in response:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line or line.startswith(":"):
                        continue
                    if not line.startswith("data:"):
                        continue

                    data = line[5:].strip()
                    if data == "[DONE]":
                        done_emitted = True
                        break

                    payload_item = _parse_stream_event(data)
                    deltas = _extract_content_deltas(payload_item)
                    for delta in deltas:
                        chunks.append(
                            ProviderChunk(
                                request_id=request.request_id,
                                index=chunk_index,
                                content_delta=delta,
                                done=False,
                            )
                        )
                        chunk_index += 1
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise ProviderExecutionError(
                code="provider.openrouter.http_error",
                message=f"openrouter http error {exc.code}: {detail}",
            ) from exc
        except URLError as exc:
            raise ProviderExecutionError(
                code="provider.openrouter.network_error",
                message=f"openrouter network error: {exc.reason}",
            ) from exc

        chunks.append(
            ProviderChunk(
                request_id=request.request_id,
                index=chunk_index,
                content_delta="",
                done=True,
                metadata={"done_marker": done_emitted},
            )
        )
        return chunks


def _parse_stream_event(data: str) -> dict[str, Any]:
    try:
        payload = json.loads(data)
    except json.JSONDecodeError as exc:
        raise ProviderExecutionError(
            code="provider.openrouter.invalid_response",
            message="openrouter stream returned invalid json chunk",
        ) from exc

    if not isinstance(payload, dict):
        raise ProviderExecutionError(
            code="provider.openrouter.invalid_response",
            message="openrouter stream chunk must be an object",
        )
    return payload


def _extract_content_deltas(payload: dict[str, Any]) -> list[str]:
    choices = payload.get("choices")
    if not isinstance(choices, list):
        return []

    deltas: list[str] = []
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        delta = choice.get("delta")
        if not isinstance(delta, dict):
            continue
        content = delta.get("content")
        if isinstance(content, str) and content:
            deltas.append(content)
    return deltas

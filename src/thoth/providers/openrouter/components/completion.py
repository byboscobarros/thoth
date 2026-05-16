"""OpenRouter non-streaming completion component."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from thoth.domain.envelopes import RuntimeMessage, RuntimeMessageRole
from thoth.domain.providers import ProviderExecutionError, ProviderRequest, ProviderResponse


class OpenRouterCompletionComponent:
    """Execute non-streaming chat completions against OpenRouter."""

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

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        payload: dict[str, Any] = {
            "model": request.model or self._default_model,
            "messages": _serialize_messages(request.messages),
        }
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens

        try:
            response_payload = self._post_json(payload)
        except ProviderExecutionError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ProviderExecutionError(
                code="provider.openrouter.request_failed",
                message=f"openrouter request failed: {exc}",
            ) from exc

        output_text = _extract_output_text(response_payload)
        usage = _extract_usage(response_payload)
        response_message = RuntimeMessage(role=RuntimeMessageRole.ASSISTANT, content=output_text)
        return ProviderResponse(
            request_id=request.request_id,
            output_text=output_text,
            messages=[response_message],
            usage=usage,
            metadata={
                "provider": "openrouter",
                "component": "completion",
                "model": str(response_payload.get("model", payload["model"])),
                "response_id": str(response_payload.get("id", "")),
            },
        )

    def _post_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = Request(
            url=self._endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=_build_headers(
                api_key=self._api_key,
                http_referer=self._http_referer,
                app_title=self._app_title,
            ),
            method="POST",
        )

        try:
            with self._opener(request, timeout=self._timeout_seconds) as response:
                raw_body = response.read().decode("utf-8")
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

        try:
            payload_obj = json.loads(raw_body)
        except json.JSONDecodeError as exc:
            raise ProviderExecutionError(
                code="provider.openrouter.invalid_response",
                message="openrouter returned invalid json",
            ) from exc

        if not isinstance(payload_obj, dict):
            raise ProviderExecutionError(
                code="provider.openrouter.invalid_response",
                message="openrouter response must be an object",
            )
        return payload_obj


def _serialize_messages(messages: list[RuntimeMessage]) -> list[dict[str, Any]]:
    serialized: list[dict[str, Any]] = []
    for message in messages:
        entry: dict[str, Any] = {
            "role": message.role.value,
            "content": message.content,
        }
        tool_call_id = message.metadata.get("tool_call_id")
        if (
            message.role is RuntimeMessageRole.TOOL
            and isinstance(tool_call_id, str)
            and tool_call_id
        ):
            entry["tool_call_id"] = tool_call_id
        serialized.append(entry)
    return serialized


def _build_headers(
    *,
    api_key: str,
    http_referer: str | None,
    app_title: str | None,
) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if http_referer:
        headers["HTTP-Referer"] = http_referer
    if app_title:
        headers["X-OpenRouter-Title"] = app_title
    return headers


def _extract_output_text(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ProviderExecutionError(
            code="provider.openrouter.invalid_response",
            message="openrouter response missing choices",
        )

    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise ProviderExecutionError(
            code="provider.openrouter.invalid_response",
            message="openrouter response choice must be an object",
        )

    message = first_choice.get("message")
    if not isinstance(message, dict):
        raise ProviderExecutionError(
            code="provider.openrouter.invalid_response",
            message="openrouter response missing message",
        )

    content = message.get("content")
    if isinstance(content, str):
        return content
    if content is None:
        return ""

    raise ProviderExecutionError(
        code="provider.openrouter.invalid_response",
        message="openrouter response message.content must be a string or null",
    )


def _extract_usage(payload: dict[str, Any]) -> dict[str, int]:
    usage_payload = payload.get("usage")
    if not isinstance(usage_payload, dict):
        return {}

    usage: dict[str, int] = {}
    prompt_tokens = usage_payload.get("prompt_tokens")
    completion_tokens = usage_payload.get("completion_tokens")
    total_tokens = usage_payload.get("total_tokens")

    if isinstance(prompt_tokens, int):
        usage["input_tokens"] = prompt_tokens
    if isinstance(completion_tokens, int):
        usage["output_tokens"] = completion_tokens
    if isinstance(total_tokens, int):
        usage["total_tokens"] = total_tokens
    return usage

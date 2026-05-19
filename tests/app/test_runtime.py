import json
from pathlib import Path

import pytest

from thoth.app.runtime import (
    _resolve_learning_provider_and_model,
    bootstrap_runtime,
    render_output,
)


@pytest.fixture(autouse=True)
def _disable_repo_dotenv(monkeypatch: object) -> None:
    # Keep tests deterministic even when repository root has a .env file.
    monkeypatch.setenv("THOTH_DOTENV_PATH", ".dotenv.missing")  # type: ignore[attr-defined]


def test_bootstrap_runtime_executes_with_explicit_session() -> None:
    runtime = bootstrap_runtime()

    output = runtime.execute(
        gateway="cli",
        message="hello",
        session_id="sess_1",
        request_id="req_123",
    )

    assert output.request_id == "req_123"
    assert output.status.value == "success"
    assert output.audit_ref == "session:sess_1:rev:1"
    assert output.messages[0].content == "[mock] echo: hello"


def test_render_output_is_json_serializable() -> None:
    runtime = bootstrap_runtime()
    output = runtime.execute(gateway="cli", message="hello", request_id="req_abc")

    serialized = render_output(output)
    payload = json.loads(serialized)

    assert payload["request_id"] == "req_abc"
    assert payload["status"] == "success"
    assert payload["messages"][0]["role"] == "assistant"


def test_bootstrap_runtime_uses_file_store_from_env(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.setenv("THOTH_SESSION_STORE", "file")  # type: ignore[attr-defined]
    monkeypatch.setenv("THOTH_SESSION_DIR", str(tmp_path))  # type: ignore[attr-defined]

    first_runtime = bootstrap_runtime()
    first_output = first_runtime.execute(
        gateway="cli",
        message="first",
        session_id="sess_file",
        request_id="req_file_1",
    )

    second_runtime = bootstrap_runtime()
    second_output = second_runtime.execute(
        gateway="cli",
        message="second",
        session_id="sess_file",
        request_id="req_file_2",
    )

    assert first_output.audit_ref == "session:sess_file:rev:1"
    assert second_output.audit_ref == "session:sess_file:rev:2"


def test_bootstrap_runtime_prefers_provider_from_env(monkeypatch: object) -> None:
    monkeypatch.setenv("THOTH_PREFERRED_PROVIDER", "mock")  # type: ignore[attr-defined]

    runtime = bootstrap_runtime()
    output = runtime.execute(
        gateway="cli",
        message="preferred",
        session_id="sess_pref",
        request_id="req_pref_1",
    )

    assert output.messages[0].content == "[mock] echo: preferred"


def test_bootstrap_runtime_accepts_llm_summarizer_strategy(monkeypatch: object) -> None:
    monkeypatch.setenv("THOTH_SESSION_SUMMARIZER", "llm")  # type: ignore[attr-defined]

    runtime = bootstrap_runtime()
    output = runtime.execute(
        gateway="cli",
        message="strategy",
        session_id="sess_strategy",
        request_id="req_strategy_1",
    )

    assert output.status.value == "success"


def test_learning_provider_and_model_use_explicit_overrides(monkeypatch: object) -> None:
    monkeypatch.setenv("THOTH_PREFERRED_PROVIDER", "mock")  # type: ignore[attr-defined]
    monkeypatch.setenv("THOTH_SESSION_SUMMARIZER_PROVIDER", "legacy_provider")  # type: ignore[attr-defined]
    monkeypatch.setenv("THOTH_SESSION_SUMMARIZER_MODEL", "legacy_model")  # type: ignore[attr-defined]
    monkeypatch.setenv("THOTH_LEARNING_PROVIDER", "learning_provider")  # type: ignore[attr-defined]
    monkeypatch.setenv("THOTH_LEARNING_MODEL", "learning_model")  # type: ignore[attr-defined]

    provider, model = _resolve_learning_provider_and_model()

    assert provider == "learning_provider"
    assert model == "learning_model"


def test_learning_provider_falls_back_to_main_provider(monkeypatch: object) -> None:
    monkeypatch.delenv("THOTH_LEARNING_PROVIDER", raising=False)  # type: ignore[attr-defined]
    monkeypatch.delenv("THOTH_SESSION_SUMMARIZER_PROVIDER", raising=False)  # type: ignore[attr-defined]
    monkeypatch.setenv("THOTH_PREFERRED_PROVIDER", "mock")  # type: ignore[attr-defined]

    provider, _ = _resolve_learning_provider_and_model()

    assert provider == "mock"


def test_learning_model_falls_back_to_none_when_not_defined(monkeypatch: object) -> None:
    monkeypatch.delenv("THOTH_LEARNING_MODEL", raising=False)  # type: ignore[attr-defined]
    monkeypatch.delenv("THOTH_SESSION_SUMMARIZER_MODEL", raising=False)  # type: ignore[attr-defined]

    _, model = _resolve_learning_provider_and_model()

    assert model is None


def test_bootstrap_runtime_fallbacks_to_mock_when_openrouter_is_unhealthy(
    monkeypatch: object,
) -> None:
    monkeypatch.setenv("THOTH_PREFERRED_PROVIDER", "openrouter")  # type: ignore[attr-defined]
    monkeypatch.setenv("THOTH_OPENROUTER_API_KEY", "")  # type: ignore[attr-defined]

    runtime = bootstrap_runtime()
    output = runtime.execute(
        gateway="cli",
        message="fallback",
        session_id="sess_fallback",
        request_id="req_fallback_1",
    )

    assert output.messages[0].content == "[mock] echo: fallback"


def test_bootstrap_runtime_emits_memory_updates_when_enabled(monkeypatch: object) -> None:
    monkeypatch.setenv("THOTH_MEMORY_ENABLED", "true")  # type: ignore[attr-defined]

    runtime = bootstrap_runtime()
    output = runtime.execute(
        gateway="cli",
        message="prefiro respostas em bullet points",
        session_id="sess_memory_enabled",
        request_id="req_memory_enabled_1",
    )

    assert output.status.value == "success"
    assert output.memory_updates


def test_runtime_loads_learning_across_sessions_from_global_store(
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    monkeypatch.setenv("THOTH_MEMORY_ENABLED", "true")  # type: ignore[attr-defined]
    monkeypatch.setenv("THOTH_LEARNING_STORE", "file")  # type: ignore[attr-defined]
    monkeypatch.setenv(
        "THOTH_LEARNING_STORE_PATH",
        str(tmp_path / "learning" / "memory_updates.json"),
    )  # type: ignore[attr-defined]

    runtime = bootstrap_runtime()
    runtime.execute(
        gateway="cli",
        message="prefiro respostas curtas",
        session_id="sess_global_1",
        request_id="req_global_1",
    )

    output = runtime.execute(
        gateway="cli",
        message="prefiro respostas curtas",
        session_id="sess_global_2",
        request_id="req_global_2",
    )

    assert output.memory_updates
    assert any("repeated_signal" in item["reason"] for item in output.memory_updates)


def test_bootstrap_runtime_loads_dotenv_from_cwd(tmp_path: Path, monkeypatch: object) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "THOTH_SESSION_STORE=file",
                "THOTH_SESSION_DIR=.sessions_from_dotenv",
                "",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)  # type: ignore[attr-defined]
    monkeypatch.setenv("THOTH_DOTENV_PATH", str(env_file))  # type: ignore[attr-defined]
    monkeypatch.delenv("THOTH_SESSION_STORE", raising=False)  # type: ignore[attr-defined]
    monkeypatch.delenv("THOTH_SESSION_DIR", raising=False)  # type: ignore[attr-defined]

    first_runtime = bootstrap_runtime()
    first_output = first_runtime.execute(
        gateway="cli",
        message="first",
        session_id="sess_dotenv",
        request_id="req_dotenv_1",
    )

    second_runtime = bootstrap_runtime()
    second_output = second_runtime.execute(
        gateway="cli",
        message="second",
        session_id="sess_dotenv",
        request_id="req_dotenv_2",
    )

    assert first_output.audit_ref == "session:sess_dotenv:rev:1"
    assert second_output.audit_ref == "session:sess_dotenv:rev:2"


def test_bootstrap_runtime_does_not_override_existing_env(
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "THOTH_SESSION_STORE=file",
                "THOTH_SESSION_DIR=.sessions_from_dotenv",
                "",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)  # type: ignore[attr-defined]
    monkeypatch.setenv("THOTH_DOTENV_PATH", str(env_file))  # type: ignore[attr-defined]
    monkeypatch.setenv("THOTH_SESSION_STORE", "inmemory")  # type: ignore[attr-defined]
    monkeypatch.delenv("THOTH_SESSION_DIR", raising=False)  # type: ignore[attr-defined]

    first_runtime = bootstrap_runtime()
    first_output = first_runtime.execute(
        gateway="cli",
        message="first",
        session_id="sess_dotenv_priority",
        request_id="req_dotenv_priority_1",
    )

    second_runtime = bootstrap_runtime()
    second_output = second_runtime.execute(
        gateway="cli",
        message="second",
        session_id="sess_dotenv_priority",
        request_id="req_dotenv_priority_2",
    )

    assert first_output.audit_ref == "session:sess_dotenv_priority:rev:1"
    assert second_output.audit_ref == "session:sess_dotenv_priority:rev:1"

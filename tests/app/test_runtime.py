import json
from pathlib import Path

from thoth.app.runtime import bootstrap_runtime, render_output


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

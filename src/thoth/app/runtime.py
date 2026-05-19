"""Runtime bootstrap and CLI gateway adapter."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from thoth.core import (
    FileSessionStore,
    HeuristicSessionSummarizer,
    InMemoryEventBus,
    InMemoryLearningStore,
    InMemorySessionStore,
    LearningReviewerConfig,
    LLMSessionSummarizer,
    LLMLearningReviewer,
    FileLearningStore,
    MemoryManager,
    MemoryManagerConfig,
    ProviderContextBuilder,
    ProviderContextConfig,
    ProviderLoader,
    ProviderRegistry,
    ProviderSelectionConfig,
    ProviderSelector,
    RuntimeOrchestrator,
    SessionCompactionConfig,
    SessionCompactor,
    SessionManager,
    SessionSummarizer,
)
from thoth.core.session_store import SessionStore
from thoth.domain import (
    RuntimeInputEnvelope,
    RuntimeMessage,
    RuntimeMessageRole,
    RuntimeOutputEnvelope,
)


@dataclass(slots=True)
class RuntimeApplication:
    """Bootstrapped runtime dependencies for processing requests."""

    orchestrator: RuntimeOrchestrator

    def execute(
        self,
        *,
        gateway: str,
        message: str,
        session_id: str | None = None,
        request_id: str | None = None,
    ) -> RuntimeOutputEnvelope:
        resolved_request_id = request_id or f"req_{uuid4().hex}"
        session_payload = {"session_id": session_id} if session_id else {}

        envelope = RuntimeInputEnvelope(
            request_id=resolved_request_id,
            gateway=gateway,
            session=session_payload,
            input=[RuntimeMessage(role=RuntimeMessageRole.USER, content=message)],
        )
        return self.orchestrator.handle(envelope)


def bootstrap_runtime() -> RuntimeApplication:
    """Create the default runtime composition for local execution."""

    _load_dotenv()

    session_store = _build_session_store()
    session_manager = SessionManager(session_store)
    event_bus = InMemoryEventBus()
    provider_registry = ProviderRegistry()
    provider_loader = ProviderLoader(provider_registry)
    provider_loader.load_from_paths(
        search_paths=[_default_providers_path()],
        context={"runtime": "thoth", "gateway": "cli"},
    )
    selector = ProviderSelector(provider_registry) if provider_registry.list() else None
    selection_config = ProviderSelectionConfig(
        preferred_provider=os.getenv("THOTH_PREFERRED_PROVIDER")
    )
    compaction_config = SessionCompactionConfig(
        active_window=_read_int_env("THOTH_SESSION_ACTIVE_WINDOW", 40),
        compaction_threshold=_read_int_env("THOTH_SESSION_COMPACTION_THRESHOLD", 20),
        max_summary_chars=_read_int_env("THOTH_SESSION_MAX_SUMMARY_CHARS", 1200),
        context_token_limit=_read_optional_int_env("THOTH_SESSION_CONTEXT_TOKEN_LIMIT"),
        compaction_token_threshold_ratio=_read_float_env(
            "THOTH_SESSION_COMPACTION_TOKEN_THRESHOLD_RATIO", 0.50
        ),
    )
    context_config = ProviderContextConfig(
        provider_context_limit=_read_int_env("THOTH_PROVIDER_CONTEXT_LIMIT", 40),
        max_summary_chars=_read_int_env("THOTH_SESSION_MAX_SUMMARY_CHARS", 1200),
    )
    orchestrator = RuntimeOrchestrator(
        session_manager=session_manager,
        event_bus=event_bus,
        provider_selector=selector,
        provider_selection=selection_config,
        session_compactor=SessionCompactor(
            config=compaction_config,
            summarizer=_build_session_summarizer(selector),
        ),
        context_builder=ProviderContextBuilder(config=context_config),
        memory_manager=MemoryManager(
            MemoryManagerConfig(
                enabled=_read_bool_env("THOTH_MEMORY_ENABLED", False),
                persist_threshold=_read_float_env("THOTH_MEMORY_PERSIST_THRESHOLD", 0.70),
                review_threshold=_read_float_env("THOTH_MEMORY_REVIEW_THRESHOLD", 0.50),
                max_updates=_read_int_env("THOTH_MEMORY_MAX_UPDATES", 200),
                max_candidates=_read_int_env("THOTH_MEMORY_MAX_CANDIDATES", 10),
                review_enabled=_read_bool_env("THOTH_LEARNING_REVIEW_ENABLED", False),
                max_review_suggestions=_read_int_env("THOTH_LEARNING_REVIEW_MAX_SUGGESTIONS", 3),
            ),
            learning_store=_build_learning_store(),
            reviewer=_build_learning_reviewer(selector),
        ),
    )
    return RuntimeApplication(orchestrator=orchestrator)


def _build_session_store() -> SessionStore:
    backend = os.getenv("THOTH_SESSION_STORE", "inmemory").strip().lower()
    if backend == "file":
        session_dir = os.getenv("THOTH_SESSION_DIR", ".thoth/sessions")
        return FileSessionStore(Path(session_dir))
    return InMemorySessionStore()


def _default_providers_path() -> Path:
    return Path(__file__).resolve().parents[1] / "providers"


def _build_learning_store() -> InMemoryLearningStore | FileLearningStore:
    backend = os.getenv("THOTH_LEARNING_STORE", "file").strip().lower()
    max_updates = _read_int_env("THOTH_LEARNING_STORE_MAX_UPDATES", 5000)
    if backend == "inmemory":
        return InMemoryLearningStore(max_updates=max_updates)

    path = os.getenv("THOTH_LEARNING_STORE_PATH", ".thoth/learning/memory_updates.json")
    return FileLearningStore(Path(path), max_updates=max_updates)


def _build_learning_reviewer(provider_selector: ProviderSelector | None) -> LLMLearningReviewer | None:
    if provider_selector is None:
        return None

    if not _read_bool_env("THOTH_LEARNING_REVIEW_ENABLED", False):
        return None

    preferred_provider, model = _resolve_learning_provider_and_model()
    return LLMLearningReviewer(
        provider_selector=provider_selector,
        provider_selection=ProviderSelectionConfig(preferred_provider=preferred_provider),
        model=model,
        config=LearningReviewerConfig(
            max_suggestions=_read_int_env("THOTH_LEARNING_REVIEW_MAX_SUGGESTIONS", 3)
        ),
    )


def _read_int_env(env_name: str, default: int) -> int:
    raw_value = os.getenv(env_name, "").strip()
    if not raw_value:
        return default

    try:
        parsed = int(raw_value)
    except ValueError:
        return default
    if parsed <= 0:
        return default
    return parsed


def _read_optional_int_env(env_name: str) -> int | None:
    raw_value = os.getenv(env_name, "").strip()
    if not raw_value:
        return None

    try:
        parsed = int(raw_value)
    except ValueError:
        return None
    if parsed <= 0:
        return None
    return parsed


def _read_float_env(env_name: str, default: float) -> float:
    raw_value = os.getenv(env_name, "").strip()
    if not raw_value:
        return default

    try:
        parsed = float(raw_value)
    except ValueError:
        return default
    if parsed <= 0:
        return default
    return parsed


def _read_bool_env(env_name: str, default: bool) -> bool:
    raw_value = os.getenv(env_name, "").strip().lower()
    if not raw_value:
        return default
    if raw_value in {"1", "true", "yes", "on"}:
        return True
    if raw_value in {"0", "false", "no", "off"}:
        return False
    return default


def _build_session_summarizer(provider_selector: ProviderSelector | None) -> SessionSummarizer:
    strategy = os.getenv("THOTH_SESSION_SUMMARIZER", "heuristic").strip().lower()
    if strategy == "llm":
        preferred_provider, model = _resolve_learning_provider_and_model()
        provider_selection = ProviderSelectionConfig(preferred_provider=preferred_provider)
        return LLMSessionSummarizer(
            provider_selector=provider_selector,
            provider_selection=provider_selection,
            model=model,
        )
    return HeuristicSessionSummarizer()


def _resolve_learning_provider_and_model() -> tuple[str | None, str | None]:
    learning_provider = os.getenv("THOTH_LEARNING_PROVIDER", "").strip() or None
    learning_model = os.getenv("THOTH_LEARNING_MODEL", "").strip() or None

    legacy_provider = os.getenv("THOTH_SESSION_SUMMARIZER_PROVIDER", "").strip() or None
    legacy_model = os.getenv("THOTH_SESSION_SUMMARIZER_MODEL", "").strip() or None

    main_provider = os.getenv("THOTH_PREFERRED_PROVIDER", "").strip() or None

    preferred_provider = learning_provider or legacy_provider or main_provider
    model = learning_model or legacy_model
    return preferred_provider, model


def _load_dotenv() -> None:
    """Load key/value pairs from a local .env file into process environment."""

    dotenv_path = Path(os.getenv("THOTH_DOTENV_PATH", ".env")).expanduser()
    if not dotenv_path.is_absolute():
        dotenv_path = Path.cwd() / dotenv_path

    if not dotenv_path.exists() or not dotenv_path.is_file():
        return

    for line in dotenv_path.read_text(encoding="utf-8").splitlines():
        parsed = _parse_dotenv_line(line)
        if parsed is None:
            continue

        key, value = parsed
        # Respect explicit environment variables already provided by the process.
        os.environ.setdefault(key, value)


def _parse_dotenv_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None

    if stripped.startswith("export "):
        stripped = stripped[len("export ") :].strip()

    if "=" not in stripped:
        return None

    key, raw_value = stripped.split("=", maxsplit=1)
    key = key.strip()
    if not key:
        return None

    value = _strip_inline_comment(raw_value.strip())
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1]

    return key, value


def _strip_inline_comment(value: str) -> str:
    """Strip inline comments only for unquoted dotenv values."""

    if not value:
        return value
    if value[0] in {'"', "'"}:
        return value

    comment_index = value.find(" #")
    if comment_index == -1:
        return value
    return value[:comment_index].rstrip()


def render_output(output: RuntimeOutputEnvelope) -> str:
    """Render canonical runtime output in a CLI-friendly JSON format."""

    payload = {
        "schema_version": output.schema_version,
        "request_id": output.request_id,
        "timestamp": output.timestamp.isoformat(),
        "status": output.status.value,
        "messages": [
            {
                "role": message.role.value,
                "content": message.content,
                "metadata": message.metadata,
            }
            for message in output.messages
        ],
        "actions": output.actions,
        "tool_results": output.tool_results,
        "artifacts": output.artifacts,
        "memory_updates": output.memory_updates,
        "policy_decisions": output.policy_decisions,
        "audit_ref": output.audit_ref,
    }
    return json.dumps(payload, ensure_ascii=True, indent=2)


def run(
    *,
    message: str = "hello from thoth",
    session_id: str | None = None,
) -> int:
    """Run a single CLI request through the canonical runtime flow."""

    app = bootstrap_runtime()
    output = app.execute(
        gateway="cli",
        message=message,
        session_id=session_id,
    )
    print(render_output(output))
    return 0

# Thoth

Runtime/harness for autonomous agents.

## Requirements
- Python 3.12+
- uv

## Setup
```bash
uv sync --dev
```

## Run
```bash
uv run thoth
```

## .env File (Automatic Loading)
At startup, the runtime tries to load a `.env` file from the current directory.

Rules:
- variables already defined in the environment are not overridden by `.env`.
- a custom path can be defined with `THOTH_DOTENV_PATH`.

Example:
```bash
cp .env.example .env
uv run thoth --message "hello"
```

## Use the OpenRouter Provider
The runtime automatically loads providers from manifests, including `mock` and `openrouter`.

To force OpenRouter in provider selection:
```bash
THOTH_PREFERRED_PROVIDER=openrouter \
THOTH_OPENROUTER_API_KEY=<your_key> \
THOTH_OPENROUTER_MODEL=openai/gpt-5.2 \
uv run thoth --message "hello"
```

Optional variables:
- `THOTH_OPENROUTER_BASE_URL` (default: `https://openrouter.ai/api/v1`)
- `THOTH_OPENROUTER_HTTP_REFERER`
- `THOTH_OPENROUTER_TITLE`
- `THOTH_OPENROUTER_TIMEOUT_SECONDS` (default: `60`)

## Persistent Session (Optional)
By default, the runtime uses an in-memory store (session resets every process run).

To persist sessions in JSON files:
```bash
THOTH_SESSION_STORE=file THOTH_SESSION_DIR=.thoth/sessions uv run thoth --message "ping" --session-id "sess_cli"
```

## Session Summarizer Strategy
Session compaction supports a pluggable summarizer strategy.

Environment variable:
- `THOTH_SESSION_SUMMARIZER=heuristic|llm`

Optional LLM strategy variables:
- `THOTH_LEARNING_PROVIDER` (preferred provider id for learning/summarization)
- `THOTH_LEARNING_MODEL` (model override used only by learning/summarization)

Legacy-compatible variables (still supported):
- `THOTH_SESSION_SUMMARIZER_PROVIDER`
- `THOTH_SESSION_SUMMARIZER_MODEL`

Notes:
- `heuristic` is the default strategy.
- `llm` tries to summarize through the configured provider/model and safely falls back
	to heuristic behavior if provider selection/execution fails or returns invalid JSON.
- Provider fallback order for learning: `THOTH_LEARNING_PROVIDER` ->
	`THOTH_SESSION_SUMMARIZER_PROVIDER` -> `THOTH_PREFERRED_PROVIDER`.
- Model fallback order for learning: `THOTH_LEARNING_MODEL` ->
	`THOTH_SESSION_SUMMARIZER_MODEL` -> provider default model (same behavior as main flow).

## Learning Memory Pipeline (Layer 4)
Learning memory is disabled by default to preserve current runtime behavior.

Enable and tune with:
- `THOTH_MEMORY_ENABLED=true|false` (default: `false`)
- `THOTH_MEMORY_PERSIST_THRESHOLD` (default: `0.70`)
- `THOTH_MEMORY_REVIEW_THRESHOLD` (default: `0.50`)
- `THOTH_MEMORY_MAX_UPDATES` (default: `200`)
- `THOTH_MEMORY_MAX_CANDIDATES` (default: `10`)

Global learning store (cross-session):
- `THOTH_LEARNING_STORE=file|inmemory` (default: `file`)
- `THOTH_LEARNING_STORE_PATH` (default: `.thoth/learning/memory_updates.json`)
- `THOTH_LEARNING_STORE_MAX_UPDATES` (default: `5000`)

LLM learning review (Hermes-style best-effort):
- `THOTH_LEARNING_REVIEW_ENABLED=true|false` (default: `false`)
- `THOTH_LEARNING_REVIEW_MAX_SUGGESTIONS` (default: `3`)

Provider/model used by learning review follow the same fallback chain:
- provider: `THOTH_LEARNING_PROVIDER` -> `THOTH_SESSION_SUMMARIZER_PROVIDER` -> `THOTH_PREFERRED_PROVIDER`
- model: `THOTH_LEARNING_MODEL` -> `THOTH_SESSION_SUMMARIZER_MODEL` -> provider default

When enabled, the runtime appends learning decisions to `memory_updates` in the output envelope
and persists history in session state.

Additionally, persisted `decision=persist` updates are written to the global learning store,
so future sessions can reuse long-lived learning signals.

## Tests
```bash
uv run pytest
```

## Lint
```bash
uv run ruff check .
```

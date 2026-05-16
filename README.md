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

## Tests
```bash
uv run pytest
```

## Lint
```bash
uv run ruff check .
```

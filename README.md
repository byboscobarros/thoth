# Thoth

Runtime/harness para agentes autonomos.

## Requisitos
- Python 3.12+
- uv

## Setup
```bash
uv sync --dev
```

## Executar
```bash
uv run thoth
```

## Arquivo .env (carregamento automatico)
No startup, o runtime tenta carregar um arquivo `.env` no diretorio atual.

Regras:
- variaveis ja definidas no ambiente nao sao sobrescritas pelo `.env`.
- caminho customizado pode ser definido com `THOTH_DOTENV_PATH`.

Exemplo:
```bash
cp .env.example .env
uv run thoth --message "ola"
```

## Usar provider OpenRouter
O runtime carrega providers por manifesto automaticamente, incluindo `mock` e `openrouter`.

Para forcar o uso do OpenRouter na selecao de provider:
```bash
THOTH_PREFERRED_PROVIDER=openrouter \
THOTH_OPENROUTER_API_KEY=<sua_chave> \
THOTH_OPENROUTER_MODEL=openai/gpt-5.2 \
uv run thoth --message "ola"
```

Variaveis opcionais:
- `THOTH_OPENROUTER_BASE_URL` (default: `https://openrouter.ai/api/v1`)
- `THOTH_OPENROUTER_HTTP_REFERER`
- `THOTH_OPENROUTER_TITLE`
- `THOTH_OPENROUTER_TIMEOUT_SECONDS` (default: `60`)

## Sessao Persistente (Opcional)
Por padrao, o runtime usa store em memoria (reinicia a sessao a cada processo).

Para persistir sessao em arquivos JSON:
```bash
THOTH_SESSION_STORE=file THOTH_SESSION_DIR=.thoth/sessions uv run thoth --message "ping" --session-id "sess_cli"
```

## Testes
```bash
uv run pytest
```

## Lint
```bash
uv run ruff check .
```

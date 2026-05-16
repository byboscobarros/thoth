# Thoth - Guia de Criacao de Provider Componentizado

## Objetivo
Este documento explica como criar um provider componentizado no Thoth seguindo os contratos canônicos e o fluxo manifest-driven da camada atual.

Ao final, voce tera:
- um provider com contrato valido.
- um `manifest.json` carregavel pelo loader.
- componentes internos separados por capacidade.
- testes de contrato e comportamento.

## 1. Conceitos Base
No Thoth, um provider e dividido em:

1. Contrato canônico
- Interface `Provider` (metodos obrigatorios).
- Tipos `ProviderRequest`, `ProviderResponse`, `ProviderChunk`, `ProviderHealth`.
- Erros padronizados (`ProviderConfigurationError`, `ProviderExecutionError`).

2. Manifesto declarativo
- Arquivo `manifest.json` com metadados, capabilities e entrypoint.

3. Componentes de capacidade
- Modulos internos para responsabilidades especificas (completion, streaming, etc).

4. Integracao no runtime
- Loader descobre manifesto.
- Registry registra provider.
- Selector escolhe provider por capability.
- Orchestrator executa via abstracao.

Referencias no projeto:
- `src/thoth/domain/providers.py`
- `src/thoth/domain/provider_manifest.py`
- `src/thoth/core/provider_loader.py`
- `src/thoth/core/provider_registry.py`
- `src/thoth/core/provider_selector.py`
- `src/thoth/providers/mock/`

## 2. Estrutura de Pastas Recomendada
Exemplo para um provider chamado `acme`:

```text
src/thoth/providers/acme/
  manifest.json
  provider.py
  components/
    completion.py
    streaming.py
  __init__.py
```

## 3. Passo a Passo

### Passo 1 - Criar o manifest.json
Crie `src/thoth/providers/acme/manifest.json`:

```json
{
  "schema_version": "v1",
  "type": "provider",
  "name": "acme",
  "version": "0.1.0",
  "entrypoint": "thoth.providers.acme.provider:AcmeProvider",
  "capabilities": {
    "chat_completion": true,
    "streaming": true,
    "tool_calling": false
  },
  "compatibility": {
    "runtime": ">=0.1.0"
  },
  "metadata": {
    "description": "Acme provider"
  }
}
```

Regras importantes:
- `schema_version` deve ser `v1`.
- `type` deve ser `provider`.
- `entrypoint` deve seguir `<modulo>:<classe>`.
- `capabilities` deve ser objeto nao vazio com booleanos.

### Passo 2 - Criar componentes internos
Exemplo `completion.py`:

```python
from thoth.domain.envelopes import RuntimeMessage, RuntimeMessageRole
from thoth.domain.providers import ProviderRequest, ProviderResponse


class AcmeCompletionComponent:
    def complete(self, request: ProviderRequest) -> ProviderResponse:
        text = "[acme] resposta de exemplo"
        return ProviderResponse(
            request_id=request.request_id,
            output_text=text,
            messages=[RuntimeMessage(role=RuntimeMessageRole.ASSISTANT, content=text)],
            usage={"input_tokens": len(request.messages), "output_tokens": 1},
        )
```

Exemplo `streaming.py`:

```python
from thoth.domain.providers import ProviderChunk, ProviderRequest


class AcmeStreamingComponent:
    def stream(self, request: ProviderRequest) -> list[ProviderChunk]:
        return [
            ProviderChunk(request_id=request.request_id, index=0, content_delta="[acme] "),
            ProviderChunk(request_id=request.request_id, index=1, content_delta="done", done=True),
        ]
```

### Passo 3 - Implementar a classe principal do provider
Exemplo `provider.py`:

```python
from typing import Any

from thoth.domain.providers import (
    Provider,
    ProviderChunk,
    ProviderConfigurationError,
    ProviderHealth,
    ProviderRequest,
    ProviderResponse,
)
from thoth.providers.acme.components.completion import AcmeCompletionComponent
from thoth.providers.acme.components.streaming import AcmeStreamingComponent


class AcmeProvider(Provider):
    def __init__(self) -> None:
        self._initialized = False
        self._completion = AcmeCompletionComponent()
        self._streaming = AcmeStreamingComponent()

    def initialize(self, context: dict[str, Any]) -> None:
        _ = context
        self._initialized = True

    def execute(self, request: ProviderRequest) -> ProviderResponse:
        self._ensure_initialized()
        return self._completion.complete(request)

    def stream(self, request: ProviderRequest) -> list[ProviderChunk]:
        self._ensure_initialized()
        return self._streaming.stream(request)

    def shutdown(self) -> None:
        self._initialized = False

    def healthcheck(self) -> ProviderHealth:
        return ProviderHealth(ok=self._initialized, details="ready" if self._initialized else "not initialized")

    def _ensure_initialized(self) -> None:
        if not self._initialized:
            raise ProviderConfigurationError(
                code="provider.acme.not_initialized",
                message="acme provider must be initialized before execution",
            )
```

## 4. Carregar o Provider no Runtime
No estado atual, o runtime carrega providers do diretorio `src/thoth/providers`.

Se o `manifest.json` estiver valido e o `entrypoint` correto, o loader tenta:
1. descobrir manifesto.
2. validar schema.
3. importar classe.
4. instanciar provider.
5. chamar `initialize(context)`.
6. registrar no `ProviderRegistry`.

## 5. Como Testar

### Testes unitarios do provider
Crie testes semelhantes aos do mock em:
- `tests/providers/test_mock_provider.py`

Pontos minimos:
1. manifesto valido.
2. `execute` retorna `ProviderResponse` canônico.
3. `stream` retorna `ProviderChunk` canônico.
4. erro quando executar sem `initialize`.

### Teste de loader
Garanta que seu provider aparece no report do loader.

Comando util:
```bash
uv run pytest tests/core/test_provider_loader.py tests/providers -q
```

### Teste de selecao
Se capability `chat_completion=true`, ele deve ser candidato no selector.

Comando util:
```bash
uv run pytest tests/core/test_provider_selector.py -q
```

## 6. Boas Praticas
1. `provider.py` deve ser fino
- Apenas coordenar componentes e contrato.

2. Componentes pequenos e testaveis
- Evitar logica gigante em um unico arquivo.

3. Erros padronizados
- Nunca vazar excecao crua de SDK para o core.

4. Healthcheck confiavel
- Deve refletir capacidade real de atender requests.

5. Capabilities honestas no manifesto
- Nao declarar `streaming=true` se nao implementar.

## 7. Checklist de Pronto
1. `manifest.json` valido no schema v1.
2. Provider implementa todos os metodos obrigatorios.
3. Completion e streaming separados em componentes.
4. Testes de provider passando.
5. Loader consegue descobrir e registrar o provider.
6. Selector consegue escolher o provider pela capability esperada.

## 8. Exemplo de Referencia Atual
Use o provider mock como template oficial:
- `src/thoth/providers/mock/manifest.json`
- `src/thoth/providers/mock/provider.py`
- `src/thoth/providers/mock/components/completion.py`
- `src/thoth/providers/mock/components/streaming.py`
- `tests/providers/test_mock_provider.py`

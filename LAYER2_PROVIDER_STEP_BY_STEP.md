# Thoth - Camada 2 (Componentizacao de Providers)

## Objetivo
Implementar a camada de providers componentizados para desacoplar o core do runtime de SDKs/LLMs especificos e habilitar evolucao modular por manifest.

Resultado esperado:
- runtime chama providers por contrato canônico.
- providers sao carregaveis por manifesto e capacidades declaradas.
- trocar de provider nao exige alterar o core.
- existe provider local/mock para desenvolvimento e testes.

## Escopo da Camada 2
1. Contrato canônico de provider.
2. Modelos de request/response de provider.
3. Componentes de capacidade (completion/stream/tool-calling).
4. Registry + loader por manifest.
5. Seletor de provider por capacidade.
6. Integracao do orquestrador com provider abstraido.
7. Suite de testes de contrato e fluxo.

## Estrutura de pastas sugerida nesta etapa
- src/thoth/domain/providers.py
- src/thoth/core/provider_registry.py
- src/thoth/core/provider_loader.py
- src/thoth/core/provider_selector.py
- src/thoth/core/provider_runtime.py
- src/thoth/providers/mock/manifest.json
- src/thoth/providers/mock/provider.py
- src/thoth/providers/mock/components/completion.py
- src/thoth/providers/mock/components/streaming.py
- tests/domain/test_providers_contract.py
- tests/core/test_provider_registry.py
- tests/core/test_provider_loader.py
- tests/core/test_provider_selector.py
- tests/core/test_provider_runtime.py

## Passo a passo

### Passo 1 - Definir contrato canônico de provider
Tarefas:
1. Criar interface/base para provider com metodos obrigatorios:
   - initialize(context)
   - execute(request)
   - stream(request)
   - shutdown()
   - healthcheck()
2. Definir modelos canônicos:
   - ProviderRequest
   - ProviderResponse
   - ProviderChunk (stream)
3. Definir excecoes padronizadas:
   - ProviderError
   - ProviderConfigurationError
   - ProviderExecutionError

Decisoes:
- contrato fixo no dominio.
- erro padronizado para evitar vazamento de excecoes de SDK.

Criterio de pronto:
- contrato importavel e testado em unidade.

### Passo 2 - Definir manifesto de provider
Tarefas:
1. Criar schema inicial de manifesto (v1) para providers.
2. Campos minimos:
   - type=provider
   - name
   - version
   - entrypoint
   - capabilities
   - compatibility
3. Validar manifesto no load-time.

Decisoes:
- sem carregar provider sem manifesto valido.
- schema_version explicito e versionado.

Criterio de pronto:
- manifestos invalidos sao bloqueados com erro claro.

### Passo 3 - Implementar Provider Registry
Tarefas:
1. Criar estrutura em memoria para registrar providers carregados.
2. Indexar por:
   - provider_id/name
   - capabilities
   - status de healthcheck
3. Expor operacoes:
   - register
   - get
   - list
   - list_by_capability

Decisoes:
- registry sem dependencia de IO direto.
- foco em lookup rapido para o orquestrador.

Criterio de pronto:
- providers registraveis e recuperaveis por capacidade.

### Passo 4 - Implementar Provider Loader (manifest-driven)
Tarefas:
1. Descobrir manifestos em diretorios configurados.
2. Validar schema/compatibilidade.
3. Importar entrypoint dinamicamente.
4. Instanciar provider e chamar initialize.
5. Registrar no Provider Registry.

Decisoes:
- falha de um provider nao derruba o runtime inteiro.
- erros sao auditaveis e explicitos.

Criterio de pronto:
- loader sobe providers validos e ignora invalidos com log/erro controlado.

### Passo 5 - Criar provider mock componentizado
Tarefas:
1. Criar provider mock com manifesto proprio.
2. Implementar componentes internos:
   - completion component
   - streaming component
3. Retornar respostas deterministicas para testes.

Decisoes:
- provider mock e referencia de contrato para novos providers.
- usado como fallback default no ambiente local.

Criterio de pronto:
- testes de contrato passam com provider mock.

### Passo 6 - Implementar Provider Selector
Tarefas:
1. Selecionar provider por capacidade requerida.
2. Aplicar prioridade por config (ex: preferred_provider).
3. Fallback para proximo provider compativel se indisponivel.

Decisoes:
- selecao deterministica e explicavel.
- sem if hardcoded por nome de provider no core.

Criterio de pronto:
- selector escolhe provider correto e suporta fallback.

### Passo 7 - Integrar provider no orquestrador
Tarefas:
1. Substituir resposta fixa por chamada ao provider selecionado.
2. Mapear RuntimeInputEnvelope -> ProviderRequest.
3. Mapear ProviderResponse -> RuntimeOutputEnvelope.
4. Preservar eventos e persistencia de sessao ja existentes.

Decisoes:
- integracao sem quebrar contratos da Camada 1.
- orquestrador depende de abstracao, nao de SDK especifico.

Criterio de pronto:
- CLI retorna resposta vinda do provider mock via pipeline completo.

### Passo 8 - Cobertura de testes da camada
Tarefas:
1. Testes de contrato (provider base + mock).
2. Testes de loader com manifestos validos/invalidos.
3. Testes de selector com capacidades e fallback.
4. Teste ponta a ponta do orquestrador com provider mock.

Criterio de pronto:
- testes verdes cobrindo caminho feliz e falhas de configuracao.

### Passo 9 - Preparar primeiro provider real
Tarefas:
1. Criar adaptador OpenAI-compatible (ou similar) seguindo contrato.
2. Ler credenciais por ambiente.
3. Implementar healthcheck de conectividade/autenticacao.
4. Registrar no loader por manifesto.

Decisoes:
- provider real entra sem alterar API do core.
- mock continua como fallback para dev/test.

Criterio de pronto:
- runtime alterna entre mock e real por configuracao.

### Passo 10 - Definir pronto para seguir para Camada 3
Checklist:
1. Contrato de provider estavel e testado.
2. Manifesto de provider validado no load-time.
3. Registry e loader funcionais.
4. Selector por capacidade com fallback.
5. Orquestrador integrado ao provider abstrato.
6. Provider mock operando no fluxo CLI.
7. Testes verdes.

Se tudo acima estiver verde, iniciar Camada 3:
- memoria/aprendizagem (resumo de sessao + retrieval + consolidacao).

Status atual (2026-05-13):
1. Concluido: Passo 1 (contrato canônico de provider).
2. Concluido: Passo 2 (manifesto v1 + validacao load-time).
3. Concluido: Passo 3 (Provider Registry).
4. Concluido: Passo 4 (Provider Loader manifest-driven).
5. Concluido: Passo 5 (provider mock componentizado).
6. Concluido: Passo 6 (Provider Selector com preferencia e fallback).
7. Concluido: Passo 7 (integracao provider no orquestrador).
8. Concluido: Passo 8 (cobertura de testes da camada).
9. Concluido: Passo 9 (provider real OpenRouter implementado e integrado).

Decisao:
- Layer 2 concluida (mock + provider real + fallback).
- Proximo incremento: Layer 3 (memoria/aprendizagem e compactacao de sessao).

## Ordem de implementacao recomendada (curta)
1. domain/providers.py
2. provider_registry.py
3. provider_loader.py
4. provider mock
5. provider_selector.py
6. integracao no orchestrator
7. testes
8. provider real

## Comandos operacionais
- uv sync --dev
- uv run pytest
- uv run ruff check .
- uv run mypy src

## Riscos e mitigacoes
1. Risco: acoplamento do orquestrador ao provider concreto.
Mitigacao: mapear sempre via ProviderRequest/ProviderResponse.

2. Risco: plugins quebrando runtime no load.
Mitigacao: isolamento de erro por provider e validacao antecipada de manifesto.

3. Risco: selecao inconsistente de provider.
Mitigacao: regras deterministicas + testes de fallback.

4. Risco: provider real dificultar testes.
Mitigacao: manter mock oficial como provider de referencia.

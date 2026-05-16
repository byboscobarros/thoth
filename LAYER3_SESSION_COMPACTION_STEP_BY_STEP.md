# Thoth - Camada 3 (Compactacao e Resumo de Sessao)

## Objetivo
Implementar compactacao de sessao para manter contexto util em conversas longas, reduzindo custo de tokens e preservando continuidade semantica.

Resultado esperado:
- sessoes longas nao degradam qualidade por excesso de historico bruto.
- provider recebe contexto enxuto: resumo + janela ativa recente.
- estado de sessao continua auditavel e versionado.

## Escopo da Camada 3
1. Modelo de resumo e metadados de compactacao.
2. Compactor de sessao (heuristico inicial).
3. Rehidratacao de contexto no orquestrador.
4. Configuracao por ambiente para limites de contexto.
5. Testes de compactacao e regressao de comportamento.

## Estrutura de pastas sugerida
- src/thoth/domain/session_compaction.py
- src/thoth/core/session_compactor.py
- src/thoth/core/context_builder.py
- tests/domain/test_session_compaction.py
- tests/core/test_session_compactor.py
- tests/core/test_orchestrator_compaction.py

## Passo a passo

### Passo 1 - Definir contrato de compactacao no dominio
Tarefas:
1. Criar modelo `SessionSummary`.
2. Criar modelo `CompactionMeta`.
3. Definir campos na sessao:
   - `data.session_summary`
   - `data.compaction_meta`

Proposta de estrutura minima:
- `session_summary.version`
- `session_summary.short`
- `session_summary.structured`
  - `facts`
  - `goals`
  - `decisions`
  - `open_tasks`
- `compaction_meta.total_messages_seen`
- `compaction_meta.total_messages_compacted`
- `compaction_meta.last_compaction_at`
- `compaction_meta.last_compacted_request_id`

Criterio de pronto:
- modelos importaveis e validados em testes de dominio.

### Passo 2 - Definir politicas de janela e gatilho
Tarefas:
1. Definir `active_window` (mensagens brutas mantidas).
2. Definir `compaction_threshold` (novas mensagens para acionar compactacao).
3. Definir `provider_context_limit` final.

Valores iniciais recomendados:
- active_window = 40
- compaction_threshold = 20
- provider_context_limit = 40

Criterio de pronto:
- parametros centralizados e configuraveis por env.

### Passo 3 - Implementar SessionCompactor (heuristico)
Tarefas:
1. Selecionar bloco antigo fora da janela ativa.
2. Extrair sinal util (heuristica inicial):
   - perguntas recorrentes
   - preferencias declaradas
   - tarefas pendentes
   - decisoes tomadas
3. Gerar `session_summary.short` e atualizar `structured`.
4. Truncar `message_history` para janela ativa.
5. Atualizar `compaction_meta`.

Decisoes:
- primeira versao sem LLM, deterministicamente testavel.
- preparar interface para sumarizador LLM no futuro.

Criterio de pronto:
- historico bruto reduz apos gatilho e resumo persistido na sessao.

### Passo 4 - Integrar compactacao no ciclo do orquestrador
Tarefas:
1. Após persistencia da nova interacao, verificar gatilho.
2. Se gatilho ativo, chamar compactor.
3. Persistir estado compactado via SessionManager.
4. Emitir evento `session.compacted`.

Criterio de pronto:
- compactacao acontecendo automaticamente sem quebrar o fluxo atual.

### Passo 5 - Implementar rehidratacao de contexto para provider
Tarefas:
1. Criar `context_builder` no core.
2. Montar contexto do provider com:
   - resumo curto (`session_summary.short`)
   - itens estruturados relevantes
   - ultimas N mensagens da janela ativa
3. Garantir ordem e limite de contexto.

Regra:
- provider nao recebe historico inteiro quando houver resumo valido.

Criterio de pronto:
- provider recebe contexto compacto e coerente em sessoes longas.

### Passo 6 - Configuracao por ambiente
Tarefas:
1. Adicionar variaveis de ambiente:
   - `THOTH_SESSION_ACTIVE_WINDOW`
   - `THOTH_SESSION_COMPACTION_THRESHOLD`
   - `THOTH_PROVIDER_CONTEXT_LIMIT`
   - `THOTH_SESSION_MAX_SUMMARY_CHARS`
2. Aplicar defaults seguros quando valores forem invalidos.

Criterio de pronto:
- runtime aceita tuning sem alteracao de codigo.

### Passo 7 - Cobertura de testes
Tarefas:
1. Testes de dominio para modelos de resumo/meta.
2. Testes do compactor:
   - aciona no limiar
   - nao aciona abaixo do limiar
   - atualiza metadados corretamente
3. Testes do orquestrador:
   - contexto enviado ao provider contem resumo + janela ativa
   - regressao: sem perder comportamento em sessoes curtas

Criterio de pronto:
- testes verdes e deterministas.

### Passo 8 - Observabilidade e auditoria
Tarefas:
1. Registrar evento `session.compacted` com metadados:
   - session_id
   - mensagens compactadas
   - tamanho antes/depois
2. Incluir referencia de compactacao em trilha de auditoria.

Criterio de pronto:
- operacao de compactacao rastreavel ponta a ponta.

### Passo 9 - Evolucao para sumarizador LLM (futuro)
Tarefas:
1. Criar interface `SessionSummarizer` plugavel.
2. Implementar:
   - `HeuristicSummarizer` (default)
   - `LLMSummarizer` (opcional)
3. Selecao por config:
   - `THOTH_SESSION_SUMMARIZER=heuristic|llm`

Criterio de pronto:
- trocar sumarizador sem alterar orquestrador.

### Passo 10 - Definir pronto para Camada 4
Checklist:
1. Compactacao automatica funcional.
2. Resumo persistido e reutilizado.
3. Contexto do provider limitado e coerente.
4. Metadados de compactacao auditaveis.
5. Testes verdes.

Se tudo acima estiver verde, iniciar Camada 4:
- aprendizagem incremental (capture -> score -> redact -> persist).

## Ordem recomendada (curta)
1. domain/session_compaction.py
2. core/session_compactor.py
3. core/context_builder.py
4. integracao no orchestrator
5. env config
6. testes
7. observabilidade

## Comandos operacionais
- uv sync --dev
- uv run pytest
- uv run ruff check .
- uv run mypy src

## Riscos e mitigacoes
1. Risco: resumo perder informacao critica.
Mitigacao: manter janela ativa + resumo estruturado + testes de regressao.

2. Risco: compactacao agressiva demais.
Mitigacao: thresholds configuraveis e defaults conservadores.

3. Risco: comportamento instavel com sumarizador LLM.
Mitigacao: default heuristico deterministico e fallback automatico.

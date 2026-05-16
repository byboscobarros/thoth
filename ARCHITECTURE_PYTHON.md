# Thoth Architecture (Python)

## 1. Objetivo
Este documento define a arquitetura alvo do Thoth em Python, baseada no manifesto do projeto.

Diretrizes centrais:
- modularidade total por plugins e contratos.
- runtime com envelopes canonicos de entrada e saida.
- guardrails elasticos e auditaveis.
- execucao com sandbox por padrao conforme risco.
- memoria e aprendizagem continua com governanca.

## 2. Estilo Arquitetural
Combinacao recomendada:
- Hexagonal architecture (ports and adapters).
- Event-driven internamente para observabilidade e aprendizagem.
- Plugin-first para extensibilidade sem alterar o core.

Principio operacional:
- core pequeno e estavel.
- tudo que for variavel vira plugin configurado por manifest.json.

## 3. Componentes Principais

### 3.1 Runtime Core
Responsavel por:
- ciclo de vida do runtime.
- roteamento de requests.
- coordenacao entre policy, memoria, sandbox e execucao.
- orquestracao de eventos e montagem da resposta canonica.

### 3.2 Session Manager (fonte de verdade da sessao)
Responsavel por:
- criar, recuperar, bloquear e finalizar sessoes.
- aplicar versionamento de estado (snapshot + revision).
- checkpoints e resume de execucao.
- controle de concorrencia por session_id.

Regra:
- estado canonico da sessao fica no runtime (Session Manager), nunca no gateway.

### 3.3 Session Store
Responsavel por:
- persistir estado operacional da sessao.
- guardar snapshots, metadata e TTL.
- suportar recovery apos falhas.

Backend inicial sugerido:
- Arquivos json

### 3.4 Plugin Registry e Plugin Loader
Responsavel por:
- discovery de plugins.
- validacao de manifest.json por schema versionado.
- validacao de contrato obrigatorio por tipo.
- healthcheck no carregamento.

Tipos de plugin:
- provider
- gateway
- tool
- skill
- mcp
- sandbox driver
- memory backend

### 3.5 Contract Kit (SDK + Schemas)
Responsavel por:
- definir interfaces Python obrigatorias.
- padronizar models de entrada/saida.
- oferecer testes de conformidade para plugins.
- suportar migracao entre versoes de contrato.

### 3.6 Gateway Adapter Layer
Responsavel por:
- traduzir payload externo para RuntimeInputEnvelope.
- traduzir RuntimeOutputEnvelope para canal de destino.
- manter idempotencia e correlacao de request_id.

Regra:
- gateway nunca chama provider diretamente.

### 3.7 Policy Engine (guardrail elastico)
Responsavel por:
- avaliar politicas em camadas: global/workspace/session/agent/tool.
- decidir allow, deny, require_approval, redact, sandbox_redirect.
- registrar decisao com racional para auditoria.

Modos:
- permissive
- balanced
- strict
- air-gapped

### 3.8 Sandbox Manager e Catalog
Responsavel por:
- selecionar backend de execucao (container, microvm, vm, native).
- aplicar limites de recursos e egress.
- provisionar ambiente isolado por tarefa.

Catalogo por sandbox deve declarar:
- isolamento, custo, latencia, limites, compliance tags.

### 3.9 Tool/Skill Execution Engine
Responsavel por:
- executar tools e skills com timeout/retry/cancelamento.
- enviar execucao para sandbox quando policy exigir.
- normalizar resultados, erros e artifacts.

### 3.10 Memory and Learning System
Responsavel por:
- gerenciar camadas de memoria: ephemeral, working, long-term, org-knowledge.
- aplicar pipeline capture -> score -> redact -> persist.
- retrieval hibrido para enriquecer contexto da sessao.
- registrar memory_updates no envelope de saida.

### 3.11 Event Bus
Responsavel por:
- publicar eventos canonicos do runtime.
- desacoplar observabilidade, auditoria, analytics e aprendizagem.

Eventos base:
- request.received
- policy.evaluated
- tool.started
- tool.completed
- tool.failed
- memory.updated
- response.emitted

### 3.12 Observability and Audit
Responsavel por:
- logs estruturados por trace_id/request_id/session_id.
- metricas de latencia, erro e custo.
- trilha de auditoria de decisoes e mudancas de estado.

## 4. Contratos Canonicos de I/O

### 4.1 RuntimeInputEnvelope (minimo)
- schema_version
- request_id
- timestamp
- gateway
- actor
- session
- context
- input
- attachments
- policy_hints

### 4.2 RuntimeOutputEnvelope (minimo)
- schema_version
- request_id
- timestamp
- status
- messages
- actions
- tool_results
- artifacts
- memory_updates
- policy_decisions
- audit_ref

Regras:
- input de qualquer gateway entra no mesmo envelope.
- output do runtime sai no mesmo envelope.
- adaptacao de canal e responsabilidade do gateway adapter.

## 5. Fluxo Canonico de Execucao
1. Gateway recebe mensagem externa e monta RuntimeInputEnvelope.
2. Runtime valida envelope e schema_version.
3. Session Manager cria/recupera estado da sessao.
4. Policy Engine avalia regras iniciais.
5. Orchestrator consulta memoria contextual.
6. Orchestrator planeja acoes e seleciona provider/tools/skills.
7. Sandbox Manager decide ambiente de execucao por policy/risco.
8. Execution Engine executa e publica eventos.
9. Memory System avalia e persiste aprendizagem autorizada.
10. Session Manager persiste novo snapshot de estado.
11. Runtime gera RuntimeOutputEnvelope.
12. Gateway adapter renderiza resposta no canal final.

## 6. Estrutura de Pastas Sugerida (Python)
```text
thoth/
  pyproject.toml
  README.md
  src/thoth/
    app/
      bootstrap.py
      runtime.py
    domain/
      envelopes.py
      session.py
      events.py
      policies.py
      contracts/
        provider.py
        gateway.py
        tool.py
        skill.py
        mcp.py
        sandbox.py
        memory.py
    core/
      orchestrator.py
      session_manager.py
      policy_engine.py
      execution_engine.py
      sandbox_manager.py
      memory_manager.py
      event_bus.py
      audit.py
    plugins/
      registry.py
      loader.py
      validator.py
    adapters/
      gateways/
        cli/
        slack/
        whatsapp/
      sandboxes/
        docker/
        firecracker/
      memory/
        postgres/
        vector/
    infra/
      db/
      queue/
      telemetry/
  schemas/
    manifest.schema.json
    envelope.input.schema.json
    envelope.output.schema.json
  docs/
    MANIFESTO.md
    ARCHITECTURE_PYTHON.md
```

## 7. Padrao de Plugin
Cada plugin deve conter:
- manifest.json com type, version, capabilities, permissions, compatibility.
- implementacao Python do contrato obrigatorio.
- healthcheck.
- testes de conformidade.

Contrato minimo de provider:
- initialize(context)
- execute(request)
- stream(request) quando aplicavel
- shutdown()
- healthcheck()

## 8. Persistencia Recomendada
1. PostgreSQL
- session store, auditoria, configuracao e metadata.

2. Vector store (plugin)
- memoria semantica para retrieval.

3. Object storage (opcional)
- artifacts e anexos maiores.

## 9. Confiabilidade e Seguranca
- idempotencia por request_id.
- retries com backoff e circuit breaker para dependencias externas.
- timeout padrao por tool/skill/provider.
- segregacao de segredos por ambiente.
- policy simulation mode (dry-run) para validar regras.
- assinatura e verificacao de integridade de plugins.

### 9.1 Gestao Centralizada de Secrets (diretriz arquitetural)
Diretriz para fases futuras:
- secrets devem ser gerenciados por um componente central (Secret Broker), nao por leitura direta em tools/agentes/providers.
- agentes nunca recebem valores brutos de secrets; apenas referencias logicas.
- injeção de segredo ocorre apenas no boundary do provider/sandbox, com escopo minimo necessario.

Componentes previstos:
1. SecretBroker (core)
- interface unica para resolver segredo por chave logica.
- aplica policy, escopo e auditoria.

2. SecretStore (plugin)
- backend local para desenvolvimento (arquivo criptografado).
- backend externo para producao (Vault/Secret Manager equivalente).

3. SecretPolicy
- regras de allow/deny por provider, workspace e ambiente.
- bloqueio de leitura direta em filesystem sensivel.
- redacao automatica em logs, traces e eventos.

Regras de seguranca:
- sem secret em manifest.json, logs, mensagens de agente ou artifacts.
- cada provider acessa apenas os secrets do proprio escopo.
- rotacao e auditoria obrigatorias para segredos de producao.

Nota de escopo:
- este item esta registrado como diretriz arquitetural e nao faz parte do escopo imediato da implementacao atual.

## 10. Roadmap de Implementacao (MVP -> Maturidade)
1. MVP de runtime
- envelopes v1
- session manager + postgres
- policy engine basico
- gateway CLI
- provider unico
- sandbox docker

2. Fase 2
- registry/loader de plugins por manifest
- conformidade automatica de contrato
- memoria working + long-term
- event bus e auditoria completa

3. Fase 3
- multiplos gateways (Slack/WhatsApp/API)
- catalogo completo de sandboxes
- policy simulation
- score de confianca de plugins

## 11. Decisoes Arquiteturais Criticas
- Sessao: estado canonico no Runtime Core (Session Manager).
- Gateway: sem estado de negocio permanente.
- Contratos: envelope unico para entrada/saida.
- Extensoes: plugin-first por manifest e interface obrigatoria.
- Seguranca: policy-first e sandbox-by-default.

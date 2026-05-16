# Thoth - Camada 1 (Contratos de Runtime)

## Objetivo
Implementar a primeira camada do Thoth com contratos canonicos de entrada/saida, estado de sessao basico, orquestracao minima e eventos iniciais de observabilidade.

Resultado esperado:
- qualquer gateway consegue enviar input em formato padrao.
- o runtime responde em formato padrao.
- a sessao tem estado canonico no runtime.
- existe trilha minima de eventos para request e response.

## Escopo da Camada 1
1. RuntimeInputEnvelope e RuntimeOutputEnvelope.
2. Validacao de campos obrigatorios e schema_version.
3. Session Manager minimo (create/get/save).
4. Session Store em memoria (MVP) com interface para persistencia futura.
5. Orchestrator minimo (input -> output).
6. Event Bus minimo com eventos request.received e response.emitted.
7. Integracao CLI basica para exercitar o fluxo ponta a ponta.

## Estrutura de pastas sugerida nesta etapa
- src/thoth/domain/envelopes.py
- src/thoth/domain/session.py
- src/thoth/domain/events.py
- src/thoth/core/session_manager.py
- src/thoth/core/session_store.py
- src/thoth/core/orchestrator.py
- src/thoth/core/event_bus.py
- src/thoth/app/runtime.py
- tests/domain/test_envelopes.py
- tests/core/test_session_manager.py
- tests/core/test_orchestrator.py

## Passo a passo

### Passo 1 - Definir modelos canonicos de envelope
Tarefas:
1. Criar RuntimeInputEnvelope com os campos minimos do manifesto.
2. Criar RuntimeOutputEnvelope com os campos minimos do manifesto.
3. Definir enums/status para reduzir ambiguidade de respostas.

Decisoes:
- usar dataclasses no MVP para simplicidade.
- manter schema_version explicito em ambos os envelopes.

Criterio de pronto:
- modelos criados e importaveis.

### Passo 2 - Implementar validacao de envelope
Tarefas:
1. Criar validadores para campos obrigatorios.
2. Validar schema_version suportada.
3. Padronizar erro de validacao com codigo e mensagem.

Decisoes:
- erros de contrato devem ser deterministas e testaveis.
- nenhuma execucao segue adiante sem envelope valido.

Criterio de pronto:
- testes cobrindo casos validos e invalidos.

### Passo 3 - Criar modelo de sessao
Tarefas:
1. Definir SessionState com session_id, revision, metadata e dados operacionais basicos.
2. Definir regra de incremento de revision por mutacao.
3. Definir timestamp de criacao e atualizacao.

Decisoes:
- session_id e obrigatorio para correlacao.
- estado de sessao e canonico no runtime.

Criterio de pronto:
- SessionState com operacoes basicas de atualizacao.

### Passo 4 - Implementar Session Store (MVP in-memory)
Tarefas:
1. Criar interface SessionStore (porta).
2. Implementar InMemorySessionStore (adapter inicial).
3. Suportar create/get/save por session_id.

Decisoes:
- in-memory apenas para MVP.
- interface pronta para trocar por PostgreSQL depois.

Criterio de pronto:
- store substituivel sem alterar Session Manager.

### Passo 5 - Implementar Session Manager
Tarefas:
1. Criar metodo get_or_create(session_id).
2. Criar metodo persist(state).
3. Aplicar regra de concorrencia simples por sessao (lock local do processo).

Decisoes:
- manager concentra regras de ciclo de vida de sessao.
- gateway nao guarda estado canonico.

Criterio de pronto:
- sessao criada automaticamente quando inexistente.

### Passo 6 - Implementar Event Bus minimo
Tarefas:
1. Definir modelo de evento com type, timestamp, request_id e session_id.
2. Implementar publish(event).
3. Implementar subscriber opcional para logs.

Eventos obrigatorios:
- request.received
- response.emitted

Criterio de pronto:
- eventos publicados durante fluxo principal.

### Passo 7 - Implementar Orchestrator minimo
Tarefas:
1. Receber RuntimeInputEnvelope valido.
2. Publicar request.received.
3. Carregar sessao via Session Manager.
4. Gerar RuntimeOutputEnvelope com resposta simples de confirmacao.
5. Persistir novo estado de sessao.
6. Publicar response.emitted.

Decisoes:
- sem provider/tool real nesta etapa.
- foco e garantir contrato e ciclo de estado.

Criterio de pronto:
- fluxo completo executa sem dependencias externas.

### Passo 8 - Integrar no app/runtime e CLI
Tarefas:
1. Criar runtime.py com bootstrap dos componentes.
2. Ajustar CLI para chamar o runtime com input de exemplo.
3. Exibir output em formato legivel.

Decisoes:
- CLI atua como primeiro gateway adapter.
- manter separacao entre adaptacao de entrada e core.

Criterio de pronto:
- comando local executa o fluxo ponta a ponta.

### Passo 9 - Cobertura de testes minima
Tarefas:
1. Testes de validacao de envelope.
2. Testes de Session Manager (create/get/save/revision).
3. Teste de orquestracao ponta a ponta em memoria.

Criterio de pronto:
- todos os testes passando com uv run pytest.

### Passo 10 - Definir pronto para seguir para Camada 2
Checklist:
1. Contratos de input/output estaveis.
2. Erros de validacao padronizados.
3. Sessao canonica funcionando com revision.
4. Eventos request/response emitidos.
5. CLI exercitando o caminho feliz.
6. Testes verdes.

Se tudo acima estiver verde, iniciar Camada 2:
- Policy Engine basico.
- Plugin Loader por manifest.

Status atual (2026-05-13):
1. Concluido: contratos de input/output estaveis.
2. Concluido: erros de validacao padronizados.
3. Concluido: sessao canonica funcionando com revision.
4. Concluido: eventos request/response emitidos.
5. Concluido: CLI exercitando o caminho feliz.
6. Concluido: testes verdes.

Decisao:
- Camada 1 aprovada para avancar.
- Proxima etapa: iniciar Camada 2 com Policy Engine basico e Plugin Loader por manifest.

## Ordem de implementacao recomendada (curta)
1. domain/envelopes.py
2. domain/session.py
3. core/session_store.py
4. core/session_manager.py
5. domain/events.py + core/event_bus.py
6. core/orchestrator.py
7. app/runtime.py
8. ajustes de CLI
9. testes

## Comandos operacionais
- uv sync --dev
- uv run pytest
- uv run ruff check .
- uv run mypy src

## Riscos e mitigacoes
1. Risco: acoplamento de CLI com core.
Mitigacao: manter adaptacao no app/runtime e usar envelopes no core.

2. Risco: estado de sessao espalhado.
Mitigacao: centralizar regras no Session Manager.

3. Risco: contrato instavel cedo.
Mitigacao: validar schema_version e travar campos obrigatorios desde o inicio.

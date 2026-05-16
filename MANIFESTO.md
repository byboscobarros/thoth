# Manifesto Thoth

## 1. Proposito
Thoth e um runtime/harness para agentes autonomos, desenhado para operacao real, extensibilidade maxima e governanca explicita.

Nosso objetivo nao e apenas "rodar agentes"; e oferecer uma base padronizada para orquestrar providers, tools, skills, gateways, MCPs e sandboxes com seguranca, previsibilidade e customizacao profunda.

## 2. Principios Nao Negociaveis
1. Modularidade em primeiro lugar
Todo componente que puder ser plugavel deve ser plugavel.

2. Manifest-driven architecture
Novos modulos devem ser registraveis por manifesto declarativo (manifest.json), com contrato claro de capacidades e metodos obrigatorios.

3. Convencao + contrato + validacao
A experiencia de extensao deve ser simples, mas rigorosa: schema versionado, validacao em load-time e erro explicito.

4. Seguranca configuravel, nao acidental
Guardrails elasticos: do modo permissivo ao altamente restritivo, sempre auditavel e reversivel por configuracao.

5. Execucao isolada por padrao
Tools, skills e agentes podem rodar em isolamento (microVM, VM, container ou local controlado), conforme politica e risco.

6. Observabilidade por design
Tudo importante gera trilha de auditoria: quem fez, quando fez, com que permissao, com qual resultado.

7. Padronizacao para escala
Padroes claros de ciclo de vida, versionamento, naming, logs, erros e telemetria.

8. Compatibilidade progressiva
Evolucao sem quebrar ecossistema: deprecacao orientada, feature flags e migracoes guiadas.

## 3. Arquitetura de Extensao Universal
Todo tipo de extensao (provider, gateway, skill, tool, mcp, sandbox driver, agent profile) deve seguir o mesmo modelo:

- `manifest.json`: metadados, versao, capacidades, dependencias, permissoes, runtime alvo.
- `contract`: metodos obrigatorios por tipo.
- `health`: check de sanidade para load e runtime.
- `permissions`: escopo minimo necessario.
- `policies`: limites de execucao e guardrail.

### 3.1 Contrato minimo de provider (exemplo)
1. `initialize(context)`
2. `execute(request)`
3. `stream(request)` (quando aplicavel)
4. `shutdown()`
5. `healthcheck()`

Se o modulo implementar o contrato e o manifesto validar no schema oficial, o sistema deve fazer discovery, load, registro e exposicao automatica.

## 4. Guardrail Elastico
Thoth deve oferecer um motor de policy com composicao em camadas:

1. Global policy (organizacao)
2. Workspace policy (projeto)
3. Session policy (execucao atual)
4. Agent policy (perfil)
5. Tool policy (operacao especifica)

Cada camada pode:
- permitir, negar, exigir aprovacao, mascarar dado, ou redirecionar para sandbox.
- ser declarativa (YAML/JSON) e testavel.
- registrar decisao com motivo em trilha de auditoria.

Modos sugeridos de operacao:
- `permissive`
- `balanced`
- `strict`
- `air-gapped`

## 5. Catalogo de Sandboxes
O runtime deve suportar multiplos backends de isolamento com interface unica:

- `container` (Docker, Podman)
- `microvm` (Firecracker, Kata, etc)
- `vm` (QEMU, cloud VM)
- `native` (apenas para ambientes confiaveis)

Cada sandbox entry no catalogo deve declarar:
- nivel de isolamento
- custo estimado
- latencia de cold start
- limites de CPU/memoria/rede/disco
- politicas de egress
- compliance tags

Objetivo: permitir que usuario escolha isolamento por tarefa, risco e custo.

## 6. Memoria e Aprendizagem Continua
Thoth deve ter um subsistema de memoria e aprendizagem inspirado em abordagens maduras de agentes, mas com governanca explicita e padrao de contrato.

Camadas de memoria obrigatorias:
- `ephemeral`: memoria de curto prazo da execucao/sessao.
- `working`: contexto operacional atual (tarefas, planos, estado intermediario).
- `long-term`: fatos, preferencias, resultados historicos e conhecimento validado.
- `org-knowledge`: base compartilhada por workspace/organizacao, com permissoes.

Principios de aprendizagem:
1. Aprender com eventos e resultados
Cada interacao pode gerar "memory candidates" com score de relevancia.

2. Consolidacao controlada
Nao existe escrita cega em memoria permanente; toda consolidacao segue policy, thresholds e filtros de risco.

3. Memoria auditavel e versionada
Toda escrita, atualizacao e exclusao deve gerar trilha de auditoria e versionamento.

4. Retencao e esquecimento programaveis
TTL, politicas de expiracao, sumarizacao e "right to forget" configuravel por tenant/workspace.

5. Privacidade e minimizacao de dados
Dados sensiveis devem ser mascarados, criptografados ou bloqueados por policy antes de persistir.

6. Portabilidade de memoria
Memoria exportavel/importavel por formato padrao para migracao entre ambientes.

Mecanismos minimos do runtime:
- memory registry plugavel (vector, sql, kv, graph).
- pipeline de ingestao: capture -> score -> redact -> persist.
- retrieval hibrido (semantico + simbolico + filtros de policy).
- feedback loop para melhorar selecao de contexto e estrategia do agente.

## 7. Envelope Canonico de Runtime (Entrada e Saida)
Sem bagunca de integracao: todo gateway (CLI, Slack, WhatsApp, API, etc) conversa com Thoth por um envelope canonico unico.

Regras obrigatorias:
1. Gateway nunca fala com provider diretamente
Gateway adapta payload externo para `RuntimeInputEnvelope`.

2. Runtime nunca devolve formato especifico de gateway
Runtime sempre responde em `RuntimeOutputEnvelope`, e o adapter do gateway faz renderizacao final.

3. Contratos estaveis e versionados
Envelope com `schema_version` e backward compatibility declarada.

4. Metadados de governanca sempre presentes
identidade, origem, tenant, sessao, trace-id, policy-mode, nivel de risco, sandbox selecionada.

5. Conteudo e controle separados
campos distintos para `content`, `actions`, `tool_calls`, `events`, `artifacts`, `errors`.

Campos minimos de entrada (`RuntimeInputEnvelope`):
- `schema_version`
- `request_id`
- `timestamp`
- `gateway`
- `actor`
- `session`
- `context`
- `input`
- `attachments`
- `policy_hints`

Campos minimos de saida (`RuntimeOutputEnvelope`):
- `schema_version`
- `request_id`
- `timestamp`
- `status`
- `messages`
- `actions`
- `tool_results`
- `artifacts`
- `memory_updates`
- `policy_decisions`
- `audit_ref`

Beneficios diretos:
- troca de gateway sem alterar core do runtime.
- testes de contrato unificados para todas as integracoes.
- observabilidade e compliance consistentes ponta a ponta.

## 8. Governanca e Maturidade
1. Versionamento sem ambiguidades
SemVer para core + compatibilidade declarada por plugin.

2. Contratos versionados
Schema versionado para manifestos com migradores oficiais.

3. Testes por nivel
- unitario (contrato)
- integracao (runtime)
- conformidade (plugin)
- seguranca (policy/sandbox)

4. Qualidade minima para plugin publico
Assinatura, provenance, scanner de seguranca, SBOM e score de confianca.

5. Documentacao operacional
Todo modulo deve ter exemplos, limites e fallback behavior.

## 9. UX para Desenvolvedor de Plugin
A regra de ouro: "plugar rapido, operar com seguranca".

Thoth deve fornecer:
- CLI para scaffold de plugin por tipo.
- geracao automatica de `manifest.json`.
- testes de contrato em um comando.
- simulador local de policy + sandbox.
- validacao antes de publicar no catalogo.

## 10. Propostas Adicionais para um Projeto Maduro
1. Capability graph
Mapa declarativo de capacidades e dependencias entre modulos para evitar acoplamento oculto.

2. Event bus oficial
Eventos padronizados (`agent.started`, `tool.failed`, etc) para observabilidade e extensoes reativas.

3. Runtime profiles
Perfis prontos (`dev`, `ci`, `prod`, `regulated`) com combinacoes de policy e sandbox.

4. Reproducibilidade
Execucoes com lock de versoes, snapshot de config e trace-id unico.

5. Supply-chain security
Assinatura de plugins, verificacao de integridade e allowlist por organizacao.

6. Modo "policy simulation"
Rodar uma execucao em "dry-run" para prever bloqueios antes de ir para producao.

7. Matriz de confianca
Score para providers/tools/plugins baseado em origem, historico, vulnerabilidades e comportamento.

8. Default seguro, override explicito
Mesmo permissivo, toda elevacao de privilegio deve ser deliberada e auditavel.

## 11. Definicao de Sucesso
Thoth sera considerado maduro quando:
- novas extensoes forem adicionadas sem alterar o core.
- politicas e isolamento forem trocados por config, sem refatoracoes profundas.
- cada execucao for auditavel fim a fim.
- a plataforma manter compatibilidade enquanto evolui rapidamente.

## 12. Frase Guia
"Tudo que puder ser plugin, sera plugin. Tudo que puder ser politica, sera politica. Tudo que puder ser isolado, sera isolado."

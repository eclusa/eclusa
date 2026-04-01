# Guia do Usuário do Eclusa

Referência detalhada de workflows, troubleshooting e configuração. Para setup rápido, veja o [README](../../README.pt-BR.md).

---

## Sumário

- [Fluxo de trabalho](#fluxo-de-trabalho)
- [Contrato de UI](#contrato-de-ui)
- [Backlog e Threads](#backlog-e-threads)
- [Workstreams](#workstreams)
- [Segurança](#segurança)
- [Referência de comandos](#referência-de-comandos)
- [Configuração](#configuração)
- [Exemplos de uso](#exemplos-de-uso)
- [Troubleshooting](#troubleshooting)
- [Recuperação rápida](#recuperação-rápida)

---

## Fluxo de trabalho

Fluxo recomendado por fase:

1. `/eclusa:discuss-phase [N]` — trava preferências de implementação
2. `/eclusa:ui-phase [N]` — contrato visual para fases frontend
3. `/eclusa:plan-phase [N]` — pesquisa + plano + validação
4. `/eclusa:execute-phase [N]` — execução em ondas paralelas
5. `/eclusa:verify-work [N]` — UAT manual com diagnóstico
6. `/eclusa:ship [N]` — cria PR (opcional)

Para iniciar projeto novo:

```bash
/eclusa:new-project
```

Para seguir automaticamente o próximo passo:

```bash
/eclusa:next
```

### Nyquist Validation

Durante `plan-phase`, o Eclusa pode mapear requisitos para comandos de teste automáticos antes da implementação. Isso gera `{phase}-VALIDATION.md` e aumenta a confiabilidade de verificação pós-execução.

Desativar:

```json
{
  "workflow": {
    "nyquist_validation": false
  }
}
```

### Modo de discussão por suposições

Com `workflow.discuss_mode: "assumptions"`, o Eclusa analisa o código antes de perguntar, apresenta suposições estruturadas e pede apenas correções.

---

## Contrato de UI

### Comandos

| Comando | Descrição |
|---------|-----------|
| `/eclusa:ui-phase [N]` | Gera contrato de design `UI-SPEC.md` para a fase |
| `/eclusa:ui-review [N]` | Auditoria visual retroativa em 6 pilares |

### Quando usar

- Rode `/eclusa:ui-phase` depois de `/eclusa:discuss-phase` e antes de `/eclusa:plan-phase`.
- Rode `/eclusa:ui-review` após execução/validação para avaliar qualidade visual e consistência.

### Configurações relacionadas

| Setting | Padrão | O que controla |
|---------|--------|----------------|
| `workflow.ui_phase` | `true` | Gera contratos de UI para fases frontend |
| `workflow.ui_safety_gate` | `true` | Ativa gate de segurança para componentes de registry |

---

## Backlog e Threads

### Backlog (999.x)

Ideias fora da sequência ativa vão para backlog:

```bash
/eclusa:add-backlog "Camada GraphQL"
/eclusa:add-backlog "Responsividade mobile"
```

Promover/revisar:

```bash
/eclusa:review-backlog
```

### Seeds

Seeds guardam ideias futuras com condição de gatilho:

```bash
/eclusa:plant-seed "Adicionar colaboração real-time quando infra de WebSocket estiver pronta"
```

### Threads persistentes

Threads são contexto leve entre sessões:

```bash
/eclusa:thread
/eclusa:thread fix-deploy-key-auth
/eclusa:thread "Investigar timeout TCP"
```

---

## Workstreams

Workstreams permitem trabalho paralelo sem colisão de estado de planejamento.

| Comando | Função |
|---------|--------|
| `/eclusa:workstreams create <name>` | Cria workstream isolado |
| `/eclusa:workstreams switch <name>` | Troca workstream ativo |
| `/eclusa:workstreams list` | Lista workstreams |
| `/eclusa:workstreams complete <name>` | Finaliza e arquiva workstream |

`workstreams` compartilham o mesmo código/git, mas isolam artefatos de `.eclusa/`.

---

## Segurança

O Eclusa aplica defesa em profundidade:

- prevenção de path traversal em entradas de arquivo
- detecção de prompt injection em texto do usuário
- hooks de proteção para escrita em `.eclusa/`
- scanner CI para padrões de injeção em agentes/workflows/comandos

Para arquivos sensíveis, use deny list no Claude Code.

---

## Referência de comandos

### Fluxo principal

| Comando | Quando usar |
|---------|-------------|
| `/eclusa:new-project` | Início de projeto |
| `/eclusa:discuss-phase [N]` | Definir preferências antes do plano |
| `/eclusa:plan-phase [N]` | Criar e validar planos |
| `/eclusa:execute-phase [N]` | Executar planos em ondas |
| `/eclusa:verify-work [N]` | UAT manual |
| `/eclusa:ship [N]` | Gerar PR da fase |
| `/eclusa:next` | Próximo passo automático |

### Gestão e utilidades

| Comando | Quando usar |
|---------|-------------|
| `/eclusa:progress` | Ver status atual |
| `/eclusa:resume-work` | Retomar sessão |
| `/eclusa:pause-work` | Pausar com handoff |
| `/eclusa:session-report` | Resumo da sessão |
| `/eclusa:quick` | Tarefa ad-hoc com garantias Eclusa |
| `/eclusa:debug [desc]` | Debug sistemático |
| `/eclusa:forensics` | Diagnóstico de workflow quebrado |
| `/eclusa:settings` | Ajustar workflow/modelos |
| `/eclusa:set-profile <profile>` | Troca rápida de perfil |

Para lista completa e flags avançadas, consulte [Command Reference](../COMMANDS.md).

---

## Configuração

Arquivo de configuração: `.eclusa/config.json`

### Núcleo

| Setting | Opções | Padrão |
|---------|--------|--------|
| `mode` | `interactive`, `yolo` | `interactive` |
| `granularity` | `coarse`, `standard`, `fine` | `standard` |
| `model_profile` | `quality`, `balanced`, `budget`, `inherit` | `balanced` |

### Workflow

| Setting | Padrão |
|---------|--------|
| `workflow.research` | `true` |
| `workflow.plan_check` | `true` |
| `workflow.verifier` | `true` |
| `workflow.nyquist_validation` | `true` |
| `workflow.ui_phase` | `true` |
| `workflow.ui_safety_gate` | `true` |

### Perfis de modelo

| Perfil | Uso recomendado |
|--------|------------------|
| `quality` | trabalho crítico, maior qualidade |
| `balanced` | padrão recomendado |
| `budget` | reduzir custo de tokens |
| `inherit` | seguir modelo da sessão/runtime |

Detalhes completos: [Configuration Reference](../CONFIGURATION.md).

---

## Exemplos de uso

### Projeto novo

```bash
claude --dangerously-skip-permissions
/eclusa:new-project
/eclusa:discuss-phase 1
/eclusa:ui-phase 1
/eclusa:plan-phase 1
/eclusa:execute-phase 1
/eclusa:verify-work 1
/eclusa:ship 1
```

### Código já existente

```bash
/eclusa:map-codebase
/eclusa:new-project
```

### Correção rápida

```bash
/eclusa:quick
> "Corrigir botão de login no mobile Safari"
```

### Preparação para release

```bash
/eclusa:audit-milestone
/eclusa:plan-milestone-gaps
/eclusa:complete-milestone
```

---

## Troubleshooting

### "Project already initialized"

`.eclusa/PROJECT.md` já existe. Apague `.eclusa/` se quiser reiniciar do zero.

### Sessão longa degradando contexto

Use `/clear` entre etapas grandes e retome com `/eclusa:resume-work` ou `/eclusa:progress`.

### Plano desalinhado

Rode `/eclusa:discuss-phase [N]` antes do plano e valide suposições com `/eclusa:list-phase-assumptions [N]`.

### Execução falhou ou saiu com stubs

Replaneje com escopo menor (tarefas menores por plano).

### Custo alto

Use perfil budget:

```bash
/eclusa:set-profile budget
```

### Runtime não-Claude (Codex/OpenCode/Gemini)

Use `resolve_model_ids: "omit"` para deixar o runtime resolver modelos padrão.

---

## Recuperação rápida

| Problema | Solução |
|---------|---------|
| Perdeu contexto | `/eclusa:resume-work` ou `/eclusa:progress` |
| Fase deu errado | `git revert` + replanejar |
| Precisa alterar escopo | `/eclusa:add-phase`, `/eclusa:insert-phase`, `/eclusa:remove-phase` |
| Bug em workflow | `/eclusa:forensics` |
| Correção pontual | `/eclusa:quick` |
| Custo alto | `/eclusa:set-profile budget` |
| Não sabe próximo passo | `/eclusa:next` |

---

## Estrutura de arquivos do projeto

```text
.eclusa/
  PROJECT.md
  REQUIREMENTS.md
  ROADMAP.md
  STATE.md
  config.json
  MILESTONES.md
  HANDOFF.json
  research/
  reports/
  todos/
  debug/
  codebase/
  phases/
    XX-phase-name/
      XX-YY-PLAN.md
      XX-YY-SUMMARY.md
      CONTEXT.md
      RESEARCH.md
      VERIFICATION.md
      XX-UI-SPEC.md
      XX-UI-REVIEW.md
  ui-reviews/
```

> [!NOTE]
> Esta é a versão pt-BR do guia para uso diário. Para detalhes técnicos exatos e cobertura completa de parâmetros avançados, consulte também o [guia original em inglês](../USER-GUIDE.md).

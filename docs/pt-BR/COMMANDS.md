# Referência de Comandos do Eclusa

Este documento descreve os comandos principais do Eclusa em Português.  
Para detalhes completos de flags avançadas e mudanças recentes, consulte também a [versão em inglês](../COMMANDS.md).

---

## Fluxo Principal

| Comando | Finalidade | Quando usar |
|---------|------------|-------------|
| `/eclusa:new-project` | Inicialização completa: perguntas, pesquisa, requisitos e roadmap | Início de projeto |
| `/eclusa:discuss-phase [N]` | Captura decisões de implementação | Antes do planejamento |
| `/eclusa:ui-phase [N]` | Gera contrato de UI (`UI-SPEC.md`) | Fases com frontend |
| `/eclusa:plan-phase [N]` | Pesquisa + planejamento + verificação | Antes de executar uma fase |
| `/eclusa:execute-phase <N>` | Executa planos em ondas paralelas | Após planejamento aprovado |
| `/eclusa:verify-work [N]` | UAT manual com diagnóstico automático | Após execução |
| `/eclusa:ship [N]` | Cria PR da fase validada | Ao concluir a fase |
| `/eclusa:next` | Detecta e executa o próximo passo lógico | Qualquer momento |
| `/eclusa:fast <texto>` | Tarefa curta sem planejamento completo | Ajustes triviais |

## Navegação e Sessão

| Comando | Finalidade |
|---------|------------|
| `/eclusa:progress` | Mostra status atual e próximos passos |
| `/eclusa:resume-work` | Retoma contexto da sessão anterior |
| `/eclusa:pause-work` | Salva handoff estruturado |
| `/eclusa:session-report` | Gera resumo da sessão |
| `/eclusa:help` | Lista comandos e uso |
| `/eclusa:update` | Atualiza o Eclusa |

## Gestão de Fases

| Comando | Finalidade |
|---------|------------|
| `/eclusa:add-phase` | Adiciona fase no roadmap |
| `/eclusa:insert-phase [N]` | Insere trabalho urgente entre fases |
| `/eclusa:remove-phase [N]` | Remove fase futura e reenumera |
| `/eclusa:list-phase-assumptions [N]` | Mostra abordagem assumida pelo Claude |
| `/eclusa:plan-milestone-gaps` | Cria fases para fechar lacunas de auditoria |

## Brownfield e Utilidades

| Comando | Finalidade |
|---------|------------|
| `/eclusa:map-codebase` | Mapeia base existente antes de novo projeto |
| `/eclusa:quick` | Tarefas ad-hoc com garantias do Eclusa |
| `/eclusa:debug [desc]` | Debug sistemático com estado persistente |
| `/eclusa:forensics` | Diagnóstico de falhas no workflow |
| `/eclusa:settings` | Configuração de agentes, perfil e toggles |
| `/eclusa:set-profile <perfil>` | Troca rápida de perfil de modelo |

## Qualidade de Código

| Comando | Finalidade |
|---------|------------|
| `/eclusa:review` | Peer review com múltiplas IAs |
| `/eclusa:pr-branch` | Cria branch limpa sem commits de planejamento |
| `/eclusa:audit-uat` | Audita dívida de validação/UAT |

## Backlog e Threads

| Comando | Finalidade |
|---------|------------|
| `/eclusa:add-backlog <desc>` | Adiciona item no backlog (999.x) |
| `/eclusa:review-backlog` | Promove, mantém ou remove itens |
| `/eclusa:plant-seed <ideia>` | Registra ideia com gatilho futuro |
| `/eclusa:thread [nome]` | Gerencia threads persistentes |

---

## Exemplo rápido

```bash
/eclusa:new-project
/eclusa:discuss-phase 1
/eclusa:plan-phase 1
/eclusa:execute-phase 1
/eclusa:verify-work 1
/eclusa:ship 1
```

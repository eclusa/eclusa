---
name: eclusa:do
description: Route freeform text to the right Eclusa command automatically
argument-hint: "<description of what you want to do>"
allowed-tools:
  - Read
  - Bash
  - AskUserQuestion
---
<objective>
Analyze freeform natural language input and dispatch to the most appropriate Eclusa command.

Acts as a smart dispatcher — never does the work itself. Matches intent to the best Eclusa command using routing rules, confirms the match, then hands off.

Use when you know what you want but don't know which `/eclusa:*` command to run.
</objective>

<execution_context>
@~/.claude/eclusa/workflows/do.md
@~/.claude/eclusa/references/ui-brand.md
</execution_context>

<context>
$ARGUMENTS
</context>

<process>
Execute the do workflow from @~/.claude/eclusa/workflows/do.md end-to-end.
Route user intent to the best Eclusa command and invoke it.
</process>

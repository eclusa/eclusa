---
name: eclusa:cleanup
description: Archive accumulated phase directories from completed milestones
---
<objective>
Archive phase directories from completed milestones into `.eclusa/milestones/v{X.Y}-phases/`.

Use when `.eclusa/phases/` has accumulated directories from past milestones.
</objective>

<execution_context>
@~/.claude/eclusa/workflows/cleanup.md
</execution_context>

<process>
Follow the cleanup workflow at @~/.claude/eclusa/workflows/cleanup.md.
Identify completed milestones, show a dry-run summary, and archive on confirmation.
</process>

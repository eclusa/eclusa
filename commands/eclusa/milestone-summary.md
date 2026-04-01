---
type: prompt
name: eclusa:milestone-summary
description: Generate a comprehensive project summary from milestone artifacts for team onboarding and review
argument-hint: "[version]"
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
---

<objective>
Generate a structured milestone summary for team onboarding and project review. Reads completed milestone artifacts (ROADMAP, REQUIREMENTS, CONTEXT, SUMMARY, VERIFICATION files) and produces a human-friendly overview of what was built, how, and why.

Purpose: Enable new team members to understand a completed project by reading one document and asking follow-up questions.
Output: MILESTONE_SUMMARY written to `.eclusa/reports/`, presented inline, optional interactive Q&A.
</objective>

<execution_context>
@~/.claude/eclusa/workflows/milestone-summary.md
</execution_context>

<context>
**Project files:**
- `.eclusa/ROADMAP.md`
- `.eclusa/PROJECT.md`
- `.eclusa/STATE.md`
- `.eclusa/RETROSPECTIVE.md`
- `.eclusa/milestones/v{version}-ROADMAP.md` (if archived)
- `.eclusa/milestones/v{version}-REQUIREMENTS.md` (if archived)
- `.eclusa/phases/*-*/` (SUMMARY.md, VERIFICATION.md, CONTEXT.md, RESEARCH.md)

**User input:**
- Version: $ARGUMENTS (optional — defaults to current/latest milestone)
</context>

<process>
Read and execute the milestone-summary workflow from @~/.claude/eclusa/workflows/milestone-summary.md end-to-end.
</process>

<success_criteria>
- Milestone version resolved (from args, STATE.md, or archive scan)
- All available artifacts read (ROADMAP, REQUIREMENTS, CONTEXT, SUMMARY, VERIFICATION, RESEARCH, RETROSPECTIVE)
- Summary document written to `.eclusa/reports/MILESTONE_SUMMARY-v{version}.md`
- All 7 sections generated (Overview, Architecture, Phases, Decisions, Requirements, Tech Debt, Getting Started)
- Summary presented inline to user
- Interactive Q&A offered
- STATE.md updated
</success_criteria>

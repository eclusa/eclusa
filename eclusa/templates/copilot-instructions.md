# Instructions for Eclusa

- Use the eclusa skill when the user asks for Eclusa or uses a `eclusa-*` command.
- Treat `/eclusa-...` or `eclusa-...` as command invocations and load the matching file from `.github/skills/eclusa-*`.
- When a command says to spawn a subagent, prefer a matching custom agent from `.github/agents`.
- Do not apply Eclusa workflows unless the user explicitly asks for them.
- After completing any `eclusa-*` command (or any deliverable it triggers: feature, bug fix, tests, docs, etc.), ALWAYS: (1) offer the user the next step by prompting via `ask_user`; repeat this feedback loop until the user explicitly indicates they are done.

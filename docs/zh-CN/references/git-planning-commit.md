# Git 规划提交

使用 eclusa-tools CLI 提交规划工件，它会自动检查 `commit_docs` 配置和 gitignore 状态。

## 通过 CLI 提交

始终使用 `eclusa-tools.cjs commit` 处理 `.eclusa/` 文件 — 它会自动处理 `commit_docs` 和 gitignore 检查：

```bash
node "$HOME/.claude/eclusa/bin/eclusa-tools.cjs" commit "docs({scope}): {description}" --files .eclusa/STATE.md .eclusa/ROADMAP.md
```

如果 `commit_docs` 为 `false` 或 `.eclusa/` 被 gitignore，CLI 会返回 `skipped`（带原因）。无需手动条件检查。

## 修改上次提交

将 `.eclusa/` 文件变更合并到上次提交：

```bash
node "$HOME/.claude/eclusa/bin/eclusa-tools.cjs" commit "" --files .eclusa/codebase/*.md --amend
```

## 提交消息模式

| 命令 | 范围 | 示例 |
|------|------|------|
| plan-phase | phase | `docs(phase-03): create authentication plans` |
| execute-phase | phase | `docs(phase-03): complete authentication phase` |
| new-milestone | milestone | `docs: start milestone v1.1` |
| remove-phase | chore | `chore: remove phase 17 (dashboard)` |
| insert-phase | phase | `docs: insert phase 16.1 (critical fix)` |
| add-phase | phase | `docs: add phase 07 (settings page)` |

## 何时跳过

- config 中 `commit_docs: false`
- `.eclusa/` 被 gitignore
- 无变更可提交（用 `git status --porcelain .eclusa/` 检查）
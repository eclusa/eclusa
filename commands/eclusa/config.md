---
description: Edit vestibular or project file
subagent_type: general-purpose
---

# eclusa:config

Edit eclusa configuration files interactively.

## Usage

```
/eclusa:config [target]
```

**Targets:**
- `vestibular` — Edit `~/.vestibular` (human orientation, portable across projects)
- `project` — Edit `project.eclusa` (project pipeline configuration)
- (no target) — Show current config status for both files

## Behavior

### No target: Status overview

1. Load vestibular from `~/.vestibular`:
```bash
node "$HOME/.claude/eclusa/bin/eclusa-tools.cjs" vestibular load
```

2. Load project file from current directory:
```bash
node "$HOME/.claude/eclusa/bin/eclusa-tools.cjs" project-file load
```

3. Display status:
   - Vestibular: found/not found, valid/invalid, register.name, autonomy.level
   - Project: found/not found, valid/invalid, identity.name, sources count, stances count
   - Validation errors (if any)

### Target: vestibular

If `~/.vestibular` doesn't exist, offer to scaffold:

```
AskUserQuestion([{
  question: "No ~/.vestibular found. Create one?",
  header: "Vestibular",
  options: [
    { label: "Create", description: "Answer a few questions to set up your orientation file" },
    { label: "Skip", description: "Continue without a vestibular" }
  ]
}])
```

If creating, ask:
1. Name and role
2. Autonomy level (autonomous / collaborative / supervised)
3. Communication style (concise / detailed / verbose)
4. Notification script path (optional)

Then scaffold:
```bash
node "$HOME/.claude/eclusa/bin/eclusa-tools.cjs" vestibular scaffold '{"name":"NAME","role":"ROLE","autonomy_level":"LEVEL","communication_style":"STYLE"}'
```

If `~/.vestibular` exists, show current values and offer to edit specific sections.

### Target: project

If `project.eclusa` doesn't exist, offer to scaffold (same as Step 4b in new-project).

If it exists, show current values and offer to edit:
- Identity (name, description, tags)
- Stances (add/remove/modify)
- Agent model bindings
- Provenance settings

After edits, validate:
```bash
node "$HOME/.claude/eclusa/bin/eclusa-tools.cjs" project-file validate
```

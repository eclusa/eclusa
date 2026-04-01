---
name: eclusa:add-backlog
description: Add an idea to the backlog parking lot (999.x numbering)
argument-hint: <description>
allowed-tools:
  - Read
  - Write
  - Bash
---

<objective>
Add a backlog item to the roadmap using 999.x numbering. Backlog items are
unsequenced ideas that aren't ready for active planning — they live outside
the normal phase sequence and accumulate context over time.
</objective>

<process>

1. **Read ROADMAP.md** to find existing backlog entries:
   ```bash
   cat .eclusa/ROADMAP.md
   ```

2. **Find next backlog number:**
   ```bash
   NEXT=$(node "$HOME/.claude/eclusa/bin/eclusa-tools.cjs" phase next-decimal 999 --raw)
   ```
   If no 999.x phases exist, start at 999.1.

3. **Create the phase directory:**
   ```bash
   SLUG=$(node "$HOME/.claude/eclusa/bin/eclusa-tools.cjs" generate-slug "$ARGUMENTS")
   mkdir -p ".eclusa/phases/${NEXT}-${SLUG}"
   touch ".eclusa/phases/${NEXT}-${SLUG}/.gitkeep"
   ```

4. **Add to ROADMAP.md** under a `## Backlog` section. If the section doesn't exist, create it at the end:

   ```markdown
   ## Backlog

   ### Phase {NEXT}: {description} (BACKLOG)

   **Goal:** [Captured for future planning]
   **Requirements:** TBD
   **Plans:** 0 plans

   Plans:
   - [ ] TBD (promote with /eclusa:review-backlog when ready)
   ```

5. **Commit:**
   ```bash
   node "$HOME/.claude/eclusa/bin/eclusa-tools.cjs" commit "docs: add backlog item ${NEXT} — ${ARGUMENTS}" --files .eclusa/ROADMAP.md ".eclusa/phases/${NEXT}-${SLUG}/.gitkeep"
   ```

6. **Report:**
   ```
   ## 📋 Backlog Item Added

   Phase {NEXT}: {description}
   Directory: .eclusa/phases/{NEXT}-{slug}/

   This item lives in the backlog parking lot.
   Use /eclusa:discuss-phase {NEXT} to explore it further.
   Use /eclusa:review-backlog to promote items to active milestone.
   ```

</process>

<notes>
- 999.x numbering keeps backlog items out of the active phase sequence
- Phase directories are created immediately, so /eclusa:discuss-phase and /eclusa:plan-phase work on them
- No `Depends on:` field — backlog items are unsequenced by definition
- Sparse numbering is fine (999.1, 999.3) — always uses next-decimal
</notes>

---
name: spec-kit
description: Orchestrate GitHub's spec-kit Spec-Driven Development pipeline. Supports GitHub and Azure DevOps repos. Claude Code authors specs/plans/code, Codex and Gemini CLI review. Trigger with "spec-kit:" prefix or commands like "spec-kit init", "spec-kit specify", "spec-kit plan", "spec-kit implement", "spec-kit status", "spec-kit resume".
---

# Spec-Kit: Spec-Driven Development Orchestrator

Orchestrate structured software development using GitHub's spec-kit toolkit. Claude Code authors all artifacts, Codex and Gemini CLI review them.

## Sub-Agent Architecture

The spec-kit pipeline involves long-running phases (authoring, reviewing, revising) that can block the chat session for 5-10+ minutes. To keep the session responsive:

### Core Principle
- **Heavy work MUST be offloaded to sub-agents** via `sessions_spawn`
- The **main session orchestrates**: reads state, sends progress messages, handles user interaction
- **Sub-agents do the work**: file I/O, CLI execution, artifact creation, review launching
- This keeps the chat responsive to new messages while pipeline work runs in the background

### What Runs Inline (Main Session)
- State reads (`spec-kit-state.json`)
- Progress messages to the user
- User gates (confirmations)
- Quick commits (`auto-commit.ps1`)
- Pipeline orchestration decisions

### What Gets Spawned (Sub-Agents)
- **AUTHOR phase** → sub-agent runs Claude Code, writes artifact, updates state (~300s timeout)
- **REVIEW phase** → sub-agent launches Codex + Gemini in parallel, saves reviews, updates state (~180s timeout)
- **AUTO-REVISE phase** → sub-agent reads reviews, applies fixes, writes revision notes, updates state (~120s timeout)

### Spawn Pattern
```
1. Main session sends progress message: "🔄 Spawning author agent for <step>..."
2. Main session calls sessions_spawn with descriptive task (see template below)
3. Sub-agent does the work and updates spec-kit-state.json when done
4. Sub-agent announces completion back to chat
5. Main session reads updated state and proceeds (or waits at user gate)
```

### sessions_spawn Task Template
Every spawned task description MUST include:
```
Task: <What to do — e.g., "Author the technical plan for feature X">
Repo: <repo_path>
Context files to read:
  - <constitution path>
  - <spec path> (if applicable)
  - <any other relevant artifacts>
Output: <where to write the artifact>
State file: memory/spec-kit-state.json
State update on completion:
  - step: <current step>
  - phase: <completed phase>
  - next_action: "<what the main session should do next>"
Review mode: <full|lite|none>
Config: <path to spec-kit-config.json>
```

## ⚡ Session Startup — Auto-Resume

**On EVERY session start** (including after gateway restart), check for in-progress work:

1. Read `memory/spec-kit-state.json`
2. For each entry in `active_features`:
   - Check `step`, `phase`, and `next_action`
   - If `next_action` is set → **that's exactly what to do next** (execute it)
   - If `phase` is NOT `done` or `user_gate` → resume from that phase
   - If `phase` is `user_gate` → remind the user and wait for confirmation
3. Report status to user: "🔄 Spec-Kit: Resuming [feature] — [next_action]"

**The `next_action` field is the single source of truth** for what happens next. Always write it when updating state.

## Pipeline Overview

```
1. INIT         → Set up spec-kit in the repo
2. CONSTITUTION → Establish project principles (per-repo)
3. SPECIFY      → Write feature spec (PRD)
4. PLAN         → Create technical implementation plan
5. TASKS        → Break plan into actionable tasks
6. IMPLEMENT    → Execute tasks (one at a time)
```

Each step follows the **Author → Review → Auto-Revise → Build/Test → Commit → Confirm** cycle.

## Trigger Patterns

| Command | Action |
|---------|--------|
| `spec-kit: <description>` | Full pipeline from specify through tasks |
| `spec-kit init <path> [--agent X]` | Initialize spec-kit in a repo |
| `spec-kit specify <description>` | Create/update feature spec |
| `spec-kit plan [tech stack]` | Generate technical plan |
| `spec-kit tasks` | Break plan into tasks |
| `spec-kit implement` | Execute all tasks |
| `spec-kit status` | Show current feature progress |
| `spec-kit resume` | Resume from last checkpoint |

## Step-by-Step Workflow

### 0. Detect & Configure

Before any step, detect the repo:
1. Read `spec-kit-config.json` from repo root (if exists)
2. If not, detect from git remote:
   - `github.com` → platform: github
   - `visualstudio.com` or `dev.azure.com` → platform: ado
3. Prompt user for missing config (build_cmd, test_cmd)
4. Save to `spec-kit-config.json`

Config schema:
```json
{
  "platform": "github|ado",
  "build_cmd": "npm run build",
  "test_cmd": "npm test",
  "lint_cmd": "npm run lint",
  "review_mode": "full|lite|none",
  "commit_prefix": "speckit"
}
```

### 1. Initialize (`spec-kit init`)

```powershell
# Install specify-cli if not present
uv tool install specify-cli --from git+https://github.com/github/spec-kit.git

# Init in the repo (always use PowerShell scripts on Windows)
specify init . --ai claude --script ps --force
```

### 2. Author-Review-Commit Cycle (for each step)

For steps that produce artifacts (specify, plan, tasks, implement):

#### Phase 1: AUTHOR (Claude Code) — via sub-agent
**Do NOT run inline.** Spawn a sub-agent to handle authoring:

1. Main session sends: "✍️ Spawning author agent for [step]..."
2. `sessions_spawn` with task:
   ```
   Author the <step> artifact for <feature>.
   Repo: <repo_path>
   Read: <constitution>, <spec> (if exists), <any prior artifacts>
   Run: claude --dangerously-skip-permissions '/speckit.<step> <args>' in <repo_path>
   Monitor the process until completion.
   When done, update memory/spec-kit-state.json:
     phase: "author"
     next_action: "Launch Codex + Gemini reviews of <artifact>"
   Announce completion to chat with artifact summary.
   ```
   Timeout: ~300s
3. Sub-agent runs Claude Code, writes the artifact, updates state, announces completion
4. Main session reads state and proceeds to review (or next phase if review_mode is `none`)

**Update state (done by sub-agent):** `phase: "author"`, `next_action: "Launch Codex + Gemini reviews of <artifact>"`

#### Phase 2: REVIEW (Codex + Gemini, parallel) — via sub-agent
Only if review_mode is `full` or `lite`. **Do NOT run inline.**

1. Main session sends: "🔍 Spawning review agent for [step]..."
2. `sessions_spawn` with task:
   ```
   Review the <step> artifact for <feature>.
   Repo: <repo_path>
   Artifact to review: <artifact_path>
   Constitution: <constitution_path>
   
   Launch BOTH reviewers in parallel:
   
   Codex:
     exec pty:true workdir:<repo_path> background:true command:"codex exec --full-auto 'Review the following artifact at <artifact_path>. Write your review to <review_path>. Focus on: completeness, correctness, edge cases, security concerns, and alignment with the constitution. Be specific — cite line numbers and suggest concrete fixes.'"
   
   Gemini:
     exec pty:true workdir:<repo_path> background:true command:"gemini 'Review the following artifact at <artifact_path>. Write your review to <review_path>. Focus on: completeness, correctness, edge cases, security concerns, and alignment with the constitution. Be specific — cite line numbers and suggest concrete fixes.'"
   
   Wait for both to complete. Capture stdout and save review files manually
   (Codex and Gemini run in read-only sandboxes and may not write files directly).
   
   When done, update memory/spec-kit-state.json:
     phase: "review"
     next_action: "Auto-revise <artifact> based on Codex/Gemini feedback"
   Announce completion with review summary (critical/major/minor counts).
   ```
   Timeout: ~180s
3. Sub-agent launches both reviewers in parallel, captures output, saves review files, updates state
4. Main session reads state and proceeds to auto-revise

**⚠️ Note:** Codex and Gemini run in read-only sandboxes — they may output reviews to stdout instead of writing files. The sub-agent must always capture their stdout and save review files manually.

**Update state (done by sub-agent):** `phase: "review"`, `next_action: "Auto-revise <artifact> based on Codex/Gemini feedback"`

#### Phase 3: AUTO-REVISE (Claude — immediate, no user gate) — via sub-agent
**This happens automatically after reviews complete.** Do NOT wait for user approval to revise. **Do NOT run inline.**

1. Main session sends: "📝 Spawning revision agent for [step]..."
2. `sessions_spawn` with task:
   ```
   Revise the <step> artifact for <feature> based on review feedback.
   Repo: <repo_path>
   Artifact: <artifact_path>
   Review files: <codex_review_path>, <gemini_review_path>
   
   Steps:
   1. Read all review files (Codex + Gemini)
   2. Triage findings by severity:
      - Critical/Major: Must address (correctness, security, architecture)
      - Minor/Suggestions: Address if they improve quality, skip stylistic nitpicks
   3. Apply revisions directly to the artifact:
      - For specs/plans: Edit the markdown directly
      - For code: Use Claude Code to fix
   4. Write revision summary to <spec_dir>/reviews/revision-notes.md with format:
      # Revision Notes — <step> (Round <N>)
      ## Addressed / ## Deferred / ## Rejected
   5. Update memory/spec-kit-state.json:
      phase: "revised"
      next_action: "Auto-commit and proceed to user gate"
   Announce completion with revision summary.
   ```
   Timeout: ~120s
3. Sub-agent reads reviews, applies fixes, writes revision notes, updates state
4. Main session reads state and proceeds to commit (inline)

**Revision summary format** (written to `<spec_dir>/reviews/revision-notes.md`):
```markdown
# Revision Notes — <step> (Round <N>)
## Addressed
- [Codex #1] Fixed psycopg3 API usage — switched from execute_values to executemany
- [Gemini #3] Added original_id index for query performance
## Deferred
- [Codex #5] COPY-based bulk insert — deferred to optimization pass (current approach correct)
## Rejected
- [Gemini #2] Suggestion to use content hashing — UUIDs already handle dedup
```

**Update state (done by sub-agent):** `phase: "revised"`, `next_action: "Auto-commit and proceed to user gate"`

**For `lite` review mode:** Same auto-revise but skip the consensus re-review (Phase 4).
**For `full` review mode:** After revising, optionally do one consensus re-review if there were critical findings (max 2 rounds). Otherwise proceed.

#### Phase 4: CONSENSUS CHECK — only if review_mode is `full` AND critical findings existed
Re-run reviewers on the revised artifact only if Round 1 had critical/major issues. If Round 2 is clean or only minor, proceed. **Max 2 review rounds total.**
**Update state:** `phase: "consensus"`, `next_action: "Commit artifacts"`

#### Phase 5: BUILD & TEST (for implementation steps)
Skip for spec/plan/tasks steps (markdown only).
```powershell
# Run from repo root
scripts/build-test.ps1 -RepoPath <path> -ConfigPath <config>
```
If fail → Claude Code fixes → re-run (max 3 attempts).
**Update state:** `phase: "build_test"`, `next_action: "Fix build failures"` or `next_action: "Commit code"`

#### Phase 6: AUTO-COMMIT — inline (no sub-agent needed)
Quick operation, runs directly in the main session.
```powershell
scripts/auto-commit.ps1 -RepoPath <path> -Step <step> -Message "<description>"
```
Commits with: `speckit(<step>): <description>`
Pushes to feature branch.
**Update state:** `phase: "committed"`, `next_action: "User gate — confirm to proceed to <next_step>"`

#### Phase 7: USER GATE — inline (no sub-agent needed)
Report results to user. Wait for confirmation before next step.
**Implementation step always requires explicit user confirmation.**
**Update state:** `phase: "user_gate"`, `next_action: "Waiting for user to confirm <next_step>"`

### 3. State Tracking

Track in `memory/spec-kit-state.json`:
```json
{
  "active_features": {
    "<repo_path>": {
      "feature": "OAuth2 authentication",
      "branch": "feature/003-oauth2-auth",
      "step": "plan",
      "phase": "review",
      "next_action": "Auto-revise plan.md based on Codex/Gemini feedback",
      "review_mode": "full",
      "spec_dir": "specs/003-oauth2-auth/",
      "platform": "github|ado",
      "started": "2026-02-03T14:51:00",
      "steps_completed": ["constitution", "specify"],
      "review_round": 1,
      "last_updated": "2026-02-03T15:30:00",
      "notes": "Codex found 3 critical issues. Gemini approved with minor suggestions."
    }
  }
}
```

**Critical fields:**
- `next_action` — **Human-readable description of the exact next thing to do.** This is what gets executed on resume. Always write this on every state update.
- `step` — Current pipeline step (init/constitution/specify/plan/tasks/implement)
- `phase` — Current phase within the step (author/review/revised/consensus/build_test/committed/user_gate/done)
- `notes` — Brief context about what happened (review results, blockers, etc.)

**Update state after EVERY phase transition.** This is what enables resume after restart.

### 4. Resume

On `spec-kit resume [repo_path]` **OR on session startup with active features**:
1. Load state from `memory/spec-kit-state.json`
2. For each active feature, read `next_action`
3. If `phase` is `user_gate` → remind user and wait
4. Otherwise → **execute `next_action` immediately**
5. Report to user what you're doing: "🔄 Resuming: [next_action]"

**Resume is automatic.** If the gateway restarts mid-pipeline, the next session picks up exactly where it left off. No user intervention needed (except at user gates).

## Review Mode Details

| Mode | Author | Review | Revise | Consensus | Speed |
|------|--------|--------|--------|-----------|-------|
| `full` | Claude | Codex + Gemini | Claude addresses | Re-review | ~15-20 min/step |
| `lite` | Claude | Codex + Gemini | Claude incorporates | Skip | ~10 min/step |
| `none` | Claude | Skip | Skip | Skip | ~5 min/step |

Default: `full` for specify/plan, `lite` for tasks, `none` for individual implement tasks (code is validated by build/test instead).

## ADO-Specific Workflows

See [references/ado-integration.md](references/ado-integration.md) for:
- Creating work items from tasks
- Creating PRs with linked work items
- Using `az boards` and `az repos` CLI

## Agent Launch Reference

See [references/agents.md](references/agents.md) for:
- Exact launch commands per agent
- Config file locations
- Slash command mappings

## Progress Reporting

When orchestrating the pipeline, keep the user informed:
1. **Start:** "🔧 Spec-Kit: Starting [step] for [repo] (review mode: [mode])"
2. **Phase transitions:** "✍️ Claude authoring plan..." / "🔍 Codex + Gemini reviewing..." / "📝 Claude revising..."
3. **Build/test:** "🏗️ Build passed ✅" or "❌ Build failed, Claude fixing (attempt 2/3)"
4. **Commit:** "📦 Committed: speckit(plan): technical plan for OAuth2 auth"
5. **Gate:** "⏸️ Ready for next step. Review [artifact] and confirm to proceed."

## Important Rules

1. **Claude always authors.** Codex and Gemini only review.
2. **Never auto-implement.** Always confirm with user before implementation step.
3. **Always track state with `next_action`.** Update `spec-kit-state.json` after every phase transition. The `next_action` field must always describe exactly what to do next in human-readable terms.
4. **Auto-revise after reviews.** Don't wait for user approval to incorporate review feedback. Use best judgment: address critical/major findings, note deferred items, reject suggestions that conflict with design decisions.
5. **User gate only at step boundaries.** The user confirms transitions between major steps (specify→plan, plan→tasks, tasks→implement), NOT between phases within a step.
6. **Build/test before commit.** Code changes must pass.
7. **Per-repo constitution.** Don't share constitutions across repos.
8. **Use PTY mode** for all coding agent processes.
9. **Don't run agents in the clawd workspace.** Always use the target repo's directory.
10. **Resume on startup.** Always check `spec-kit-state.json` when starting a session. If there's active work, resume it (or remind user if at a gate).
11. **Always use `sessions_spawn` for heavy phases.** Author, review, and revise phases involve multiple tool calls and long-running processes — they MUST be offloaded to sub-agents. Never run these inline in the main chat session.
12. **Keep inline only lightweight operations.** State reads, progress messages, user gates, quick commits, and orchestration decisions stay in the main session. Everything else goes to a sub-agent.
13. **Sub-agent timeouts.** Use ~300s for authoring, ~180s for reviews, ~120s for revisions. If a sub-agent times out, update state with a note and retry or ask the user.

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
- **AUTO-REVISE phase** → sub-agent reads reviews, applies fixes, writes revision notes, updates state (~120s timeout)

### What Runs as Direct Exec (NOT Sub-Agents)
- **REVIEW phase** → Codex and Gemini CLIs launched directly via `exec background:true` from main session
- ⚠️ **NEVER delegate review launching to sub-agents** — they are Claude instances that may write fake reviews instead of running the external tools

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

Each step follows the **Author → Review (with Flow Trace) → Auto-Revise → Build/Test → Visual Verification → Commit → Confirm** cycle.

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

#### Phase 2: REVIEW (Codex + Gemini, parallel) — DIRECT EXEC, NOT sub-agents
Only if review_mode is `full` or `lite`.

⚠️ **CRITICAL:** Reviews MUST be performed by the actual external CLI tools (Codex, Gemini). **NEVER delegate review launching to sub-agents** — sub-agents are Claude instances that may write reviews themselves instead of running the external tools. This produces fake reviews that defeat the purpose of multi-model review.

**Flow Trace (mandatory for implementation reviews):**
The reviewer (Arc or whoever reviews) must include a "Flow Trace" section that traces the primary user journey through the code, click by click:
- User action → event handler → API call → backend processing → state update → response → frontend re-render
- Document each link in the chain. If any link is missing, unclear, or disconnected (e.g., no orchestration layer wiring components together) → flag as **Critical**.
- If the reviewer cannot run the app, explicitly state: **"Needs manual verification — I reviewed code paths only"** instead of approving outright.

Run reviews as direct `exec background:true` calls from the main session:

1. Main session sends: "🔍 Launching Codex + Gemini reviews..."
2. Launch BOTH reviewers in parallel using exec:

   **Codex** (use `--full-auto` for unattended, `-c reasoning_effort="xhigh"` for deepest analysis):
   ```
   exec pty:true workdir:<repo> background:true timeout:900 command:"codex --model gpt-5.3-codex -c reasoning_effort=\"xhigh\" --full-auto 'Review the artifact at <path>. Read the project constitution at <constitution>. Write your review to <review_path>. Focus on: completeness, correctness, edge cases, security, and constitution alignment. Be specific — cite line numbers. Rate findings as Critical/High/Medium/Low.'"
   ```

   **Gemini** (use `--yolo` to auto-approve all file writes and shell commands):
   ```
   exec pty:true workdir:<repo> background:true timeout:900 env:{"PATH":":/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"} command:"gemini --model gemini-3-pro-preview --yolo 'Review the artifact at <path>. Read the project constitution at <constitution>. Write your review to <review_path>. Focus on: completeness, correctness, edge cases, security, and constitution alignment. Be specific — cite line numbers. Rate findings as Critical/High/Medium/Low.'"
   ```

3. Poll both sessions periodically (`process log`) to monitor progress
4. When both complete, verify review files exist:
   ```
   exec command:"wc -l <review_paths>"
   ```
5. If a reviewer failed to write its file (e.g., wrote to stdout instead), capture the terminal log and save it manually. But **NEVER write a review yourself** pretending it came from another model.
6. If a reviewer's model is unavailable or errors out, report the failure to the user and ask how to proceed (retry with different model, skip that reviewer, etc.)

**Handling Gemini interactive prompts:** If Gemini gets stuck on approval prompts despite `--yolo`, use process send-keys to approve:
```
process action:send-keys sessionId:<id> keys:["Down", "Return"]
```

**Update state:** `phase: "review"`, `next_action: "Auto-revise <artifact> based on Codex/Gemini feedback"`

### 🚫 Anti-Fake Review Rule

Claude (in any form — main session, sub-agent, or spawned task) must **NEVER** write a review and attribute it to Codex or Gemini. If an external reviewer fails, the correct action is:
1. Report the failure to the user
2. Offer to retry with a different model or skip that reviewer
3. If skipping, note in the revision that only one reviewer was used

**Fabricating reviews destroys the value of multi-model review and is always wrong.**

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

#### Phase 5.5: VISUAL VERIFICATION (mandatory for user-facing implementation steps)

**This phase is non-negotiable.** It exists because passing tests alone proved insufficient — the Arena postmortem (2026-02) showed that 620+ tests could pass while the core feature was fundamentally non-functional.

**Implementer must:**
1. Run the full stack (not mocked, not headless)
2. Manually walk through the core user journey as defined in the spec
3. Capture evidence: screenshots or short screen recording of the feature working in a real browser
4. Post evidence to the review channel/PR

**Definition of Working checklist** (all must be YES before proceeding):
- [ ] App starts cleanly on a fresh/clean database
- [ ] Core user journey works end-to-end (as defined in spec)
- [ ] No raw template strings, unrendered markup, or placeholder data visible in UI
- [ ] User inputs handled realistically (numeric formats, units, typos, edge values)
- [ ] Data flows through the full pipeline (not just individual components in isolation)
- [ ] State transitions are driven by actual orchestration (not manually triggered or mocked)
- [ ] Visual evidence captured and posted

**If any checkbox fails → fix before proceeding. Do not commit incomplete work.**

**If the implementer cannot run the full stack** (e.g., no Docker), they must explicitly flag this and request manual verification from someone who can. This is NOT a skip — it's a delegation.

**Update state:** `phase: "visual_verify"`, `next_action: "Post visual evidence and proceed to commit"`

**E2E Test Quality Gate:**
Before visual verification, confirm that E2E tests meet these standards:
- Every E2E test starts with a user story: "As a [role], I [action], and I see [outcome]"
- Tests run against the full stack through the actual UI (not direct API calls)
- Assertions check **visible outcomes** (rendered text, UI state), not just API responses or DOM existence
- At least one test uses realistic user input (e.g., "3.50" not just "3.5", "$5" not just "5")
- **Anti-pattern to reject:** Tests that hit API endpoints directly and assert on JSON responses are integration tests, not E2E. Label them correctly — they cannot substitute for real E2E validation.

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

**For implementation steps, the gate message must include:**
1. Summary of what was implemented
2. Link to visual verification evidence (screenshots/recording)
3. Specific smoke test steps for the user (derived from the spec's user journey), e.g.:
   - "Start the app, navigate to Arena, click 'Find Match'"
   - "Answer 3 questions, verify scores update"
   - "Complete the match, confirm results screen shows"
4. ⚠️ If no visual verification was performed (e.g., implementer couldn't run full stack), explicitly warn: **"Visual verification was not performed — manual testing is critical before proceeding."**

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
11. **Use `sessions_spawn` for AUTHOR and REVISE phases only.** These involve Claude doing heavy file I/O and are safe to delegate to sub-agents.
12. **REVIEW phase runs as direct exec from main session.** NEVER delegate review launching to sub-agents. Sub-agents are Claude instances that may write reviews themselves instead of running external tools. Launch Codex and Gemini CLIs directly via `exec background:true` and poll their progress.
13. **NEVER fake a review.** Claude must never write a review and attribute it to Codex, Gemini, or any other model. If an external reviewer fails, report the failure and ask the user how to proceed. Fabricating reviews is always wrong.
14. **Keep inline only lightweight operations.** State reads, progress messages, user gates, quick commits, and orchestration decisions stay in the main session.
15. **Timeouts.** Use ~300s for authoring sub-agents, ~120s for revision sub-agents, and **~1800s for review exec sessions** (Codex/Gemini xhigh can take 10-15+ minutes on complex artifacts). If a process times out, retry with a longer timeout or ask the user. Previous 900s timeout was insufficient — reviews consistently took 12-18 minutes.
16. **Visual verification before commit.** Any implementation step that produces user-facing changes MUST include visual proof (screenshots/recording) of the feature working in a real browser on a clean database. Passing tests alone is insufficient — this was learned the hard way (Arena postmortem, 2026-02). The implementer provides evidence; the reviewer confirms it matches the spec.
17. **Pre-merge smoke test prompt.** The user gate message for implementation steps must include specific steps for a 2-minute manual smoke test (derived from the spec's user journey), link to visual verification evidence, and explicitly ask the user to confirm they've tested it before proceeding.

## Windows-Specific Notes

### Codex CLI on Windows
- **Model**: Use `gpt-5.3-codex` (requires codex-cli ≥0.101.0). Run `npm update -g @openai/codex` if model not found.
- **Sandbox prompt**: First run shows "Set Up Agent Sandbox" interactive prompt that blocks `--full-auto`. Select option 2 "Stay in Read-Only" via `send-keys: ["Down", "Return"]`. Persists after first acceptance.
- **Read-Only mode**: Codex in read-only will ask "Would you like to run the following command?" before writing files. Approve via `send-keys: ["Return"]`.
- **Bypass all prompts**: Use `codex --dangerously-bypass-approvals-and-sandbox -c reasoning_effort="xhigh" "prompt"` to skip sandbox + approval prompts entirely. Only safe in contained VMs. This is the **preferred mode for review runs** on Arc's VM.
- **Auth**: Works with ChatGPT Plus subscription (chatgpt auth mode). No `OPENAI_API_KEY` needed.
- **PowerShell**: Use `;` not `&&` to chain commands.

### Gemini CLI on Windows
- **Trust prompt**: First run in a new directory shows "Do you trust this folder?" prompt. Select option 1 via `send-keys: ["Return"]`. After accepting, Gemini restarts and loses the original command — must re-send the prompt.
- **`--yolo` flag**: Works correctly after folder trust is established.
- **Auth**: Google OAuth via `gemini auth login`.

### General Windows Tips
- **Run Codex and Gemini sequentially** (one at a time) on Windows VMs. Parallel runs hit the exec timeout faster and both get killed. Running sequentially is more reliable.
- **SIGKILL is usually timeout, NOT OOM.** Check `process list` — if both sessions show the same runtime (e.g., 15m1s), it's the exec timeout. Bump timeout to 1800s for complex reviews. Always verify system memory (`systeminfo`) before assuming OOM.
- Sub-agents spawned via `sessions_spawn` may fail to write files on Windows. For authoring/revision, prefer inline execution in main session if sub-agents fail twice.
- Delete `~/.codex/models_cache.json` after updating codex-cli to refresh available models.

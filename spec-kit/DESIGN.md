# Spec-Kit Skill — Design Draft

**Date:** 2026-02-03
**Author:** Aibot + Jason
**Status:** Draft

---

## Overview

An OpenClaw skill that integrates GitHub's [spec-kit](https://github.com/github/spec-kit) Spec-Driven Development toolkit. Enables the bot to orchestrate structured software development workflows — from spec writing through implementation — using any supported coding agent (Claude Code, Codex, Copilot, Gemini CLI) against GitHub or Azure DevOps repositories.

## Problem

Today, kicking off structured development with spec-kit requires:
1. Manually running `specify init` in the right repo
2. Launching a specific coding agent
3. Running slash commands in sequence
4. Manually tracking progress across features

This skill lets Jason say: *"spec-kit: build a caching layer for RgManager"* from Discord and have the bot handle the full pipeline.

## User Experience

### Trigger Phrases
- `spec-kit: <description>` — Full pipeline (init → specify → plan → tasks → implement)
- `spec-kit init <repo> [--agent claude|codex|copilot|gemini]` — Initialize spec-kit in a repo
- `spec-kit specify <description>` — Create/update feature spec only
- `spec-kit plan` — Generate technical plan from current spec
- `spec-kit tasks` — Break plan into tasks
- `spec-kit implement` — Execute all tasks
- `spec-kit status` — Show current feature progress

### Example Flow

```
Jason: spec-kit: add OAuth2 authentication to MyTutor API

Bot: 🔧 Spec-Kit: Starting SDD pipeline for MyTutor
     📁 Repo: Q:\src\Personal\MyTutor
     🤖 Agent: Claude Code (default)
     
     Step 1/5: Creating feature branch...
     ✅ Branch: feature/003-oauth2-auth
     
     Step 2/5: Generating specification...
     [spawns coding agent subagent]
     ✅ Spec written to specs/003-oauth2-auth/spec.md
     
     Step 3/5: Creating technical plan...
     ✅ Plan written to specs/003-oauth2-auth/plan.md
     
     Step 4/5: Breaking into tasks...
     ✅ 8 tasks created in specs/003-oauth2-auth/tasks.md
     
     Step 5/5: Ready to implement.
     
     📋 Tasks:
     1. Set up OAuth2 provider config
     2. Create auth middleware
     3. Implement token refresh logic
     ...
     
     Run `spec-kit implement` to execute, or review the plan first.
```

## Architecture

### Skill Structure
```
spec-kit/
├── SKILL.md                      # Main skill instructions
├── scripts/
│   ├── init.ps1                  # Initialize spec-kit in a repo
│   ├── run-pipeline.ps1          # Orchestrate full SDD pipeline
│   └── status.ps1                # Check feature progress
├── references/
│   ├── agents.md                 # Agent-specific config (claude, codex, copilot, gemini)
│   ├── ado-integration.md        # ADO-specific workflows (PRs, work items)
│   └── github-integration.md     # GitHub-specific workflows (issues, PRs)
└── assets/
    └── templates/
        ├── constitution-default.md   # Default project constitution
        └── ado-tasks-template.md     # ADO work item template
```

### How It Works

#### 1. Initialization (`spec-kit init`)
- Detects repo type (GitHub vs ADO) from git remote
- Runs `specify init <repo> --ai <agent> --script ps`
- Applies any project-specific constitution from memory
- Stores repo config in `spec-kit-config.json` at workspace root

#### 2. Agent Orchestration
The skill spawns coding agents as background processes:

| Agent | How It's Launched | Config Location |
|-------|-------------------|-----------------|
| Claude Code | `claude --dangerously-skip-permissions` | `.claude/commands/` |
| Codex | `codex --dangerously-skip-permissions` | `codex-instructions.md` |
| Copilot | `code --` (VS Code CLI) | `.github/copilot-instructions.md` |
| Gemini CLI | `gemini` | `.gemini/commands/` |

The bot uses the **coding-agent skill** to manage these as background PTY processes, feeding them the appropriate `/speckit.*` commands.

#### 3. Pipeline Steps
Each step is a coding agent interaction:

```
[Bot receives request]
  → init.ps1 (setup spec-kit if needed)
  → spawn agent with /speckit.constitution (if no constitution exists)
  → spawn agent with /speckit.specify "<description>"
  → spawn agent with /speckit.plan "<tech stack>"  
  → spawn agent with /speckit.tasks
  → [pause for review]
  → spawn agent with /speckit.implement
```

Between steps, the bot:
- Reads generated artifacts (spec.md, plan.md, tasks.md)
- Reports progress to Discord
- Allows Jason to intervene/modify before continuing

#### 4. Platform Integration

**GitHub repos:**
- Creates feature branches
- Can convert tasks to GitHub Issues (`/speckit.taskstoissues`)
- Creates PRs when implementation is done

**ADO repos:**
- Creates feature branches
- Converts tasks to ADO Work Items via `az boards` CLI
- Creates PRs via `az repos` CLI
- Links work items to PRs

### Agent Selection Logic

```
1. If --agent specified → use that
2. If repo has .claude/ → Claude Code
3. If repo has .github/copilot-instructions.md → Copilot
4. If repo has .gemini/ → Gemini CLI
5. Default → Claude Code
```

### State Tracking

Track active features in `memory/spec-kit-state.json`:
```json
{
  "active_features": {
    "Q:\\src\\Personal\\MyTutor": {
      "branch": "feature/003-oauth2-auth",
      "step": "tasks",
      "agent": "claude",
      "spec_dir": "specs/003-oauth2-auth/",
      "started": "2026-02-03T14:51:00",
      "platform": "github"
    }
  }
}
```

## Key Design Decisions

### 1. Pause Before Implement
Always pause after task generation and show tasks before auto-implementing. This gives Jason a chance to review and modify the plan.

### 2. Agent-Agnostic Core
The pipeline logic is the same regardless of agent. Only the launch command and config paths change. This makes it easy to add new agents.

### 3. ADO First-Class Support
Since Jason works with ADO (RgManager), ADO isn't an afterthought:
- Work item creation from tasks
- ADO PR creation with linked work items
- PAT-based auth using existing `AZURE_DEVOPS_EXT_PAT`

### 4. Incremental Adoption
Can use individual commands (`spec-kit specify`, `spec-kit plan`) without running the full pipeline. Also works on repos that already have spec-kit initialized.

## Dependencies

- `specify-cli` (installed via `uv tool install specify-cli --from git+https://github.com/github/spec-kit.git`)
- At least one coding agent (Claude Code, Codex, Copilot CLI, or Gemini CLI)
- `az` CLI (for ADO integration)
- OpenClaw coding-agent skill (for background agent management)

## Resolved Design Decisions

### Multi-Agent Review Pipeline
Claude Code is **always the author** for spec, plan, and implementation. Codex and Gemini CLI serve as **reviewers** bringing different perspectives.

**Pipeline per step:**
```
Phase 1: AUTHOR
  └── Claude Code writes the artifact (spec.md, plan.md, etc.)

Phase 2: REVIEW (parallel)
  ├── Codex CLI reviews → review-codex.md
  └── Gemini CLI reviews → review-gemini.md

Phase 3: REVISE
  └── Claude Code reads all reviews, addresses feedback, updates artifact

Phase 4: CONSENSUS CHECK
  ├── All reviewers approve → ✅ proceed
  └── Disagreements → one more review round (max 2 rounds)

Phase 5: BUILD & TEST
  ├── Run repo-specific build command
  ├── Run repo-specific test command
  ├── Pass → auto-commit artifact to feature branch
  └── Fail → Claude Code fixes, re-run (max 3 attempts)

Phase 6: USER GATE
  └── User confirms → next step
```

**Review modes (configurable):**
- `--review full` — Author → Review → Revise → Consensus (thorough, ~15-20 min/step)
- `--review lite` — Claude authors, reviewers comment, Claude incorporates without re-review (faster, ~10 min/step)
- `--review none` — Claude only, no review (quick prototyping, ~5 min/step)

**Artifacts per step:**
```
specs/003-feature-name/
├── spec.md                    # The spec (authored by Claude)
├── plan.md                    # Technical plan (authored by Claude)
├── tasks.md                   # Task breakdown (authored by Claude)
├── reviews/
│   ├── spec-review-codex.md   # Codex's review of the spec
│   ├── spec-review-gemini.md  # Gemini's review of the spec
│   ├── plan-review-codex.md
│   ├── plan-review-gemini.md
│   └── consensus.md           # Summary of agreements/disagreements
└── constitution.md            # Per-repo project principles
```

### Implementation Confirmation
Always require user confirmation before `/speckit.implement`. No `--auto` flag for implementation.

### Progress Tracking & Resume
Track state in `memory/spec-kit-state.json`:
```json
{
  "active_features": {
    "Q:\\src\\Personal\\MyTutor": {
      "branch": "feature/003-oauth2-auth",
      "step": "plan",
      "phase": "review",
      "review_mode": "full",
      "agent": "claude",
      "reviewers": ["codex", "gemini"],
      "spec_dir": "specs/003-oauth2-auth/",
      "started": "2026-02-03T14:51:00",
      "platform": "github",
      "steps_completed": ["constitution", "specify"],
      "review_round": 1
    }
  }
}
```

Resume from any point: `spec-kit resume <repo>` picks up from last completed phase.

### Build & Test Gate
Every step that produces code changes must pass the repo's build and test commands before proceeding. On pass, changes are auto-committed to the feature branch.

**Per-repo config in `spec-kit-config.json`:**
```json
{
  "repo": "Q:\\src\\Personal\\MyTutor",
  "platform": "github",
  "build_cmd": "npm run build",
  "test_cmd": "npm test",
  "lint_cmd": "npm run lint",
  "commit_prefix": "speckit",
  "default_review_mode": "full"
}
```

**How it works:**
1. After Claude completes a step (e.g., implement task 3)
2. Run `build_cmd` → if fail, Claude fixes and retries (max 3 attempts)
3. Run `test_cmd` → if fail, Claude fixes and retries (max 3 attempts)
4. Run `lint_cmd` (optional) → same retry logic
5. All pass → auto-commit with message: `speckit: [step] - [description]`
6. Push to feature branch

**For spec/plan steps** (no code changes): Skip build/test, just auto-commit the markdown artifacts.

**Commit messages follow a pattern:**
```
speckit(specify): add OAuth2 authentication spec
speckit(plan): technical plan for OAuth2 auth
speckit(tasks): break down into 8 implementation tasks
speckit(implement): task 1 - setup OAuth2 provider config
speckit(implement): task 2 - create auth middleware
speckit(review): address Codex/Gemini feedback on plan
```

### Constitution
Per-repo. Stored in the repo's `memory/constitution.md` (spec-kit default location). Each repo defines its own principles, tech stack constraints, and quality standards.

### Architecture
Separate subagents per step (Option B). Each pipeline step is an independent subagent that reads/writes files to disk. Enables:
- Multi-agent review (parallel subagents)
- Natural checkpoints for user confirmation
- Resumability from any step
- Different agents per role (Claude authors, others review)

---

*Design approved. Ready for implementation.*

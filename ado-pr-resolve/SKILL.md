---
name: ado-pr-resolve
description: Resolve active PR comments on Azure DevOps pull requests using a multi-model AI council. Fetches active review threads, analyzes each with Claude Opus 4.5, Codex 5.2, and Gemini Pro 3, presents consensus fixes for user approval, then applies changes and resolves threads on ADO.
---

# Azure DevOps PR Comment Resolver

Resolve active review comments on ADO pull requests using multi-model AI analysis. Each comment is analyzed by 3 models, a consensus fix is proposed, and upon user approval the fix is applied, the thread is replied to, and marked resolved.

## Trigger Patterns

- "resolve pr comments {URL}"
- "fix pr comments {URL}"
- "ado resolve {URL}"
- Pasting an ADO PR URL with context about resolving/fixing comments

## Quick Start

1. Parse PR URL → extract org, project, repo, prId
2. Authenticate via `az login` + token
3. Fetch active comment threads from ADO API
4. Checkout PR source branch locally
5. For each active comment → spawn sub-agent for multi-model analysis
6. Present AI council assessment with inline action buttons
7. On user approval → apply fix **locally only** (do NOT resolve on ADO yet)
8. After all comments → build & test to verify fixes
9. Commit & push (with user confirmation)
10. Reply to ADO threads & mark resolved (only after push succeeds)

## URL Formats

```
https://dev.azure.com/{org}/{project}/_git/{repo}/pullrequest/{prId}
https://{org}.visualstudio.com/{project}/_git/{repo}/pullrequest/{prId}
```

Extract: `org`, `project`, `repo`, `prId`

## Models

| Model | Flag | Role |
|-------|------|------|
| Claude Opus 4.5 | `--model claude-opus-4.5` | Deep reasoning, nuanced analysis |
| Codex 5.2 | `--model gpt-5.2-codex` | Code-focused, practical fixes |
| Gemini Pro 3 | `--model gemini-3-pro-preview` | Broad coverage, alternative perspective |

## Authentication

```bash
# Check login
az account show

# Get access token for Azure DevOps
TOKEN=$(az account get-access-token --resource 499b84ac-1321-427f-aa17-267ca6975798 --query accessToken -o tsv)
```

## Workflow

### 1. Parse PR URL

Extract components from the URL. Support both `dev.azure.com` and `visualstudio.com` formats.

### 2. Authenticate & Fetch PR Details

```bash
# Get PR metadata (source branch, target branch, title)
curl -s "https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repo}/pullrequests/{prId}?api-version=7.1" \
  -H "Authorization: Bearer $TOKEN"
```

### 3. Fetch Active Threads

```bash
curl -s "https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repo}/pullRequests/{prId}/threads?api-version=7.0" \
  -H "Authorization: Bearer $TOKEN"
```

**Filter criteria:**
- `status === "active"` only (skip resolved, closed, byDesign, wontFix, pending)
- Skip system-generated threads (no `threadContext`, or `isDeleted` comments)
- Skip threads where all comments are from the PR author (self-comments)

**Extract per thread:**
- `threadId`
- First comment text + all reply comments (full thread context)
- `threadContext.filePath`
- `threadContext.rightFileStart.line` / `rightFileEnd.line`
- Comment author display name

### 4. Set Up Git Worktree

**Always use a git worktree** — never checkout in the main repo directory. This avoids disrupting the user's working directory.

```bash
# From the main repo directory
cd {repoPath}

# Create a worktree for resolving this PR
git fetch origin {sourceBranch}
git worktree add ../resolve-pr-{prId} origin/{sourceBranch}

# All subsequent work happens in the worktree
cd ../resolve-pr-{prId}
```

**Worktree path:** `{repoParentDir}/resolve-pr-{prId}` (sibling of the main repo)

Example: If repo is at `Q:\src\Prelude\RgManager`, worktree goes to `Q:\src\Prelude\resolve-pr-12345`.

**Cleanup:** After all comments are resolved and pushed, remove the worktree:
```bash
cd {repoPath}
git worktree remove ../resolve-pr-{prId}
```

Ask user before cleanup — they may want to keep it for further inspection.

### 5. Per-Comment Multi-Model Analysis

For **each** active comment thread, spawn a sub-agent that:

#### a) Prepare Context File

Gather the comment thread into a context file that gets passed to each model:

```bash
# Save to a context file (models will also explore the codebase themselves)
cat > {worktreePath}/tmp_resolve_context_{threadId}.txt << 'EOF'
## PR Review Comment to Resolve

Thread by {author}: "{comment_text}"
{all replies in the thread, with authors}

Commented on file: {filePath}, lines {startLine}-{endLine}
Target branch: {targetBranch}
EOF
```

#### b) Query 3 Models in Parallel — with FULL Codebase Access

**Critical:** Models must run **inside the worktree directory** with tool access enabled so they can explore the full codebase — read related files, follow includes/imports, understand class hierarchies, check callers/callees, etc. Do NOT just feed them a snippet.

Each model gets the same prompt but runs with `--allow-all-tools` in the worktree so it can navigate the code:

```bash
# Save prompt to file
cat > /tmp/resolve_prompt_{threadId}.txt << 'PROMPT'
You are resolving a code review comment on a pull request.
The full codebase is available in your working directory — USE IT.

## Review Comment
{paste context from tmp_resolve_context_{threadId}.txt}

## Your Task
1. Read the commented file ({filePath}) — the FULL file, not just a snippet
2. **Explore the codebase** to understand the broader context:
   - Read related files (headers, imports, base classes, interfaces)
   - Check how the commented code is called/used elsewhere
   - Look at similar patterns in the codebase for consistency
   - Check tests related to this code
3. Understand what the reviewer is asking for
4. Assess if the comment is valid given the full context
5. Propose a concrete code fix that is consistent with the rest of the codebase
6. If you disagree with the reviewer, explain why with evidence from the codebase

Also run: git diff origin/{targetBranch}...HEAD -- {filePath}
to see what changed in this PR for the file.

Output format:
ASSESSMENT: <valid|partially_valid|disagree>
EXPLANATION: <what the reviewer wants and why>
FILES_REVIEWED: <list of files you read to understand the context>
FIX:
```before
<original code>
```
```after
<fixed code>
```
REASONING: <why this fix is correct, referencing codebase patterns/conventions you observed>
PROMPT
```

Run all models **from the worktree directory** so they have automatic access to the full codebase:
```bash
cd {worktreePath}

# Claude Opus 4.5
copilot --model claude-opus-4.5 --allow-all-tools --no-ask-user \
  -p "$(cat /tmp/resolve_prompt_{threadId}.txt)" > /tmp/resolve_opus_{threadId}.txt 2>&1 &

# Codex 5.2
copilot --model gpt-5.2-codex --allow-all-tools --no-ask-user \
  -p "$(cat /tmp/resolve_prompt_{threadId}.txt)" > /tmp/resolve_codex_{threadId}.txt 2>&1 &

# Gemini Pro 3
copilot --model gemini-3-pro-preview --allow-all-tools --no-ask-user \
  -p "$(cat /tmp/resolve_prompt_{threadId}.txt)" > /tmp/resolve_gemini_{threadId}.txt 2>&1 &

wait
```

**Note:** Copilot CLI grants models file access to the working directory by default. Running from the worktree means all models can explore the full codebase. Use `--add-dir` only if models need access to directories outside the worktree.

**Why full codebase access matters:**
- A reviewer comment about "use RAII here" makes more sense when the model can see the project's existing RAII patterns
- "This should be thread-safe" requires understanding the threading model used elsewhere
- "Consider using the existing utility" requires finding that utility in the codebase
- Fixes that don't match codebase conventions look out of place in review

#### c) Consolidate Results

- Parse each model's ASSESSMENT, EXPLANATION, FILES_REVIEWED, FIX, and REASONING
- **If 2-3 models agree** on the fix → consensus fix, confidence: **HIGH**
- **If all models differ** → present all perspectives, confidence: **MEDIUM**
- Note which files each model explored — broader exploration = higher confidence
- Write consolidated result to `/tmp/resolve_result_{threadId}.json`

### 6. Present to User

For each comment, present inline:

```
📝 Comment #{n} by {author} on {file}:{line}
> "{comment text}"

🤖 AI Council Assessment (confidence: HIGH):

**What they want:** {explanation}

**Proposed fix:**
```diff
- old code
+ new code
```

**Model breakdown:**
- Claude: {assessment} — {brief reasoning}
- Codex: {assessment} — {brief reasoning}
- Gemini: {assessment} — {brief reasoning}
```

**Telegram inline buttons:**
- ✅ Apply fix → applies code change **locally only** (stages the file, does NOT resolve on ADO yet)
- 💬 Discuss → enter discussion loop for this comment
- ⏭️ Skip → move to next comment
- ✏️ Edit fix → user provides modified fix, then apply locally

### 6b. Discussion Loop (per-comment)

When the user taps 💬 Discuss, enter a **per-comment discussion loop**:

1. User asks questions, raises concerns, or requests alternative approaches
2. Re-query models if needed (spawn sub-agent) with updated context:
   - Include original comment + previous model analysis + user's follow-up
   - Models run again **in the worktree** with full codebase access (same as step 5b)
   - User's feedback may direct models to look at specific files or patterns
   - Models provide updated analysis/fix based on deeper exploration
3. Present updated fix proposal
4. Show buttons again: ✅ Apply | 💬 Discuss more | ⏭️ Skip | ✏️ Edit

**This loop continues until the user either applies a fix, edits and applies, or skips.**

The user can go back and forth as many times as needed on a single comment. Don't rush — the goal is getting the right fix, not speed.

**Example flow:**
```
Bot: 📝 Comment #3 — "This allocation is unnecessary"
     Proposed fix: use string_view instead
     [✅ Apply] [💬 Discuss] [⏭️ Skip] [✏️ Edit]

User: [💬] wouldn't string_view be dangerous here since the source string could go out of scope?

Bot: Good point! Let me re-check...
     🤖 Updated analysis: Claude and Codex now agree — keep std::string but use reserve() to avoid reallocation.
     Updated fix: {new diff}
     [✅ Apply] [💬 Discuss] [⏭️ Skip] [✏️ Edit]

User: [✅ Apply]
Bot: ✅ Applied locally. Moving to comment #4...
```

### 7. Apply Fix Locally (on user approval)

Apply the fix **locally only** — do NOT resolve on ADO yet.

```bash
# Apply the code change to the local file
# Use precise text replacement (Edit tool or sed)

# Stage the change
git add {filePath}
```

Track which threads had fixes applied in `memory/pr-resolve-state.json` (status: "applied").

**Repeat steps 5–7 (including 6b discussion loop) for each active comment before proceeding to build & test.**

### 8. Build & Test

After all comments have been addressed (applied or skipped), verify the fixes don't break anything.
**Run from the worktree directory:**

```bash
cd {worktreePath}  # e.g., Q:\src\Prelude\resolve-pr-12345

# Run build (use repo's build command from spec-kit-config.json or ask user)
{build_cmd}

# Run tests
{test_cmd}
```

- **If build/test passes** → proceed to commit
- **If build/test fails** → show the error, let user decide:
  - Fix the issue (re-analyze with models if needed)
  - Revert specific changes
  - Proceed anyway (user's call)

**Do NOT commit or resolve ADO threads if build/test fails** unless user explicitly overrides.

### 9. Commit & Push

After build & test passes. **Run from the worktree directory:**

```bash
cd {worktreePath}
git add -A
git commit -m "Address PR review comments"

# Always ask user before pushing
# "Push changes to remote?"
git push origin HEAD:{sourceBranch}
```

### 10. Reply & Resolve on ADO

**Only after push succeeds**, batch-resolve all applied threads:

For each thread with status "applied":

**Reply to thread with a detailed, polite explanation:**

The reply MUST include:
- **What was changed** — concrete description of the code change
- **Why** — how it addresses the reviewer's concern
- **Where** — file and line reference if helpful
- **Gratitude** — thank the reviewer for catching the issue

**Tone guidelines:**
- Always polite and respectful: "Thank you for catching this", "Good point", "Great suggestion"
- Acknowledge the reviewer's insight: "You're right that..." / "Agreed, this was an oversight"
- Be specific, not vague: say exactly what changed, not just "Fixed"
- If the fix differs from what the reviewer suggested, explain the reasoning respectfully

**Reply template:**
```
Thanks for flagging this! You're right that {what was wrong}.

Fixed by {specific change — e.g., "adding a null check before the dereference" or "switching from `std::string` to `std::string_view` to avoid the copy"}.

{Optional: if the approach differs from the reviewer's suggestion}
I went with {approach} instead of {reviewer's suggestion} because {reason} — happy to discuss if you'd prefer a different approach.
```

```bash
curl -s -X POST \
  "https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repo}/pullRequests/{prId}/threads/{threadId}/comments?api-version=7.0" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d @/tmp/reply_{threadId}.json
```

**Mark thread as fixed:**
```bash
curl -s -X PATCH \
  "https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repo}/pullRequests/{prId}/threads/{threadId}?api-version=7.0" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status": "fixed"}'
```

Report summary: "✅ Resolved {n} threads on ADO, skipped {m}."

## Important Rules

1. **Never auto-resolve** — every comment needs explicit user approval
2. **Sub-agents for heavy work** — model queries run in sub-agents, chat stays responsive
3. **One comment at a time** — present, discuss, apply locally, then move to next
4. **Preserve thread context** — read the FULL thread (all replies), not just the first comment
5. **Always show model disagreements** — if models differ, show all perspectives
6. **ADO API for thread operations** — use REST API (`az repos pr` CLI doesn't have thread commands)
7. **User can discuss** — allow back-and-forth before deciding on a fix
8. **Build & test before commit** — verify all fixes pass build/test before committing
9. **Batch commit** — accumulate all local fixes, single commit at the end
10. **ADO resolution only after push** — reply to threads and mark resolved ONLY after code is pushed successfully
11. **Ask before pushing** — never push without explicit user confirmation
12. **Always use git worktree** — never checkout in the main repo; create a sibling worktree at `{repoParent}/resolve-pr-{prId}`
13. **Clean up worktree** — after resolution is complete, ask user before removing the worktree

## State Tracking

Track progress in `memory/pr-resolve-state.json`:

```json
{
  "active_pr": {
    "url": "https://dev.azure.com/...",
    "org": "msdata",
    "project": "Database Systems",
    "repo": "RgManager",
    "prId": 12345,
    "branch": "feature/xyz",
    "repoPath": "Q:\\src\\Prelude\\RgManager",
    "worktreePath": "Q:\\src\\Prelude\\resolve-pr-12345",
    "threads": [
      {
        "threadId": 100,
        "status": "pending|applied|skipped",
        "file": "/src/file.cpp",
        "line": 42,
        "comment": "...",
        "fix_applied": null
      }
    ],
    "current_thread_index": 0
  }
}
```

Update this state after each comment is processed so progress survives session interruptions.

## Detailed References

- [API-REFERENCE.md](references/API-REFERENCE.md) — Azure DevOps REST API endpoints
- [RESOLVE-WORKFLOW.md](references/RESOLVE-WORKFLOW.md) — Detailed workflow, edge cases, error handling

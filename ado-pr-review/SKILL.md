---
name: ado-pr-review
description: Multi-model PR review for Azure DevOps using Copilot CLI. Runs the same review with multiple AI models (Opus 4.5, Codex 5.2, Gemini Pro 3) for comprehensive coverage. Consolidates findings and posts to PR. Use when reviewing Azure DevOps pull requests.
---

# Azure DevOps Multi-Model PR Review

Review PRs using Copilot CLI with multiple AI models for comprehensive coverage. Same review prompt, different models = higher confidence when they agree.

## Quick Start

1. Get PR URL from user
2. Authenticate via `az login`
3. Set up git worktree for the PR (never checkout in main repo)
4. Run Copilot CLI review with each model — full codebase access
5. Consolidate & dedupe findings
6. Get user confirmation
7. Post to Azure DevOps

## Models

Run review with these models (in parallel or sequence):

| Model | Flag | Strengths |
|-------|------|-----------|
| Claude Opus 4.5 | `--model claude-opus-4.5` | Deep reasoning, nuanced analysis |
| Codex 5.2 | `--model gpt-5.2-codex` | Code-focused, practical fixes |
| Gemini Pro 3 | `--model gemini-3-pro-preview` | Broad coverage, different perspective |

## Authentication

```bash
# Azure DevOps
az login
TOKEN=$(az account get-access-token --resource 499b84ac-1321-427f-aa17-267ca6975798 --query accessToken -o tsv)

# Copilot CLI (uses GitHub auth)
copilot  # First run opens browser for auth
```

## Review Workflow

### 1. Set Up Git Worktree

**Always use a git worktree** — never checkout in the main repo directory.

```bash
cd {repoPath}
git fetch origin {sourceBranch}
git worktree add ../review-pr-{prId} origin/{sourceBranch}
cd ../review-pr-{prId}

# Get changed files list for the prompt
git diff origin/{targetBranch}...HEAD --name-only > /tmp/changed_files.txt
```

**Worktree path:** `{repoParentDir}/review-pr-{prId}` (sibling of the main repo)

**Cleanup after review:** `git worktree remove ../review-pr-{prId}` (ask user first)

### 2. Run Multi-Model Reviews — Full Codebase Access

**Critical:** Models must run **inside the worktree** with tool access so they can explore the full codebase — read related files, follow includes/imports, understand architecture, check how changed code interacts with the rest of the system. Do NOT just feed them a diff.

**Review prompt** (save to file):
```bash
cat > /tmp/review_prompt.txt << 'EOF'
Review this pull request for issues. The full codebase is available in your working directory — USE IT.

Changed files:
$(cat /tmp/changed_files.txt)

## Your Task
1. Read each changed file in FULL (not just the diff)
2. **Explore the codebase** to understand the broader context:
   - Read related files (headers, imports, base classes, interfaces)
   - Check how the changed code is called/used elsewhere
   - Look at similar patterns in the codebase for consistency
   - Check existing tests related to the changed code
3. Run: git diff origin/{targetBranch}...HEAD -- to see the actual changes

Review criteria:
1. Correctness: bugs, logic errors, null checks, thread safety, edge cases
2. Performance: unnecessary allocations, O(n²) where O(n) possible, lock contention
3. Security: input validation, sensitive data exposure, injection risks
4. Quality: naming conventions, error handling, logging, code clarity
5. Consistency: does the change match existing codebase patterns and conventions?

For each issue found, output in this format:
FILE: <filepath> | LINE: <line_number> | CATEGORY: <correctness|performance|security|quality|consistency> | ISSUE: <description> | SUGGESTION: <recommended fix> | CONTEXT: <which related files informed this finding>

If no issues found, output: NO_ISSUES_FOUND
EOF
```

**Run each model from the worktree directory** with full tool access (parallel):
Run all models **from the worktree directory** so they have automatic access to the full codebase:
```bash
cd {worktreePath}

# Opus 4.5
copilot --model claude-opus-4.5 --allow-all-tools --no-ask-user \
  -p "$(cat /tmp/review_prompt.txt)" > /tmp/review_opus.txt 2>&1 &

# Codex 5.2
copilot --model gpt-5.2-codex --allow-all-tools --no-ask-user \
  -p "$(cat /tmp/review_prompt.txt)" > /tmp/review_codex.txt 2>&1 &

# Gemini Pro 3
copilot --model gemini-3-pro-preview --allow-all-tools --no-ask-user \
  -p "$(cat /tmp/review_prompt.txt)" > /tmp/review_gemini.txt 2>&1 &

wait  # Wait for all to complete
```

**Note:** `--add-dir` is a Copilot CLI flag (not model-specific) — works with all models. But running from the worktree cwd is simpler since Copilot grants access to the working directory by default.

**Why full codebase access matters for reviews:**
- A potential null deref is only real if callers can actually pass null — models need to check callers
- Thread safety issues depend on the project's threading model — models need to see how locks are used elsewhere
- "Missing error handling" depends on the project's error strategy — models should check conventions
- Performance suggestions should match existing patterns, not introduce inconsistencies

### 3. Consolidate Results

1. Parse each model's output into structured format
2. Group by file + line (±3 lines tolerance)
3. Merge similar issues, note sources: `[Opus, Codex]`
4. Assign confidence:
   - **HIGH**: 2+ models agree
   - **MEDIUM**: Single model

### 4. Post to Azure DevOps

```bash
cat > /tmp/comment.json << 'EOF'
{
  "comments": [{"parentCommentId": 0, "content": "**Issue:** Description", "commentType": "text"}],
  "status": "active",
  "threadContext": {
    "filePath": "/path/to/file.cpp",
    "rightFileStart": {"line": 42, "offset": 1},
    "rightFileEnd": {"line": 42, "offset": 1}
  }
}
EOF

curl -X POST "https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repo}/pullRequests/{prId}/threads?api-version=7.0" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d @/tmp/comment.json
```

## Detailed References

- [WORKFLOW.md](references/WORKFLOW.md) - Complete step-by-step workflow
- [API-REFERENCE.md](references/API-REFERENCE.md) - Azure DevOps API endpoints
- [MODELS.md](references/MODELS.md) - Model comparison and selection

## Comment Tone

- Be polite: "Consider...", "You might want to..."
- Be constructive: Explain the "why"
- Question when uncertain: "Is this intentional?"

**Always get user confirmation before posting!**

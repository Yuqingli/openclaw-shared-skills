# Complete Multi-Model PR Review Workflow

## Step 1: Get PR URL

Parse Azure DevOps URL formats:
```
https://dev.azure.com/{org}/{project}/_git/{repo}/pullrequest/{prId}
https://{org}.visualstudio.com/{project}/_git/{repo}/pullrequest/{prId}
```

Extract: `organization`, `project`, `repository`, `pullRequestId`

## Step 2: Select Models

Ask user which models to use:

| Option | Models | Use Case |
|--------|--------|----------|
| **Full** (default) | Opus 4.5 + Codex 5.2 + Gemini Pro 3 | Most thorough |
| **Fast** | Sonnet 4.5 + Codex 5.2 | Quicker, still multi-model |
| **Single** | User's choice | Fastest |

## Step 3: Authenticate

**Azure DevOps:**
```bash
az account show  # Check if logged in
az login         # If not logged in
TOKEN=$(az account get-access-token --resource 499b84ac-1321-427f-aa17-267ca6975798 --query accessToken -o tsv)
```

**Copilot CLI:** First run opens browser for GitHub auth.

## Step 4: Fetch PR Details

```bash
curl -s "https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repo}/pullrequests/{prId}?api-version=7.1" \
  -H "Authorization: Bearer $TOKEN"
```

Extract: `sourceRefName`, `targetRefName`, `title`, `description`

## Step 5: Set Up Git Worktree

**Always use a git worktree** — never checkout in the main repo directory. This avoids disrupting the user's working directory.

```bash
cd {repoPath}
git fetch origin {sourceBranch}
git worktree add ../review-pr-{prId} origin/{sourceBranch}
cd ../review-pr-{prId}

# Get changed files list
git diff origin/{targetBranch}...HEAD --name-only > /tmp/changed_files.txt
git diff origin/{targetBranch}...HEAD > /tmp/pr_diff.txt
```

**Worktree path:** `{repoParentDir}/review-pr-{prId}` (sibling of the main repo)

**Cleanup after review:** `git worktree remove ../review-pr-{prId}` (ask user first)

## Step 6: Multi-Model Review — Full Codebase Access

**Critical:** Models must run **inside the worktree** with tool access enabled so they can explore the full codebase — read related files, follow includes/imports, understand class hierarchies, check callers/callees, etc. Do NOT just feed them a diff or file list.

### Prepare Review Prompt
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

### Run Models in Parallel — from Worktree with Full Access
Run all models **from the worktree directory** so they have automatic access to the full codebase:
```bash
cd {worktreePath}

# Claude Opus 4.5
copilot --model claude-opus-4.5 --allow-all-tools --no-ask-user \
  -p "$(cat /tmp/review_prompt.txt)" > /tmp/review_opus.txt 2>&1 &

# GPT 5.2 Codex
copilot --model gpt-5.2-codex --allow-all-tools --no-ask-user \
  -p "$(cat /tmp/review_prompt.txt)" > /tmp/review_codex.txt 2>&1 &

# Gemini Pro 3
copilot --model gemini-3-pro-preview --allow-all-tools --no-ask-user \
  -p "$(cat /tmp/review_prompt.txt)" > /tmp/review_gemini.txt 2>&1 &

# Wait for all to complete
wait

# Collect results
cat /tmp/review_opus.txt
cat /tmp/review_codex.txt
cat /tmp/review_gemini.txt
```

**Note:** Copilot CLI grants models file access to the working directory by default. Running from the worktree means all models can explore the full codebase. Use `--add-dir` only if models need access to directories outside the worktree.

**Why full codebase access matters:**
- A potential null deref is only real if callers can actually pass null
- Thread safety issues depend on the project's threading model
- "Missing error handling" depends on the project's error strategy
- Performance suggestions should match existing patterns

## Step 7: Parse & Consolidate

### Parse Output
Convert each model's output to structured format:
```json
{
  "model": "opus|codex|gemini",
  "file": "/path/to/file.cpp",
  "line": 42,
  "category": "correctness",
  "issue": "Description",
  "suggestion": "Fix"
}
```

### Deduplication
1. Group by file + line (±3 lines tolerance)
2. Compare issue descriptions for semantic similarity
3. Merge similar issues, track sources: `[Opus, Codex]`

### Confidence Levels
- **CRITICAL**: All 3 models agree
- **HIGH**: 2 models agree
- **MEDIUM**: Single model

## Step 8: Validate Comments

For each consolidated comment:
1. Re-read actual code at file:line
2. Verify issue actually exists
3. Ensure line number is correct
4. Confirm suggestion is applicable
5. Discard false positives

## Step 9: User Confirmation

Present comments grouped by confidence:

```
## CRITICAL (all 3 models agree)
1. [Opus+Codex+Gemini] file.cpp:42 - Null pointer dereference...

## HIGH (2 models agree)
2. [Opus+Codex] util.h:78 - Thread safety issue...

## MEDIUM (single model)
3. [Gemini] config.cpp:156 - Consider const reference...

Options: Confirm / Edit / Skip each, or 'post all'
```

## Step 10: Collect User Comments

Ask: "Do you have additional issues to add?"

If yes:
1. Understand the concern
2. Verify against source code
3. Discuss and reach consensus
4. Format and add to list

## Step 11: Post to Azure DevOps

See API-REFERENCE.md for posting details.

**Always confirm before posting!**

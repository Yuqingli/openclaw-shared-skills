# Agent Launch Reference

## Claude Code (Author)

**Launch:**
```powershell
claude --dangerously-skip-permissions "<prompt>"
```

**Config location:** `.claude/commands/`
**Spec-kit slash commands:** Available after `specify init . --ai claude`

**For spec-kit steps:**
```powershell
# Constitution
claude --dangerously-skip-permissions "/speckit.constitution <principles>"

# Specify
claude --dangerously-skip-permissions "/speckit.specify <feature description>"

# Plan
claude --dangerously-skip-permissions "/speckit.plan <tech stack details>"

# Tasks
claude --dangerously-skip-permissions "/speckit.tasks"

# Implement
claude --dangerously-skip-permissions "/speckit.implement"
```

**For review fixes:**
```powershell
claude --dangerously-skip-permissions "Read reviews in <review_dir>. Address feedback in <artifact>. Summarize changes."
```

## Codex CLI (Reviewer)

**Launch:**
```powershell
codex exec --full-auto "<prompt>"
```

**Config location:** `codex-instructions.md`
**Model:** gpt-5.2-codex (default)

**For reviews:**
```powershell
codex exec --full-auto "Review the artifact at <path>. Write detailed review to <output_path>. Evaluate: completeness, correctness, edge cases, security, performance, alignment with project constitution at memory/constitution.md. Be specific with line numbers and concrete suggestions."
```

## Gemini CLI (Reviewer)

**Launch:**
```powershell
gemini "<prompt>"
```

**Config location:** `.gemini/commands/`
**Model:** gemini-3-pro-preview

**For reviews:**
```powershell
gemini "Review the artifact at <path>. Write detailed review to <output_path>. Evaluate: completeness, correctness, edge cases, security, performance, alignment with project constitution at memory/constitution.md. Be specific with line numbers and concrete suggestions."
```

## Copilot (Alternative Reviewer)

**Launch (via VS Code CLI):**
```powershell
code --goto <file>
```

Copilot is IDE-based — less suitable for CLI orchestration. Use Codex or Gemini for automated reviews.

## Agent Detection

Detect installed agents:
```powershell
$agents = @()
if (Get-Command claude -ErrorAction SilentlyContinue) { $agents += "claude" }
if (Get-Command codex -ErrorAction SilentlyContinue) { $agents += "codex" }
if (Get-Command gemini -ErrorAction SilentlyContinue) { $agents += "gemini" }
```

## PTY Requirements

All agents need PTY mode for proper terminal output:
```
exec pty:true workdir:<repo> background:true command:"<agent command>"
```

Without PTY, agents may hang or produce broken output.

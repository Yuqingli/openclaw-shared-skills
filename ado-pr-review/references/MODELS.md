# Copilot CLI Model Reference

## Available Models

```bash
copilot --model <model_name>
```

| Model | Flag | Best For |
|-------|------|----------|
| `claude-opus-4.5` | `--model claude-opus-4.5` | Deep analysis, complex logic |
| `claude-sonnet-4.5` | `--model claude-sonnet-4.5` | Balanced speed/quality |
| `claude-sonnet-4` | `--model claude-sonnet-4` | Fast, good quality |
| `claude-haiku-4.5` | `--model claude-haiku-4.5` | Fastest Claude |
| `gpt-5.2-codex` | `--model gpt-5.2-codex` | Code-focused, practical |
| `gpt-5.2` | `--model gpt-5.2` | General purpose |
| `gpt-5.1-codex-max` | `--model gpt-5.1-codex-max` | Extended context |
| `gpt-5.1-codex` | `--model gpt-5.1-codex` | Code tasks |
| `gpt-5` | `--model gpt-5` | General purpose |
| `gpt-5-mini` | `--model gpt-5-mini` | Fast, lighter tasks |
| `gemini-3-pro-preview` | `--model gemini-3-pro-preview` | Broad analysis |

## Recommended Review Combo

For comprehensive PR review, use these 3 models:

1. **Claude Opus 4.5** - Deep reasoning, catches subtle bugs
2. **GPT 5.2 Codex** - Code-focused, practical suggestions
3. **Gemini Pro 3** - Different perspective, broad coverage

## Usage Patterns

### Sequential (safer, easier to debug)
```bash
copilot --model claude-opus-4.5 --allow-all-tools -p "Review prompt" > opus.txt
copilot --model gpt-5.2-codex --allow-all-tools -p "Review prompt" > codex.txt
copilot --model gemini-3-pro-preview --allow-all-tools -p "Review prompt" > gemini.txt
```

### Parallel (faster)
```bash
copilot --model claude-opus-4.5 --allow-all-tools -p "prompt" > opus.txt 2>&1 &
copilot --model gpt-5.2-codex --allow-all-tools -p "prompt" > codex.txt 2>&1 &
copilot --model gemini-3-pro-preview --allow-all-tools -p "prompt" > gemini.txt 2>&1 &
wait
```

## Key Flags

| Flag | Purpose |
|------|---------|
| `--model <name>` | Select AI model |
| `--allow-all-tools` | Auto-approve tool calls |
| `-p "prompt"` | Non-interactive, single prompt |
| `--add-dir <path>` | Add directory access |
| `--no-ask-user` | Fully autonomous |

## Confidence Scoring

When consolidating results across models:

| Agreement | Confidence | Action |
|-----------|------------|--------|
| 3/3 models | **CRITICAL** | Definitely flag |
| 2/3 models | **HIGH** | Strong signal |
| 1/3 models | **MEDIUM** | Review carefully |

Issues flagged by multiple models are more likely to be real problems.

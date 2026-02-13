---
name: ai-council
description: Query Claude, ChatGPT (Codex), and Gemini for multiple AI perspectives on any question. Use "ask all" or "AI council" prompts.
---

# AI Council Skill

Query Claude, ChatGPT (Codex), and Gemini for multiple AI perspectives on any question.

## How It Works

When you ask me to "ask all" or get an "AI council" opinion:

1. I run `council.py` which queries **ChatGPT** and **Gemini** in parallel
2. I provide my own **Claude** perspective directly
3. I consolidate all three into a unified response

## Trigger Phrases
- "ask all: [question]"
- "AI council: [question]"  
- "get all opinions on: [question]"
- "what do all the AIs think about [question]"

## Progress Updates (Important!)
When processing an AI council request, ALWAYS:
1. **Immediately** send: "🔄 Querying AI Council (Claude + ChatGPT + Gemini)... this takes 30-60 seconds"
2. Run the council.py script
3. Provide the consolidated response

This lets the user know the request is being processed.

## Usage (for Aibot)

```python
# Run the council script
result = exec('python skills/ai-council/scripts/council.py "Your question"')

# Parse JSON response
responses = json.loads(result)

# Add my own Claude response
claude_answer = "My perspective on the question..."

# Consolidate all three
```

## Manual Usage

```powershell
python "skills\ai-council\scripts\council.py" "Your question here"
```

Returns JSON:
```json
{
  "question": "Your question",
  "responses": [
    {"model": "ChatGPT", "success": true, "response": "..."},
    {"model": "Gemini", "success": true, "response": "..."}
  ]
}
```

## Requirements
- `codex` CLI logged in (`codex login --device-auth`)
- `gemini` CLI logged in (first-run OAuth)
- Claude response provided by Aibot directly

## Response Format

I'll present the consolidated response like:

---
### 🧠 AI Council Response

**Question:** [the question]

**Claude:** [my answer]

**ChatGPT:** [codex response]

**Gemini:** [gemini response]

**Consensus:** [where they agree]

**Key Differences:** [notable disagreements]

---

## Models

| AI | Model | CLI Command |
|----|-------|-------------|
| **Claude** | Opus 4.5 | Direct (I am Claude) |
| **ChatGPT** | GPT-5.2 | `codex exec -m gpt-5.2` |
| **Gemini** | Gemini 3 Pro Preview | `gemini -m gemini-3-pro-preview` |

## Notes
- All responses use subscription auth (no API fees!)
- Timeout is 120s per model
- Models updated: 2026-02-01

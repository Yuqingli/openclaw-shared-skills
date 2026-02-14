---
name: workiq
description: Query Microsoft 365 data (emails, meetings, documents, Teams messages) using natural language via Work IQ CLI. Ask questions like "What did my manager say about the deadline?" or "Find documents about Q4 planning".
homepage: https://github.com/microsoft/work-iq-mcp
---

# Microsoft Work IQ

Query your Microsoft 365 Copilot data with natural language — emails, meetings, documents, Teams messages, and more.

## Trigger Phrases

Use this skill when the user asks about:
- "check my emails" / "any emails from..."
- "what meetings do I have" / "my calendar"
- "find documents about..." / "my recent files"
- "Teams messages" / "what did [person] say"
- "work:" prefix (e.g., "work: summarize my emails")
- Any M365/Outlook/Teams related queries

## How to Use (for Aibot)

Run the workiq CLI with the user's question:

```powershell
workiq ask -q "user's question here"
```

**Important:** Use PTY mode (`pty: true`) for the exec call, as workiq uses terminal features.

**Timeout:** Allow 90 seconds — queries can take time.

### Example

```python
# User asks: "What meetings do I have tomorrow?"
exec('workiq ask -q "What meetings do I have tomorrow?"', pty=true, timeout=90)
```

## Supported Queries

| Data Type | Example Questions |
|-----------|-------------------|
| **Emails** | "What did John say about the proposal?" |
| **Meetings** | "What's on my calendar tomorrow?" |
| **Documents** | "Find my recent PowerPoint presentations" |
| **Teams** | "Summarize today's messages in the Engineering channel" |
| **People** | "Who is working on Project Alpha?" |

## Response Format

1. Run the workiq command
2. Parse the response (plain text)
3. Summarize key points for the user
4. Keep formatting chat-friendly (no markdown tables on Discord/WhatsApp)

## Authentication

- Already authenticated ✅ (uses cached Microsoft Entra ID tokens)
- If auth fails, tell user to run `workiq ask` interactively to re-authenticate

## Troubleshooting

If you get permission errors:
1. Tell user to contact their tenant admin
2. See [Admin Instructions](https://github.com/microsoft/work-iq-mcp/blob/main/ADMIN-INSTRUCTIONS.md)

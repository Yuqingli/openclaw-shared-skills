---
name: youtube-insights
description: Generate cross-referenced insights from YouTube videos in a category. Fetches transcripts from recent watchlist videos, extracts key points, and compiles ~10 bullet points with YouTube source links. Trigger with "youtube insights [category]", "yt insights", "deep digest", or "summarize youtube [category]".
---

# YouTube Insights

Deep digest that fetches transcripts from recent videos and compiles cross-referenced insights.

## Trigger Patterns

| Command | Action |
|---------|--------|
| `yt insights` | Insights from all categories (last 24h) |
| `yt insights ai` | Insights from AI category only |
| `youtube insights tech` | Insights from tech category |
| `deep digest` | Alias for `yt insights` |

## Workflow

### 1. Get Recent Videos

Load `data/youtube-channels.json` and fetch RSS feeds for the target category:

```
https://www.youtube.com/feeds/videos.xml?channel_id={channelId}
```

**Time window:**
- Primary: Videos from the last 24 hours
- Fallback: If <3 videos found, extend to last 48 hours
- Note the time window used in output

Collect:
- Video title
- Video ID
- Channel name
- YouTube URL: `https://youtube.com/watch?v={videoId}`

### 2. Fetch Transcripts

For each video, run:

```bash
python skills/youtube-summarize/scripts/youtube_transcript.py {videoId}
```

Skip videos where transcripts are disabled. Note failures but continue.

### 3. Extract Key Points

For each transcript, identify:
- Major announcements or news
- Key claims or statistics
- Notable opinions or predictions
- Surprising or controversial takes

### 4. Cross-Reference & Compile

Look for themes across multiple videos:
- Same topic covered by multiple creators → stronger signal
- Conflicting opinions → note the debate
- Unique insights only one creator mentioned

### 5. Output Format

```
📊 **YouTube Insights — {category} — {date}**

• **[Key insight #1]** — Brief explanation
  → [Channel1](https://youtube.com/watch?v=xxx), [Channel2](https://youtube.com/watch?v=yyy)

• **[Key insight #2]** — Brief explanation
  → [Channel](https://youtube.com/watch?v=xxx)

...

• **[Key insight #10]** — Brief explanation
  → [Channel](https://youtube.com/watch?v=xxx)

---
*Compiled from {n} videos across {m} channels*
```

## Guidelines

- **~10 bullets max** — distill, don't dump
- **Each bullet must be independent** — no two bullets about the same topic or overlapping themes
- **Deduplicate aggressively**: If 3 creators cover the same news, that's ONE bullet with multiple sources, not three bullets
- **Prioritize**: Breaking news > data/stats > opinions > speculation
- **Cross-reference**: Multiple creators on same topic = stronger signal, cite all
- **Include contrarian views**: "Berman says X, but Isenberg disagrees..."
- **Link every bullet** to at least one source video
- **Skip fluff**: No "this is exciting" or "game changer" without substance

## Cron Setup

Weekly insights digest:
```json
{
  "name": "YouTube Weekly Insights",
  "schedule": { "kind": "cron", "expr": "0 10 * * 0", "tz": "America/Los_Angeles" },
  "payload": { 
    "kind": "agentTurn", 
    "message": "Run YouTube insights for all categories and send results.", 
    "deliver": true,
    "channel": "telegram",
    "to": "-1003787773345:642"
  },
  "sessionTarget": "isolated"
}
```

Target: Telegram group `-1003787773345` topic `642` (qqbb-bot-group daily updates).

## Limitations

- Transcripts unavailable for ~10% of videos
- Very long videos (>1h) may hit token limits — summarize in chunks
- Non-English videos need `--language` flag

## Example Output

```
📊 **YouTube Insights — AI — Feb 6, 2026**

• **Claude Opus 4.6 ships with 1M context + Agent Teams** — First Opus model with million-token context; can spawn parallel Claude Code sessions that communicate
  → [Anthropic](https://youtube.com/watch?v=dPn3GBI8lII), [Alex Finn](https://youtube.com/watch?v=iGkhfUvRV6o)

• **GPT-5.3 Codex hits 57% SWE-Bench Pro** — OpenAI's new coding model, SOTA on terminal benchmarks
  → [Matthew Berman](https://youtube.com/watch?v=QgaVA9ldrrM), [Greg Isenberg](https://youtube.com/watch?v=gmSnQPzoYHA)

• **ElevenLabs valued at $11B** — Voice AI startup's journey from $0 covered by a16z
  → [a16z](https://youtube.com/watch?v=afkFLnyrLww)

...
```

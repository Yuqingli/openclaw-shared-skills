---
name: youtube-digest
description: Monitor YouTube channels via RSS and deliver daily digest summaries. Manage a channel watchlist with categories (tech, travel, politics, etc.). Trigger with "youtube add", "youtube remove", "youtube list", "youtube digest", "youtube check", or "yt" shorthand.
---

# YouTube Channel Digest

Monitor subscribed YouTube channels via RSS feeds and deliver categorized daily digests.

## Trigger Patterns

| Command | Action |
|---------|--------|
| `yt add <url> [category]` | Add a channel to watchlist |
| `yt remove <name or url>` | Remove a channel |
| `yt list` | List all watched channels |
| `yt digest [category]` | Run digest now (optionally filter by category) |
| `yt categories` | List available categories |
| `youtube check` | Check for new videos since last digest |

## Categories

Default categories (user can define custom ones):
- `tech` — AI, programming, software, hardware
- `travel` — Travel vlogs, destination guides
- `china` — China-related content
- `politics` — Political commentary, policy, elections
- `finance` — Markets, investing, economics
- `science` — Science, space, research
- `entertainment` — General entertainment, comedy
- `news` — News channels, daily updates
- `other` — Uncategorized

## Data File

Channel watchlist stored in `data\youtube-channels.json` (relative to workspace):

```json
{
  "channels": [
    {
      "name": "All-In Podcast",
      "handle": "@allin",
      "channelId": "UCESLZhusAkFfsNsApnjF_Cg",
      "feedUrl": "https://www.youtube.com/feeds/videos.xml?channel_id=UCESLZhusAkFfsNsApnjF_Cg",
      "categories": ["tech", "politics"],
      "addedAt": "2026-02-04T10:00:00"
    }
  ],
  "lastDigest": "2026-02-04T08:00:00",
  "customCategories": []
}
```

## Adding a Channel

When user provides a YouTube URL or handle:

1. **Extract channel ID** from the URL:
   ```bash
   # Fetch the page and extract externalId
   $html = curl.exe -s -L "https://www.youtube.com/{handle}"
   [regex]::Match($html, '"externalId":"([^"]+)"').Groups[1].Value
   ```
   Supported URL formats:
   - `youtube.com/@handle`
   - `youtube.com/channel/UCxxxxxxxx`
   - `youtube.com/@handle?si=xxxxx` (with tracking params — strip them)

2. **Verify the RSS feed works:**
   ```
   https://www.youtube.com/feeds/videos.xml?channel_id={channelId}
   ```

3. **Ask for category** if not provided. Allow multiple categories per channel.

4. **Save to `youtube-channels.json`**

5. **Confirm:** "✅ Added {name} ({handle}) to watchlist under: {categories}"

## Running a Digest

When triggered manually (`yt digest`) or by cron:

1. **Load** `youtube-channels.json`
2. **Fetch RSS feed** for each channel via `web_fetch`:
   ```
   https://www.youtube.com/feeds/videos.xml?channel_id={channelId}
   ```
3. **Parse entries** — extract: title, videoId, published date, description snippet
4. **Filter by time** — only videos since `lastDigest` (or last 24h for manual)
5. **Group by category**
6. **Format digest** (see below)
7. **Save to digest history** (see below)
8. **Update `lastDigest`** timestamp

### Saving Digest History

After running a digest, append to `data/youtube-digest-history.json`:

```json
{
  "digests": [
    {
      "timestamp": "2026-02-11T08:30:00-08:00",
      "videos": [
        {
          "videoId": "abc123",
          "title": "GPT-5 Announcement Breakdown",
          "channel": "TheAIGRID",
          "category": "ai",
          "publishedAt": "2026-02-11T06:00:00Z",
          "url": "https://youtube.com/watch?v=abc123"
        }
      ]
    }
  ]
}
```

**Important:** Keep only the last 7 days of history to avoid file bloat.

```python
# Prune old entries
cutoff = datetime.now() - timedelta(days=7)
history["digests"] = [d for d in history["digests"] 
                      if parse(d["timestamp"]) > cutoff]
```

This history is consumed by the `youtube-video` skill to generate daily videos.

### Digest Format

```
📺 YouTube Digest — {date}

🔧 Tech (3 new)
• All-In Podcast: "Jensen Huang: The CEO Who..." — 2h ago
  https://youtube.com/watch?v=GdBoOaW2n-U
• Fireship: "AI just got weird..." — 5h ago
  https://youtube.com/watch?v=xxxxx

🌏 China (1 new)
• PolyMatter: "Why China's economy is..." — 8h ago
  https://youtube.com/watch?v=xxxxx

No new videos: travel, politics
```

Keep it scannable — title + time + link. No fluff.

### Optional: Category Filter

`yt digest tech` — only show tech category.

## Cron Setup

Set up a daily digest cron job:

```json
{
  "name": "YouTube Daily Digest",
  "schedule": { "kind": "cron", "expr": "0 8 * * *", "tz": "America/Los_Angeles" },
  "payload": { 
    "kind": "agentTurn", 
    "message": "Run the YouTube daily digest and send results.", 
    "deliver": true,
    "channel": "telegram",
    "to": "-1003787773345:642"
  },
  "sessionTarget": "isolated"
}
```

Target: Telegram group `-1003787773345` topic `642` (qqbb-bot-group daily updates).

## Removing a Channel

Match by name (fuzzy), handle, or channel ID. Confirm before removing.

## Listing Channels

Format as a table grouped by category:

```
📺 YouTube Watchlist (5 channels)

🔧 Tech
• All-In Podcast (@allin)
• Fireship (@Fireship)

🌏 China
• PolyMatter (@PolyMatter)

🏛️ Politics
• All-In Podcast (@allin)  ← can appear in multiple categories
```

## Important Rules

1. **RSS only** — no YouTube API key required
2. **Channel ID extraction** — always verify by fetching the feed before adding
3. **Respect rate limits** — RSS feeds are lightweight but don't fetch more than necessary
4. **Dedup across categories** — a video appears once in the digest even if the channel is in multiple categories (list under first matching category)
5. **Graceful failures** — if a feed is unreachable, note it and continue with others
6. **Keep data file small** — only store channel metadata, not video history

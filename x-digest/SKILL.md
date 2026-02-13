---
name: x-digest
description: Monitor X/Twitter accounts and deliver digest summaries. Manage a watchlist with categories. Trigger with "x add", "x remove", "x list", "x digest", or "x check".
---

# X/Twitter Account Digest

Monitor X/Twitter accounts and deliver categorized digests of new tweets.

## Trigger Patterns

| Command | Action |
|---------|--------|
| `x add @username [category]` | Add an account to watchlist |
| `x remove @username` | Remove an account |
| `x list` | List all watched accounts |
| `x digest [category]` | Run digest now (optionally filter by category) |
| `x check @username` | Fetch latest tweets from a specific user |
| `x categories` | List available categories |

## Categories

Default categories:
- `tech` — AI, programming, startups, tech news
- `politics` — Political commentary, policy
- `finance` — Markets, crypto, economics
- `news` — News accounts, journalists
- `science` — Science, space, research
- `entertainment` — Celebrities, comedy
- `other` — Uncategorized

## Data Files

**Watchlist:** `data/x-watchlist.json`
```json
{
  "accounts": [
    {
      "username": "elonmusk",
      "user_id": "44196397",
      "categories": ["tech"],
      "added_at": "2026-02-05T17:00:00"
    }
  ],
  "lastDigest": "2026-02-05T08:00:00",
  "customCategories": []
}
```

**Credentials:** `data/x-credentials.json` (auth_token, ct0 from browser cookies)

## Scripts

**x_fetch.py** — Core API client
- `get_user_tweets(username, count)` — Fetch recent tweets
- Uses session cookies for authentication
- Handles Twitter's GraphQL API

## Adding an Account

When user says `x add @username [category]`:

1. Validate username exists via API
2. Get user_id
3. Ask for category if not provided
4. Save to watchlist
5. Confirm: "✅ Added @username to watchlist under: {category}"

## Running a Digest

When triggered manually (`x digest`) or by cron:

1. Load watchlist
2. For each account, fetch tweets since `lastDigest`
3. Filter to only new tweets
4. Group by category
5. Format digest (see below)
6. Update `lastDigest` timestamp

### Digest Format

```
🐦 X Digest — Feb 5, 2026

🔧 Tech (5 new tweets)
• @elonmusk: "Starlink now available in Tajikistan 🇹🇯" — 2h ago
  ❤️ 88K  🔁 6.8K
  https://x.com/elonmusk/status/xxx

• @sama: "GPT-5 coming soon..." — 4h ago
  ❤️ 12K  🔁 2.1K
  https://x.com/sama/status/xxx

📰 News (2 new tweets)
• @breaking911: "..." — 1h ago

No new tweets: politics, finance
```

## Cookie Refresh

Twitter cookies expire periodically. When API returns 401/403:
1. Alert user: "X cookies expired. Please refresh."
2. User extracts new cookies from browser DevTools
3. Update `x-credentials.json`

## Cron Setup

Daily digest example:
```json
{
  "name": "X Daily Digest",
  "schedule": { "kind": "cron", "expr": "0 9 * * *", "tz": "America/Los_Angeles" },
  "payload": { 
    "kind": "agentTurn", 
    "message": "Run the X daily digest and send results.", 
    "deliver": true,
    "channel": "telegram",
    "to": "-1003787773345:642"
  },
  "sessionTarget": "isolated"
}
```

Target: Telegram group `-1003787773345` topic `642` (qqbb-bot-group daily updates).

## Important Rules

1. **Cookie-based auth** — No official API, uses browser session cookies
2. **Rate limits** — Don't fetch too frequently, Twitter may throttle
3. **Cookies expire** — Need periodic refresh (every few weeks)
4. **Respect privacy** — Only track public accounts
5. **Graceful failures** — If an account fails, note it and continue

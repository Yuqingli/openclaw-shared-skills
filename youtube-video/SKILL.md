---
name: youtube-video
description: Generate daily video from YouTube digest themes. Analyzes the day's digests, identifies top 2 themes, and creates a 3-5 minute 1080p video using the insights-video-pipeline. Runs nightly at 9:30 PM PST.
---

# YouTube Video Generator

Automatically generates a daily video summarizing the top themes from YouTube digests.

## Trigger Patterns

| Command | Action |
|---------|--------|
| `yt video` | Generate video from today's digests |
| `yt video [theme]` | Generate video for specific theme |
| `youtube video` | Alias for `yt video` |

## Data Files

- **Digest History:** `data/youtube-digest-history.json`
- **Output Directory:** `output/daily/YYYY-MM-DD/`

## Complete Workflow

There are two ways to run this skill:

### Option A: Full Automation (Recommended)

Run the orchestrator script that handles everything:

```bash
python skills/youtube-video/scripts/generate_daily_video.py --date YYYY-MM-DD
```

**What it does:**
1. Loads digest history from `data/youtube-digest-history.json`
2. Identifies themes (placeholder - you'll want to pre-generate these)
3. Generates TTS audio via ElevenLabs
4. Renders HeyGen avatars via browser automation
5. Composites final video with FFmpeg
6. Compresses for Telegram delivery

**With pre-generated content:**
```bash
# If you already have themes identified:
python skills/youtube-video/scripts/generate_daily_video.py --themes-json themes.json

# If you already have a script:
python skills/youtube-video/scripts/generate_daily_video.py --script-json output/daily/YYYY-MM-DD/script.json

# Skip specific phases:
python skills/youtube-video/scripts/generate_daily_video.py --skip-tts --skip-heygen
```

### Option B: Agent-Driven (Step by Step)

For more control, run each phase manually:

#### Phase 1: Theme Identification (5 min)

Load digest history and identify themes:

```python
import json
from datetime import datetime, timedelta

with open("data/youtube-digest-history.json") as f:
    history = json.load(f)

# Get last 24 hours of digests
cutoff = datetime.now() - timedelta(hours=24)
```

Use Claude to analyze video titles and find TOP 2 themes with 2+ sources each.

**If fewer than 2 themes have multiple sources:** Exit gracefully.

#### Phase 2: Script Generation (5 min)

Create a script JSON with this structure:

```json
{
  "title": "AI Daily: {Theme1} & {Theme2}",
  "date": "YYYY-MM-DD",
  "avatar_segments": [
    {"id": "hook", "type": "avatar", "text": "Hook text...", "duration": 15},
    {"id": "theme1_intro", "type": "avatar", "text": "...", "duration": 20},
    {"id": "theme1_analysis", "type": "avatar", "text": "...", "duration": 20},
    {"id": "theme2_intro", "type": "avatar", "text": "...", "duration": 20},
    {"id": "theme2_analysis", "type": "avatar", "text": "...", "duration": 20},
    {"id": "outro", "type": "avatar", "text": "Outro with CTA...", "duration": 15}
  ]
}
```

Save to: `output/daily/YYYY-MM-DD/script.json`

#### Phase 3: TTS Generation (5 min)

Generate audio for each segment via ElevenLabs (built into orchestrator script).

### Phase 5: HeyGen Avatar Generation (30-40 min) ⚠️ CRITICAL

**THIS IS THE SLOW PART - DO NOT SKIP**

Use the Playwright automation script for 1080p quality. This runs independently without consuming agent tokens.

#### 5.1 Run HeyGen Automation Script

```bash
python skills/youtube-video/scripts/heygen_render.py \
  --audio-dir "output/daily/YYYY-MM-DD/assets/audio" \
  --output-dir "output/daily/YYYY-MM-DD/assets/avatar"
```

The script will:
1. Use OpenClaw's browser profile (with HeyGen cookies)
2. Process each audio file in order
3. Upload → Render → Generate 1080p → Download
4. Save results to `render_results.json`
5. Skip already-processed segments

#### 5.2 Verify Results

Check `output/daily/YYYY-MM-DD/assets/avatar/render_results.json`:
```json
{
  "results": {
    "hook": "path/to/hook.mp4",
    "theme1_intro": "path/to/theme1_intro.mp4",
    ...
  },
  "success_count": 6,
  "total_count": 6
}
```

**If any segments failed:** Re-run the script (it skips completed segments).

#### 5.3 Troubleshooting

- **Not logged in:** Open HeyGen manually in OpenClaw browser first (`browser(action="open", profile="openclaw", targetUrl="https://app.heygen.com")`)
- **Render timeout:** Check HeyGen Projects page manually
- **Download 403:** Script handles Referer header automatically

### Phase 6: Video Composition (5 min)

The orchestrator script handles this automatically using FFmpeg concat.
Output: `output/daily/YYYY-MM-DD/final-1080p.mp4`

### Phase 7: Compress & Deliver (2 min)

```bash
ffmpeg -i final-1080p.mp4 -c:v libx264 -crf 26 -vf scale=1280:720 -c:a aac -b:a 128k final-telegram.mp4
```

Deliver to Telegram:
```
message(action="send", target="-1003787773345:642", filePath="output/daily/YYYY-MM-DD/final-telegram.mp4", caption="📺 AI Daily: {Theme1} & {Theme2}")
```

## Time Budget

| Phase | Duration |
|-------|----------|
| Theme identification | 5 min |
| Script generation | 5 min |
| TTS generation | 5 min |
| **HeyGen avatars (6 segments)** | **35 min** |
| Composition | 5 min |
| Compress & deliver | 2 min |
| **Total** | **~57 min** |

## Cron Configuration

The job timeout should be at least 90 minutes:

```json
{
  "name": "YouTube Daily Video",
  "schedule": { "kind": "cron", "expr": "30 21 * * *", "tz": "America/Los_Angeles" },
  "payload": { 
    "kind": "agentTurn", 
    "message": "Generate the daily YouTube video. Steps:\n1. Read data/youtube-digest-history.json for recent videos\n2. Identify TOP 2 themes with 2+ sources each\n3. Generate engaging script.json (6 avatar segments: hook, theme1_intro, theme1_analysis, theme2_intro, theme2_analysis, outro)\n4. Save to output/daily/YYYY-MM-DD/script.json\n5. Run: python skills/youtube-video/scripts/generate_daily_video.py --script-json output/daily/YYYY-MM-DD/script.json\n6. Send output/daily/YYYY-MM-DD/final-telegram.mp4 to Telegram",
    "deliver": true,
    "channel": "telegram",
    "to": "-1003787773345:642",
    "timeoutSeconds": 7200
  },
  "sessionTarget": "isolated"
}
```

## Critical Rules

1. **DO NOT skip HeyGen avatar generation** - The video must have real avatar clips
2. **Use browser automation, not API** - API only does 540p and often fails
3. **Budget 5-7 minutes per avatar segment** - This is normal
4. **Verify each avatar downloaded** before moving to next
5. **If HeyGen fails**, retry up to 3 times before falling back

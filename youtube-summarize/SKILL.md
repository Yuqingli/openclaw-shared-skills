---
name: youtube-summarize
description: Summarize YouTube videos by extracting and analyzing transcripts. Use when asked to summarize a video, explain what a video is about, get key points from a video, or when a YouTube URL is shared with a request for summary/overview/highlights.
---

# YouTube Video Summarizer

Summarize any YouTube video using its transcript (auto-generated or manual captions).

## Workflow

1. **Extract video ID** from URL (supports youtube.com, youtu.be, shorts)
2. **Fetch transcript** via `scripts/youtube_transcript.py`
3. **Summarize** the transcript content based on user request

## Usage

```bash
python scripts/youtube_transcript.py <video_url_or_id> [--language LANG]
```

Output is JSON:
```json
{
  "video_id": "abc123",
  "language": "en",
  "is_generated": true,
  "text": "full transcript text...",
  "segments": [{"start": 0.0, "duration": 3.5, "text": "..."}],
  "duration_seconds": 1050.5
}
```

## Summarization Guidelines

- **Default**: Key points, main arguments, conclusions (3-5 bullet points)
- **Detailed**: Section-by-section breakdown with timestamps
- **Quick**: One-paragraph TL;DR
- Adapt length/depth to video duration and user request

## Limitations

- ~10% of videos have transcripts disabled
- Some videos only have auto-generated captions (quality varies)
- Non-English videos may need `--language` flag (supports zh-Hans, zh-Hant, etc.)

## Errors

| Error | Meaning |
|-------|---------|
| "Transcripts are disabled" | Creator disabled captions |
| "Video is unavailable" | Private, deleted, or region-locked |
| "No transcript found" | No captions in requested language |

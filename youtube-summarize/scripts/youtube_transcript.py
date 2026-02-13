#!/usr/bin/env python3
"""
Fetch YouTube video transcripts using youtube-transcript-api.
Usage: python youtube_transcript.py <video_url_or_id> [--language en]
"""

import sys
import re
import json
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable
)


def extract_video_id(url_or_id: str) -> str:
    """Extract video ID from YouTube URL or return as-is if already an ID."""
    if re.match(r'^[\w-]{11}$', url_or_id):
        return url_or_id
    
    patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/|youtube\.com/v/)([\w-]{11})',
        r'youtube\.com/shorts/([\w-]{11})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)
    
    raise ValueError(f"Could not extract video ID from: {url_or_id}")


def get_transcript(video_id: str, language: str = None) -> dict:
    """
    Fetch transcript for a video.
    Returns dict with 'text', 'segments' (with timestamps), 'language'.
    """
    try:
        api = YouTubeTranscriptApi()
        transcript_list = api.list(video_id)
        
        transcript = None
        used_language = None
        
        if language:
            try:
                transcript = transcript_list.find_transcript([language])
                used_language = language
            except NoTranscriptFound:
                pass
        
        if not transcript:
            try:
                transcript = transcript_list.find_transcript(['en', 'en-US', 'en-GB'])
                used_language = 'en'
            except NoTranscriptFound:
                for t in transcript_list:
                    transcript = t
                    used_language = t.language_code
                    break
        
        if not transcript:
            return {"error": "No transcript available"}
        
        segments = transcript.fetch()
        full_text = ' '.join(seg.text for seg in segments)
        segments_data = [{"start": seg.start, "duration": seg.duration, "text": seg.text} for seg in segments]
        
        return {
            "video_id": video_id,
            "language": used_language,
            "is_generated": transcript.is_generated,
            "text": full_text,
            "segments": segments_data,
            "duration_seconds": segments_data[-1]['start'] + segments_data[-1]['duration'] if segments_data else 0
        }
        
    except TranscriptsDisabled:
        return {"error": "Transcripts are disabled for this video"}
    except VideoUnavailable:
        return {"error": "Video is unavailable"}
    except NoTranscriptFound:
        return {"error": "No transcript found for this video"}
    except Exception as e:
        return {"error": str(e)}


def main():
    if len(sys.argv) < 2:
        print("Usage: python youtube_transcript.py <video_url_or_id> [--language LANG]")
        sys.exit(1)
    
    url_or_id = sys.argv[1]
    language = None
    
    if '--language' in sys.argv:
        idx = sys.argv.index('--language')
        if idx + 1 < len(sys.argv):
            language = sys.argv[idx + 1]
    
    try:
        video_id = extract_video_id(url_or_id)
    except ValueError as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)
    
    result = get_transcript(video_id, language)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

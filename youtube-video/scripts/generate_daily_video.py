#!/usr/bin/env python3
"""
Daily YouTube Video Generator

Orchestrates the full pipeline:
1. Analyze digest history for themes
2. Generate video script
3. Generate TTS audio
4. Render HeyGen avatars
5. Composite final video
6. Compress for Telegram

Usage:
    python generate_daily_video.py [--date YYYY-MM-DD] [--skip-heygen] [--skip-tts]
"""

import argparse
import asyncio
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add insights-video-pipeline to path for ElevenLabs client
PIPELINE_DIR = Path(r"C:\Users\yuqin\projects\insights-video-pipeline")
sys.path.insert(0, str(PIPELINE_DIR))


def get_output_dir(date_str: str) -> Path:
    """Get the output directory for a given date."""
    workspace = Path(os.path.expanduser("~/.openclaw/workspace"))
    return workspace / "output" / "daily" / date_str


def load_digest_history(hours: int = 24) -> list:
    """Load digest history from the last N hours."""
    workspace = Path(os.path.expanduser("~/.openclaw/workspace"))
    history_file = workspace / "data" / "youtube-digest-history.json"
    
    if not history_file.exists():
        print("[ERROR] No digest history found")
        return []
        
    with open(history_file) as f:
        history = json.load(f)
        
    cutoff = datetime.now() - timedelta(hours=hours)
    recent = []
    
    for entry in history.get("digests", []):
        try:
            entry_time = datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00"))
            if entry_time.replace(tzinfo=None) > cutoff:
                recent.append(entry)
        except:
            continue
            
    return recent


def identify_themes(digests: list) -> list:
    """Identify top themes from digests (placeholder - would use Claude)."""
    # This is a placeholder - the actual theme identification
    # would be done by the agent using Claude
    videos = []
    for digest in digests:
        for video in digest.get("videos", []):
            videos.append({
                "videoId": video.get("videoId"),
                "title": video.get("title"),
                "channel": video.get("channel")
            })
    
    # Return placeholder themes
    return [
        {
            "name": "AI Development",
            "description": "Latest in AI tools and development",
            "videos": videos[:3] if len(videos) >= 3 else videos
        },
        {
            "name": "Tech News",
            "description": "Technology industry updates",
            "videos": videos[3:6] if len(videos) >= 6 else videos[3:] if len(videos) > 3 else []
        }
    ]


def generate_script(themes: list, output_dir: Path) -> dict:
    """Generate video script from themes."""
    # Default script structure
    script = {
        "title": f"AI Daily: {themes[0]['name']} & {themes[1]['name']}" if len(themes) >= 2 else f"AI Daily: {themes[0]['name']}",
        "date": datetime.now().strftime("%Y-%m-%d"),
        "duration_target": 240,
        "avatar_segments": [
            {"id": "hook", "type": "avatar", "text": "What's happening in AI today? Let's dive in.", "duration": 10},
            {"id": "theme1_intro", "type": "avatar", "text": f"First up, {themes[0]['name']}. {themes[0]['description']}", "duration": 15},
            {"id": "theme1_analysis", "type": "avatar", "text": "Here's what the experts are saying about this trend.", "duration": 20},
        ],
        "clip_segments": []
    }
    
    if len(themes) >= 2:
        script["avatar_segments"].extend([
            {"id": "theme2_intro", "type": "avatar", "text": f"Moving on to {themes[1]['name']}. {themes[1]['description']}", "duration": 15},
            {"id": "theme2_analysis", "type": "avatar", "text": "This is definitely something to watch.", "duration": 20},
        ])
    
    script["avatar_segments"].append(
        {"id": "outro", "type": "avatar", "text": "That's all for today's AI update. See you tomorrow!", "duration": 10}
    )
    
    # Save script
    script_path = output_dir / "script.json"
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(script_path, "w") as f:
        json.dump(script, f, indent=2)
    
    print(f"[INFO] Script saved to: {script_path}")
    return script


async def generate_tts(script: dict, output_dir: Path) -> bool:
    """Generate TTS audio for each segment."""
    try:
        from src.clients.elevenlabs_client import ElevenLabsClient
    except ImportError:
        print("[ERROR] ElevenLabs client not available")
        return False
        
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        print("[ERROR] ELEVENLABS_API_KEY not set")
        return False
        
    audio_dir = output_dir / "assets" / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    
    client = ElevenLabsClient(
        api_key=api_key,
        voice_id="EXAVITQu4vr4xnSDxMaL"  # Sarah voice
    )
    
    for segment in script["avatar_segments"]:
        output_path = audio_dir / f"{segment['id']}.mp3"
        if output_path.exists():
            print(f"[SKIP] Audio exists: {segment['id']}")
            continue
            
        print(f"[INFO] Generating TTS: {segment['id']}")
        try:
            await client.text_to_speech(segment["text"], str(output_path))
        except Exception as e:
            print(f"[ERROR] TTS failed for {segment['id']}: {e}")
            return False
            
    print("[INFO] TTS generation complete")
    return True


def render_heygen(output_dir: Path) -> bool:
    """Run HeyGen browser automation script."""
    script_path = Path(__file__).parent / "heygen_render.py"
    audio_dir = output_dir / "assets" / "audio"
    avatar_dir = output_dir / "assets" / "avatar"
    
    if not audio_dir.exists() or not list(audio_dir.glob("*.mp3")):
        print("[ERROR] No audio files found for HeyGen")
        return False
        
    cmd = [
        sys.executable, str(script_path),
        "--audio-dir", str(audio_dir),
        "--output-dir", str(avatar_dir)
    ]
    
    print(f"[INFO] Running HeyGen automation...")
    print(f"[INFO] Command: {' '.join(cmd)}")
    
    result = subprocess.run(cmd, capture_output=False)
    
    if result.returncode != 0:
        print(f"[ERROR] HeyGen automation failed with code {result.returncode}")
        return False
        
    # Verify results
    results_file = avatar_dir / "render_results.json"
    if results_file.exists():
        with open(results_file) as f:
            results = json.load(f)
        if results.get("success_count", 0) < results.get("total_count", 1):
            print(f"[WARN] Some segments failed: {results['success_count']}/{results['total_count']}")
            return False
            
    return True


def composite_video(script: dict, output_dir: Path) -> bool:
    """Composite avatar segments into final video using FFmpeg."""
    avatar_dir = output_dir / "assets" / "avatar"
    final_output = output_dir / "final-1080p.mp4"
    
    # Get avatar videos in order
    segment_files = []
    for segment in script["avatar_segments"]:
        video_path = avatar_dir / f"{segment['id']}.mp4"
        if video_path.exists():
            segment_files.append(video_path)
        else:
            print(f"[WARN] Missing segment: {segment['id']}")
            
    if not segment_files:
        print("[ERROR] No avatar videos to composite")
        return False
        
    # Create concat file
    concat_file = output_dir / "concat.txt"
    with open(concat_file, "w") as f:
        for video in segment_files:
            f.write(f"file '{video}'\n")
            
    # Run FFmpeg concat
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_file),
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "192k",
        str(final_output)
    ]
    
    print(f"[INFO] Compositing {len(segment_files)} segments...")
    result = subprocess.run(cmd, capture_output=True)
    
    if result.returncode != 0:
        print(f"[ERROR] FFmpeg failed: {result.stderr.decode()}")
        return False
        
    print(f"[INFO] Final video: {final_output}")
    return True


def compress_for_telegram(output_dir: Path) -> Path:
    """Compress video for Telegram delivery."""
    input_file = output_dir / "final-1080p.mp4"
    output_file = output_dir / "final-telegram.mp4"
    
    if not input_file.exists():
        print("[ERROR] No final video to compress")
        return None
        
    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_file),
        "-c:v", "libx264",
        "-crf", "26",
        "-vf", "scale=1280:720",
        "-c:a", "aac",
        "-b:a", "128k",
        str(output_file)
    ]
    
    print("[INFO] Compressing for Telegram...")
    result = subprocess.run(cmd, capture_output=True)
    
    if result.returncode != 0:
        print(f"[ERROR] Compression failed: {result.stderr.decode()}")
        return None
        
    print(f"[INFO] Telegram video: {output_file}")
    return output_file


async def main():
    parser = argparse.ArgumentParser(description="Daily YouTube Video Generator")
    parser.add_argument("--date", help="Date to generate for (YYYY-MM-DD)", default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--skip-heygen", action="store_true", help="Skip HeyGen rendering")
    parser.add_argument("--skip-tts", action="store_true", help="Skip TTS generation")
    parser.add_argument("--themes-json", help="Path to themes JSON (skip theme identification)")
    parser.add_argument("--script-json", help="Path to script JSON (skip script generation)")
    args = parser.parse_args()
    
    output_dir = get_output_dir(args.date)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n{'='*60}")
    print(f"Daily Video Generation: {args.date}")
    print(f"Output: {output_dir}")
    print(f"{'='*60}\n")
    
    # Step 1: Load themes or identify from digests
    if args.script_json:
        print("[INFO] Loading existing script...")
        with open(args.script_json) as f:
            script = json.load(f)
    elif args.themes_json:
        print("[INFO] Loading themes from file...")
        with open(args.themes_json) as f:
            themes = json.load(f)
        script = generate_script(themes, output_dir)
    else:
        print("[INFO] Identifying themes from digest history...")
        digests = load_digest_history()
        if not digests:
            print("[ERROR] No recent digests found")
            sys.exit(1)
        themes = identify_themes(digests)
        script = generate_script(themes, output_dir)
    
    # Step 2: Generate TTS
    if not args.skip_tts:
        print("\n[PHASE] TTS Generation")
        if not await generate_tts(script, output_dir):
            print("[ERROR] TTS generation failed")
            sys.exit(1)
    
    # Step 3: Render HeyGen avatars
    if not args.skip_heygen:
        print("\n[PHASE] HeyGen Avatar Rendering")
        if not render_heygen(output_dir):
            print("[ERROR] HeyGen rendering failed")
            sys.exit(1)
    
    # Step 4: Composite video
    print("\n[PHASE] Video Composition")
    if not composite_video(script, output_dir):
        print("[ERROR] Video composition failed")
        sys.exit(1)
    
    # Step 5: Compress for Telegram
    print("\n[PHASE] Telegram Compression")
    telegram_video = compress_for_telegram(output_dir)
    if not telegram_video:
        print("[ERROR] Compression failed")
        sys.exit(1)
    
    print(f"\n{'='*60}")
    print("[SUCCESS] Video generation complete!")
    print(f"Final: {output_dir / 'final-1080p.mp4'}")
    print(f"Telegram: {telegram_video}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
"""
Compose a video from TTS audio segments with title cards.
Fallback when HeyGen avatars are unavailable.
Uses FFmpeg to create colored background segments with text overlays.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

FFMPEG = r"C:\Users\yuqin\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.0.1-full_build\bin\ffmpeg.exe"

def get_duration(audio_path):
    """Get audio duration in seconds using ffprobe."""
    ffprobe = FFMPEG.replace("ffmpeg.exe", "ffprobe.exe")
    result = subprocess.run(
        [ffprobe, "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", audio_path],
        capture_output=True, text=True
    )
    return float(result.stdout.strip())

def create_segment_video(audio_path, text, output_path, bg_color="0x1a1a2e"):
    """Create a video segment with colored background and text overlay."""
    duration = get_duration(audio_path)
    
    # Write text to a temp file to avoid shell escaping issues
    import tempfile
    # Wrap text at ~55 chars
    words = text.split()
    lines = []
    current = ""
    for w in words:
        if len(current) + len(w) + 1 > 55:
            lines.append(current)
            current = w
        else:
            current = f"{current} {w}".strip()
    if current:
        lines.append(current)
    wrapped = "\n".join(lines)
    
    # Write to temp textfile for drawtext
    textfile = output_path + ".txt"
    with open(textfile, "w", encoding="utf-8") as tf:
        tf.write(wrapped)
    textfile_escaped = textfile.replace("\\", "/").replace(":", "\\:")
    
    cmd = [
        FFMPEG, "-y",
        "-f", "lavfi", "-i", f"color=c={bg_color}:s=1920x1080:d={duration}",
        "-i", audio_path,
        "-vf", f"drawtext=textfile='{textfile_escaped}':fontcolor=white:fontsize=32:x=(w-text_w)/2:y=(h-text_h)/2:font=Arial",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        output_path
    ]
    
    print(f"[INFO] Creating segment: {os.path.basename(output_path)} ({duration:.1f}s)")
    result = subprocess.run(cmd, capture_output=True, text=True)
    # Cleanup temp textfile
    if os.path.exists(textfile):
        os.remove(textfile)
    if result.returncode != 0:
        print(f"[ERROR] FFmpeg error: {result.stderr[-500:]}")
        return False
    return True

def concat_videos(segment_paths, output_path):
    """Concatenate video segments."""
    list_path = output_path.replace(".mp4", "_list.txt")
    with open(list_path, "w") as f:
        for p in segment_paths:
            f.write(f"file '{p}'\n")
    
    cmd = [
        FFMPEG, "-y",
        "-f", "concat", "-safe", "0", "-i", list_path,
        "-c", "copy",
        output_path
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    os.remove(list_path)
    if result.returncode != 0:
        print(f"[ERROR] Concat error: {result.stderr[-500:]}")
        return False
    return True

def compress_for_telegram(input_path, output_path):
    """Compress to <50MB for Telegram."""
    cmd = [
        FFMPEG, "-y",
        "-i", input_path,
        "-c:v", "libx264", "-crf", "26",
        "-vf", "scale=1280:720",
        "-c:a", "aac", "-b:a", "128k",
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0

def main():
    date_dir = sys.argv[1] if len(sys.argv) > 1 else "output/daily/2026-02-17"
    base = Path(os.path.expanduser("~/.openclaw/workspace")) / date_dir
    
    script_path = base / "script.json"
    audio_dir = base / "assets" / "audio"
    temp_dir = base / "assets" / "segments"
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    with open(script_path) as f:
        script = json.load(f)
    
    # Color scheme per segment type
    colors = {
        "hook": "0x16213e",
        "theme1_intro": "0x0f3460",
        "theme1_analysis": "0x0f3460",
        "theme2_intro": "0x533483",
        "theme2_analysis": "0x533483",
        "outro": "0x16213e",
    }
    
    segment_videos = []
    for seg in script["avatar_segments"]:
        sid = seg["id"]
        audio = audio_dir / f"{sid}.mp3"
        if not audio.exists():
            print(f"[SKIP] No audio for {sid}")
            continue
        
        vid = temp_dir / f"{sid}.mp4"
        bg = colors.get(sid, "0x1a1a2e")
        if create_segment_video(str(audio), seg["text"], str(vid), bg):
            segment_videos.append(str(vid))
    
    if not segment_videos:
        print("[ERROR] No segments created")
        sys.exit(1)
    
    # Concat
    final = base / "final-1080p.mp4"
    print(f"\n[INFO] Concatenating {len(segment_videos)} segments...")
    if not concat_videos(segment_videos, str(final)):
        sys.exit(1)
    
    # Compress for Telegram
    telegram = base / "final-telegram.mp4"
    print("[INFO] Compressing for Telegram...")
    if compress_for_telegram(str(final), str(telegram)):
        size_mb = os.path.getsize(str(telegram)) / (1024*1024)
        print(f"\n[SUCCESS] Final video: {telegram} ({size_mb:.1f} MB)")
    else:
        print("[ERROR] Compression failed")
        sys.exit(1)

if __name__ == "__main__":
    main()

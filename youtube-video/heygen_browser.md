# HeyGen Browser Automation - Step-by-Step

This document provides the exact browser automation steps for generating 1080p HeyGen avatars.

## Prerequisites
- Audio files in `assets/audio/` folder (MP3 format)
- OpenClaw browser available (profile: "openclaw")
- HeyGen account logged in

## Per-Segment Workflow

For EACH avatar segment audio file, follow these steps:

### Step 1: Navigate to HeyGen Create Page
```
browser(action="navigate", profile="openclaw", targetUrl="https://app.heygen.com/create-v4")
```
Wait for page to load (2-3 seconds).

### Step 2: Take Snapshot to Verify Page
```
browser(action="snapshot", profile="openclaw")
```
Look for "Create Video" or similar UI elements.

### Step 3: Click "Instant Avatar" or Use Existing Draft
If starting fresh, look for "Instant Avatar" option. If reusing a draft:
```
browser(action="navigate", profile="openclaw", targetUrl="https://app.heygen.com/create-v4/{draft_id}")
```

### Step 4: Select Avatar (if needed)
Navigate to avatar selection and choose:
- **Avatar:** "Annie Casual Standing Front 2" or similar
- **Voice:** "Annie - Lifelike"

### Step 5: Add Scene with Audio Upload
1. Click "Add Scene" or look for audio upload area
2. Take snapshot to find the upload button:
```
browser(action="snapshot", profile="openclaw")
```

### Step 6: Make File Input Visible (CRITICAL)
Execute JavaScript to reveal hidden file input:
```
browser(action="act", profile="openclaw", request={
  "kind": "evaluate",
  "fn": "const inputs = document.querySelectorAll('input[type=\"file\"]'); const audioInput = Array.from(inputs).find(i => i.accept && i.accept.includes('audio')); if(audioInput) { audioInput.style.display = 'block'; audioInput.style.opacity = '1'; audioInput.style.position = 'relative'; audioInput.style.width = '200px'; audioInput.style.height = '50px'; } return !!audioInput;"
})
```

### Step 7: Upload Audio File
```
browser(action="upload", profile="openclaw", paths=["C:\\path\\to\\audio\\segment.mp3"])
```

### Step 8: Confirm Audio Upload
Take snapshot and look for "Add audio" or "Confirm" button:
```
browser(action="snapshot", profile="openclaw")
```
Click the confirm button (ref will vary).

### Step 9: Wait for Transcription
HeyGen transcribes the audio. Wait 10-30 seconds, then snapshot to check status.

### Step 10: Render Scene
Look for "Render Scene" button and click it:
```
browser(action="snapshot", profile="openclaw")
browser(action="act", profile="openclaw", request={"kind": "click", "ref": "<render_button_ref>"})
```
Wait 2-3 minutes for scene render.

### Step 11: Generate Video at 1080p
1. Click "Generate" button
2. In resolution dialog, select "1080p" 
3. Click "Submit" or "Generate"
```
browser(action="snapshot", profile="openclaw")
# Click Generate
browser(action="act", profile="openclaw", request={"kind": "click", "ref": "<generate_button_ref>"})
# Wait for dialog, take snapshot
browser(action="snapshot", profile="openclaw")
# Select 1080p and submit
```
Wait 2-3 minutes for video generation.

### Step 12: Navigate to Video and Download
1. Go to Projects page:
```
browser(action="navigate", profile="openclaw", targetUrl="https://app.heygen.com/projects")
```

2. Find the generated video (most recent), click to open

3. Extract video URL via JavaScript:
```
browser(action="act", profile="openclaw", request={
  "kind": "evaluate", 
  "fn": "const video = document.querySelector('video'); return video ? video.src : null;"
})
```

4. Download using Python with proper headers:
```python
import requests
response = requests.get(video_url, headers={
    'User-Agent': 'Mozilla/5.0',
    'Referer': 'https://app.heygen.com/'
})
with open('output.mp4', 'wb') as f:
    f.write(response.content)
```

## Timing Estimates
- Audio upload + transcription: ~30 seconds
- Scene render: 2-3 minutes  
- Video generation: 2-3 minutes
- Download: ~10 seconds

**Total per segment: 5-7 minutes**

For a 6-segment video: **30-40 minutes total**

## Error Handling

### If upload fails:
- Re-run the visibility JavaScript
- Try clicking the upload area first, then upload

### If render times out:
- Refresh page and check Projects for the video
- May have completed in background

### If download gets 403:
- Ensure Referer header is set
- Try extracting URL again (signed URLs expire)

## Reusing Draft for Multiple Segments

To speed up: use ONE draft and cycle through scenes:
1. Generate first segment
2. Delete the scene
3. Add new scene with next audio
4. Repeat

This avoids avatar/voice re-selection each time.

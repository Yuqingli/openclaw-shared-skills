#!/usr/bin/env python3
"""
HeyGen Browser Automation Script

Renders avatar videos from audio files using HeyGen's web interface.
Uses Playwright for browser automation to bypass API 540p limit.

Usage:
    python heygen_render.py --audio-dir ./assets/audio --output-dir ./assets/avatar

Requirements:
    pip install playwright requests
    playwright install chromium
"""

import argparse
import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path
from datetime import datetime

import requests

# Check for playwright
try:
    from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    print("ERROR: playwright not installed. Run: pip install playwright && playwright install chromium")
    sys.exit(1)


# Configuration
HEYGEN_CREATE_URL = "https://app.heygen.com/create-v4"
HEYGEN_PROJECTS_URL = "https://app.heygen.com/projects"
HEYGEN_HOME_URL = "https://app.heygen.com/home"

# Browser profile path - separate from OpenClaw to avoid lock conflicts
# HeyGen cookies need to be logged in manually once
BROWSER_DATA_DIR = os.path.expanduser("~/.openclaw/browser/openclaw/user-data")

# Timeouts
PAGE_LOAD_TIMEOUT = 30000  # 30s
RENDER_TIMEOUT = 300000    # 5 min
GENERATION_TIMEOUT = 300000  # 5 min


class HeyGenAutomator:
    def __init__(self, browser_data_dir: str = BROWSER_DATA_DIR, headless: bool = False):
        self.browser_data_dir = browser_data_dir
        self.headless = headless
        self.browser = None
        self.context = None
        self.page = None
        
    async def __aenter__(self):
        await self.start()
        return self
        
    async def __aexit__(self, *args):
        await self.stop()
        
    async def start(self):
        """Start the browser with persistent context."""
        self.playwright = await async_playwright().start()
        
        # Use persistent context to preserve login cookies
        self.context = await self.playwright.chromium.launch_persistent_context(
            self.browser_data_dir,
            headless=self.headless,
            viewport={"width": 1920, "height": 1080},
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ]
        )
        
        # Use existing page or create new one
        if self.context.pages:
            self.page = self.context.pages[0]
        else:
            self.page = await self.context.new_page()
            
        print(f"[INFO] Browser started with profile: {self.browser_data_dir}")
        
    async def stop(self):
        """Close the browser."""
        if self.context:
            await self.context.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()
        print("[INFO] Browser closed")
        
    async def check_login(self) -> bool:
        """Check if we're logged into HeyGen."""
        await self.page.goto(HEYGEN_HOME_URL, timeout=PAGE_LOAD_TIMEOUT)
        await asyncio.sleep(2)
        
        # Check for login indicators
        url = self.page.url
        if "login" in url or "signin" in url:
            print("[ERROR] Not logged into HeyGen. Please log in manually first.")
            return False
            
        # Look for dashboard elements
        try:
            await self.page.wait_for_selector('[data-testid="home-page"]', timeout=5000)
            print("[INFO] Logged into HeyGen successfully")
            return True
        except:
            # Check for any projects or create button
            content = await self.page.content()
            if "Create video" in content or "My Projects" in content or "projects" in content.lower():
                print("[INFO] Logged into HeyGen successfully")
                return True
                
        print("[WARN] Could not verify HeyGen login status - proceeding anyway")
        return True
        
    async def navigate_to_create(self):
        """Navigate to the create video page."""
        print("[INFO] Navigating to create page...")
        await self.page.goto(HEYGEN_CREATE_URL, timeout=PAGE_LOAD_TIMEOUT)
        await asyncio.sleep(5)  # Wait for page to fully load
        
        # Debug: save screenshot
        debug_path = os.path.expanduser("~/.openclaw/workspace/output/debug-heygen.png")
        await self.page.screenshot(path=debug_path)
        print(f"[DEBUG] Screenshot saved: {debug_path}")
        
    async def click_upload_audio_button(self) -> bool:
        """Click the 'Upload audio' button to open the upload dialog."""
        print("[INFO] Looking for Upload audio button...")
        
        # Wait for page to settle
        await asyncio.sleep(3)
        
        # Try clicking in the script area first to activate it
        try:
            script_area = await self.page.query_selector('text="Type your script"')
            if script_area:
                await script_area.click()
                await asyncio.sleep(1)
        except:
            pass
        
        # Try multiple selectors for the Upload audio button
        selectors = [
            'button:has-text("Upload audio")',
            ':text("Upload audio")',
            'div:has-text("Upload audio"):not(:has(div:has-text("Upload audio")))',
            '[role="button"]:has-text("Upload audio")',
        ]
        
        for selector in selectors:
            try:
                btn = await self.page.wait_for_selector(selector, timeout=3000)
                if btn:
                    await btn.click()
                    print("[INFO] Clicked Upload audio button")
                    await asyncio.sleep(2)
                    return True
            except:
                continue
        
        # Try using XPath as fallback
        try:
            btn = await self.page.query_selector('xpath=//button[contains(., "Upload audio")]')
            if btn:
                await btn.click()
                print("[INFO] Clicked Upload audio button (xpath)")
                await asyncio.sleep(2)
                return True
        except:
            pass
                
        print("[WARN] Could not find Upload audio button")
        return False
        
    async def upload_audio_via_dialog(self, audio_path: str) -> bool:
        """Upload audio through HeyGen's upload dialog."""
        audio_path = os.path.abspath(audio_path)
        if not os.path.exists(audio_path):
            print(f"[ERROR] Audio file not found: {audio_path}")
            return False
            
        print(f"[INFO] Uploading audio: {audio_path}")
        
        # First click the Upload audio button to open dialog
        if not await self.click_upload_audio_button():
            return False
            
        await asyncio.sleep(2)
        
        # Look for the Upload Audio tab in the dialog
        try:
            upload_tab = await self.page.wait_for_selector('text="Upload Audio"', timeout=5000)
            if upload_tab:
                await upload_tab.click()
                await asyncio.sleep(1)
        except:
            print("[INFO] Upload Audio tab not found or already selected")
            
        # Find file input in the dialog (may be hidden)
        file_input = await self.page.query_selector('input[type="file"]')
        if not file_input:
            # Make it visible
            await self.page.evaluate("""
                () => {
                    const inputs = document.querySelectorAll('input[type="file"]');
                    inputs.forEach(input => {
                        input.style.display = 'block';
                        input.style.opacity = '1';
                        input.style.position = 'relative';
                        input.style.width = '200px';
                        input.style.height = '50px';
                    });
                }
            """)
            await asyncio.sleep(1)
            file_input = await self.page.query_selector('input[type="file"]')
            
        if file_input:
            await file_input.set_input_files(audio_path)
            print("[INFO] Audio file uploaded via dialog")
            await asyncio.sleep(3)
            
            # Wait for upload to complete and click on the uploaded file
            filename = os.path.basename(audio_path)
            try:
                # Click on the uploaded file in the list
                file_item = await self.page.wait_for_selector(f'text="{filename}"', timeout=10000)
                if file_item:
                    await file_item.click()
                    await asyncio.sleep(1)
            except:
                print(f"[WARN] Could not find uploaded file {filename} in list")
                
            # Click "Add audio" button to confirm
            try:
                add_btn = await self.page.wait_for_selector('button:has-text("Add audio")', timeout=5000)
                if add_btn:
                    await add_btn.click()
                    print("[INFO] Clicked Add audio to confirm")
                    await asyncio.sleep(2)
                    return True
            except:
                print("[WARN] Could not find Add audio button")
                
        return False
        
    async def upload_audio(self, audio_path: str) -> bool:
        """Upload an audio file using the dialog flow."""
        return await self.upload_audio_via_dialog(audio_path)
        
    async def click_button_by_text(self, text: str, timeout: int = 10000) -> bool:
        """Click a button containing specific text."""
        try:
            # Try various selectors
            selectors = [
                f'button:has-text("{text}")',
                f'[role="button"]:has-text("{text}")',
                f'div:has-text("{text}"):not(:has(div:has-text("{text}")))',  # Leaf text node
            ]
            
            for selector in selectors:
                try:
                    elem = await self.page.wait_for_selector(selector, timeout=timeout // len(selectors))
                    if elem:
                        await elem.click()
                        print(f'[INFO] Clicked: "{text}"')
                        return True
                except:
                    continue
                    
            print(f'[WARN] Could not find button: "{text}"')
            return False
        except Exception as e:
            print(f'[ERROR] Click failed for "{text}": {e}')
            return False
            
    async def wait_for_transcription(self, timeout: int = 60) -> bool:
        """Wait for audio transcription to complete."""
        print("[INFO] Waiting for transcription...")
        start = time.time()
        
        while time.time() - start < timeout:
            content = await self.page.content()
            # Look for transcription complete indicators
            if "Transcription complete" in content or "transcription" not in content.lower():
                # Check if we can proceed
                if await self.page.query_selector('button:has-text("Render")'):
                    print("[INFO] Transcription complete")
                    return True
            await asyncio.sleep(2)
            
        print("[WARN] Transcription timeout - proceeding anyway")
        return True
        
    async def render_scene(self, timeout: int = RENDER_TIMEOUT) -> bool:
        """Click render and wait for scene to render."""
        print("[INFO] Rendering scene...")
        
        if not await self.click_button_by_text("Render", timeout=10000):
            # Try alternative
            if not await self.click_button_by_text("Submit", timeout=5000):
                print("[WARN] Could not find render button")
                return False
                
        # Wait for render to complete
        start = time.time()
        while (time.time() - start) * 1000 < timeout:
            await asyncio.sleep(5)
            content = await self.page.content()
            
            # Check for completion indicators
            if "Generate" in content and "1080p" not in content:
                # Look for generate button becoming available
                gen_btn = await self.page.query_selector('button:has-text("Generate"):not([disabled])')
                if gen_btn:
                    print("[INFO] Scene render complete")
                    return True
                    
            # Check for error
            if "error" in content.lower() and "render" in content.lower():
                print("[ERROR] Render error detected")
                return False
                
            print(f"[INFO] Rendering... ({int(time.time() - start)}s)")
            
        print("[WARN] Render timeout")
        return False
        
    async def generate_1080p(self, timeout: int = GENERATION_TIMEOUT) -> bool:
        """Generate video at 1080p resolution."""
        print("[INFO] Generating 1080p video...")
        
        # Click Generate button
        if not await self.click_button_by_text("Generate", timeout=10000):
            print("[ERROR] Could not find Generate button")
            return False
            
        await asyncio.sleep(2)
        
        # Look for resolution selector
        try:
            # Try to find and click 1080p option
            selector_1080 = await self.page.query_selector('text="1080p"')
            if selector_1080:
                await selector_1080.click()
                print("[INFO] Selected 1080p resolution")
                await asyncio.sleep(1)
        except:
            print("[WARN] Could not find 1080p selector - using default")
            
        # Click Submit/Confirm
        await asyncio.sleep(1)
        if not await self.click_button_by_text("Submit", timeout=5000):
            await self.click_button_by_text("Confirm", timeout=5000)
            
        # Wait for generation
        start = time.time()
        while (time.time() - start) * 1000 < timeout:
            await asyncio.sleep(10)
            content = await self.page.content()
            
            # Check for completion - video element or download button
            video = await self.page.query_selector('video[src*="heygen"]')
            if video:
                print("[INFO] Video generation complete")
                return True
                
            download_btn = await self.page.query_selector('button:has-text("Download")')
            if download_btn:
                print("[INFO] Video generation complete (download available)")
                return True
                
            print(f"[INFO] Generating... ({int(time.time() - start)}s)")
            
        print("[WARN] Generation timeout")
        return False
        
    async def get_video_url(self) -> str:
        """Extract the generated video URL."""
        # Check for video element
        video_url = await self.page.evaluate("""
            () => {
                const video = document.querySelector('video');
                if (video && video.src) return video.src;
                
                // Try to find in source elements
                const source = document.querySelector('video source');
                if (source && source.src) return source.src;
                
                return null;
            }
        """)
        
        if video_url:
            print(f"[INFO] Found video URL")
            return video_url
            
        # Navigate to projects and find the video
        print("[INFO] Checking projects for video...")
        await self.page.goto(HEYGEN_PROJECTS_URL, timeout=PAGE_LOAD_TIMEOUT)
        await asyncio.sleep(3)
        
        # Click on most recent project
        project = await self.page.query_selector('[data-testid="project-card"]')
        if project:
            await project.click()
            await asyncio.sleep(3)
            
            video_url = await self.page.evaluate("""
                () => {
                    const video = document.querySelector('video');
                    return video ? video.src : null;
                }
            """)
            
        return video_url
        
    async def download_video(self, url: str, output_path: str) -> bool:
        """Download video with proper headers."""
        print(f"[INFO] Downloading video to: {output_path}")
        
        try:
            response = requests.get(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://app.heygen.com/'
            }, stream=True)
            
            if response.status_code == 200:
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                with open(output_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                print(f"[INFO] Downloaded: {output_path}")
                return True
            else:
                print(f"[ERROR] Download failed: HTTP {response.status_code}")
                return False
        except Exception as e:
            print(f"[ERROR] Download error: {e}")
            return False
            
    async def delete_current_scene(self):
        """Delete the current scene to prepare for next segment."""
        try:
            await self.click_button_by_text("Delete", timeout=5000)
            await asyncio.sleep(1)
            await self.click_button_by_text("Confirm", timeout=3000)
            await asyncio.sleep(1)
            print("[INFO] Scene deleted")
        except:
            print("[WARN] Could not delete scene")
            
    async def render_segment(self, audio_path: str, output_path: str) -> bool:
        """Complete workflow to render one segment."""
        print(f"\n{'='*60}")
        print(f"[SEGMENT] {os.path.basename(audio_path)}")
        print(f"{'='*60}")
        
        try:
            # Navigate to create page
            await self.navigate_to_create()
            
            # Upload audio via dialog
            if not await self.upload_audio(audio_path):
                return False
                
            # Wait for transcription
            await self.wait_for_transcription()
            
            # Render scene
            if not await self.render_scene():
                print("[ERROR] Scene render failed")
                return False
                
            # Generate 1080p
            if not await self.generate_1080p():
                print("[ERROR] Video generation failed")
                return False
                
            # Get video URL
            video_url = await self.get_video_url()
            if not video_url:
                print("[ERROR] Could not get video URL")
                return False
                
            # Download video
            if not await self.download_video(video_url, output_path):
                return False
                
            print(f"[SUCCESS] Segment complete: {output_path}")
            return True
            
        except Exception as e:
            print(f"[ERROR] Segment failed: {e}")
            return False


async def main():
    parser = argparse.ArgumentParser(description="HeyGen Browser Automation")
    parser.add_argument("--audio-dir", required=True, help="Directory containing audio files")
    parser.add_argument("--output-dir", required=True, help="Output directory for videos")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode")
    parser.add_argument("--segment", help="Render only specific segment (filename without extension)")
    args = parser.parse_args()
    
    audio_dir = Path(args.audio_dir)
    output_dir = Path(args.output_dir)
    
    if not audio_dir.exists():
        print(f"[ERROR] Audio directory not found: {audio_dir}")
        sys.exit(1)
        
    # Find audio files
    audio_files = sorted(audio_dir.glob("*.mp3"))
    if args.segment:
        audio_files = [f for f in audio_files if f.stem == args.segment]
        
    if not audio_files:
        print("[ERROR] No audio files found")
        sys.exit(1)
        
    print(f"[INFO] Found {len(audio_files)} audio files to process")
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Process each segment
    results = {}
    async with HeyGenAutomator(headless=args.headless) as heygen:
        # Check login
        if not await heygen.check_login():
            print("[ERROR] Please log into HeyGen in the browser first")
            print(f"[INFO] Browser profile: {BROWSER_DATA_DIR}")
            sys.exit(1)
            
        for audio_file in audio_files:
            segment_id = audio_file.stem
            output_path = output_dir / f"{segment_id}.mp4"
            
            # Skip if already exists
            if output_path.exists():
                print(f"[SKIP] Already exists: {output_path}")
                results[segment_id] = str(output_path)
                continue
                
            success = await heygen.render_segment(str(audio_file), str(output_path))
            if success:
                results[segment_id] = str(output_path)
            else:
                results[segment_id] = None
                
            # Brief pause between segments
            await asyncio.sleep(3)
            
    # Summary
    print(f"\n{'='*60}")
    print("[SUMMARY]")
    print(f"{'='*60}")
    
    success_count = sum(1 for v in results.values() if v)
    print(f"Successful: {success_count}/{len(results)}")
    
    for segment_id, path in results.items():
        status = "[OK]" if path else "[FAIL]"
        print(f"  {status} {segment_id}: {path or 'FAILED'}")
        
    # Write results JSON
    results_path = output_dir / "render_results.json"
    with open(results_path, "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "results": results,
            "success_count": success_count,
            "total_count": len(results)
        }, f, indent=2)
    print(f"\n[INFO] Results saved to: {results_path}")
    
    sys.exit(0 if success_count == len(results) else 1)


if __name__ == "__main__":
    asyncio.run(main())

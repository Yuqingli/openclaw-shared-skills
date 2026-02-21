#!/usr/bin/env python3
"""
HeyGen Browser Automation via CDP - connects to running Chrome instance.
"""

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime

import requests

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("ERROR: pip install playwright")
    sys.exit(1)

HEYGEN_CREATE_URL = "https://app.heygen.com/create-v4"
HEYGEN_PROJECTS_URL = "https://app.heygen.com/projects"
HEYGEN_HOME_URL = "https://app.heygen.com/home"
CDP_URL = "http://127.0.0.1:18800"

PAGE_LOAD_TIMEOUT = 30000
RENDER_TIMEOUT = 420000    # 7 min
GENERATION_TIMEOUT = 420000  # 7 min


class HeyGenCDP:
    def __init__(self):
        self.browser = None
        self.page = None

    async def __aenter__(self):
        self.pw = await async_playwright().start()
        self.browser = await self.pw.chromium.connect_over_cdp(CDP_URL)
        ctx = self.browser.contexts[0] if self.browser.contexts else await self.browser.new_context()
        self.page = await ctx.new_page()
        print("[INFO] Connected via CDP")
        return self

    async def __aexit__(self, *a):
        if self.page:
            await self.page.close()
        if hasattr(self, 'pw'):
            await self.pw.stop()

    async def check_login(self) -> bool:
        await self.page.goto(HEYGEN_HOME_URL, timeout=PAGE_LOAD_TIMEOUT)
        await asyncio.sleep(3)
        url = self.page.url
        if "login" in url or "signin" in url:
            print("[ERROR] Not logged into HeyGen")
            return False
        content = await self.page.content()
        if any(x in content for x in ["Create video", "My Projects", "projects", "home"]):
            print("[INFO] Logged into HeyGen")
            return True
        print("[WARN] Cannot verify login - proceeding")
        return True

    async def render_segment(self, audio_path: str, output_path: str) -> bool:
        print(f"\n{'='*60}")
        print(f"[SEGMENT] {os.path.basename(audio_path)}")
        print(f"{'='*60}")

        try:
            # Navigate to create page
            print("[INFO] Navigating to create page...")
            await self.page.goto(HEYGEN_CREATE_URL, timeout=PAGE_LOAD_TIMEOUT)
            await asyncio.sleep(6)

            # Click Upload audio button
            print("[INFO] Looking for Upload audio button...")
            clicked = False
            for sel in ['button:has-text("Upload audio")', ':text("Upload audio")', '[role="button"]:has-text("Upload audio")']:
                try:
                    btn = await self.page.wait_for_selector(sel, timeout=5000)
                    if btn:
                        await btn.click()
                        clicked = True
                        break
                except:
                    continue

            if not clicked:
                # Try clicking script area first
                try:
                    sa = await self.page.query_selector('text="Type your script"')
                    if sa:
                        await sa.click()
                        await asyncio.sleep(2)
                    btn = await self.page.wait_for_selector('button:has-text("Upload audio")', timeout=5000)
                    if btn:
                        await btn.click()
                        clicked = True
                except:
                    pass

            if not clicked:
                print("[ERROR] Could not find Upload audio button")
                await self.page.screenshot(path=os.path.expanduser("~/.openclaw/workspace/output/debug-heygen-upload.png"))
                return False

            await asyncio.sleep(3)

            # Click Upload Audio tab if present
            try:
                tab = await self.page.wait_for_selector('text="Upload Audio"', timeout=3000)
                if tab:
                    await tab.click()
                    await asyncio.sleep(1)
            except:
                pass

            # Make file input visible and upload
            await self.page.evaluate("""
                () => {
                    document.querySelectorAll('input[type="file"]').forEach(input => {
                        input.style.display = 'block';
                        input.style.opacity = '1';
                        input.style.position = 'relative';
                        input.style.width = '200px';
                        input.style.height = '50px';
                    });
                }
            """)
            await asyncio.sleep(1)

            fi = await self.page.query_selector('input[type="file"]')
            if not fi:
                print("[ERROR] No file input found")
                return False

            await fi.set_input_files(os.path.abspath(audio_path))
            print("[INFO] Audio uploaded")
            await asyncio.sleep(5)

            # Click uploaded file in list
            fname = os.path.basename(audio_path)
            try:
                item = await self.page.wait_for_selector(f'text="{fname}"', timeout=15000)
                if item:
                    await item.click()
                    await asyncio.sleep(1)
            except:
                pass

            # Click "Add audio" button
            try:
                add = await self.page.wait_for_selector('button:has-text("Add audio")', timeout=5000)
                if add:
                    await add.click()
                    await asyncio.sleep(3)
            except:
                pass

            # Wait for transcription
            print("[INFO] Waiting for transcription...")
            for _ in range(30):
                if await self.page.query_selector('button:has-text("Render")'):
                    break
                await asyncio.sleep(2)

            # Click Render
            print("[INFO] Rendering scene...")
            render_clicked = False
            for sel in ['button:has-text("Render")', 'button:has-text("Submit")']:
                try:
                    btn = await self.page.wait_for_selector(sel, timeout=5000)
                    if btn:
                        await btn.click()
                        render_clicked = True
                        break
                except:
                    continue

            if not render_clicked:
                print("[ERROR] Could not click Render")
                return False

            # Wait for render to complete
            start = time.time()
            while time.time() - start < RENDER_TIMEOUT / 1000:
                gen = await self.page.query_selector('button:has-text("Generate"):not([disabled])')
                if gen:
                    print(f"[INFO] Scene rendered ({int(time.time()-start)}s)")
                    break
                await asyncio.sleep(5)
                print(f"[INFO] Rendering... ({int(time.time()-start)}s)")

            # Generate 1080p
            print("[INFO] Generating 1080p...")
            gen = await self.page.query_selector('button:has-text("Generate"):not([disabled])')
            if not gen:
                print("[ERROR] No Generate button")
                return False
            await gen.click()
            await asyncio.sleep(2)

            # Select 1080p
            try:
                res = await self.page.query_selector('text="1080p"')
                if res:
                    await res.click()
                    await asyncio.sleep(1)
            except:
                pass

            # Submit/Confirm generation
            for txt in ["Submit", "Confirm", "Generate"]:
                try:
                    btn = await self.page.wait_for_selector(f'button:has-text("{txt}")', timeout=3000)
                    if btn:
                        await btn.click()
                        break
                except:
                    continue

            # Wait for generation
            start = time.time()
            video_url = None
            while time.time() - start < GENERATION_TIMEOUT / 1000:
                await asyncio.sleep(10)
                
                # Check for video element
                url = await self.page.evaluate("""
                    () => {
                        const v = document.querySelector('video');
                        if (v && v.src) return v.src;
                        const s = document.querySelector('video source');
                        if (s && s.src) return s.src;
                        return null;
                    }
                """)
                if url:
                    video_url = url
                    break

                # Check for download button
                dl = await self.page.query_selector('button:has-text("Download")')
                if dl:
                    print("[INFO] Download available, extracting URL...")
                    break

                print(f"[INFO] Generating... ({int(time.time()-start)}s)")

            if not video_url:
                # Try projects page
                await self.page.goto(HEYGEN_PROJECTS_URL, timeout=PAGE_LOAD_TIMEOUT)
                await asyncio.sleep(3)
                proj = await self.page.query_selector('[data-testid="project-card"]')
                if proj:
                    await proj.click()
                    await asyncio.sleep(3)
                    video_url = await self.page.evaluate("() => { const v = document.querySelector('video'); return v ? v.src : null; }")

            if not video_url:
                print("[ERROR] Could not get video URL")
                return False

            # Download
            print(f"[INFO] Downloading to {output_path}")
            r = requests.get(video_url, headers={
                'User-Agent': 'Mozilla/5.0',
                'Referer': 'https://app.heygen.com/'
            }, stream=True)
            if r.status_code == 200:
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                with open(output_path, 'wb') as f:
                    for chunk in r.iter_content(8192):
                        f.write(chunk)
                print(f"[SUCCESS] {output_path}")
                return True
            else:
                print(f"[ERROR] Download HTTP {r.status_code}")
                return False

        except Exception as e:
            print(f"[ERROR] {e}")
            return False


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--segment", help="Single segment name")
    args = parser.parse_args()

    audio_dir = Path(args.audio_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    audio_files = sorted(audio_dir.glob("*.mp3"))
    if args.segment:
        audio_files = [f for f in audio_files if f.stem == args.segment]

    if not audio_files:
        print("[ERROR] No audio files")
        sys.exit(1)

    print(f"[INFO] {len(audio_files)} audio files to process")
    results = {}

    async with HeyGenCDP() as hg:
        if not await hg.check_login():
            sys.exit(1)

        for af in audio_files:
            sid = af.stem
            out = output_dir / f"{sid}.mp4"
            if out.exists():
                print(f"[SKIP] {out}")
                results[sid] = str(out)
                continue

            ok = await hg.render_segment(str(af), str(out))
            results[sid] = str(out) if ok else None
            await asyncio.sleep(3)

    sc = sum(1 for v in results.values() if v)
    print(f"\n[SUMMARY] {sc}/{len(results)} succeeded")
    for sid, p in results.items():
        print(f"  {'[OK]' if p else '[FAIL]'} {sid}: {p or 'FAILED'}")

    with open(output_dir / "render_results.json", "w") as f:
        json.dump({"timestamp": datetime.now().isoformat(), "results": results, "success_count": sc, "total_count": len(results)}, f, indent=2)

    sys.exit(0 if sc == len(results) else 1)

if __name__ == "__main__":
    asyncio.run(main())

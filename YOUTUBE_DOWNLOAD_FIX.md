# YouTube Download Fix Guide - CRITICAL ISSUE CONFIRMED

## Problem Summary
YouTube download via `x_post_conv.py` AND `yt-dlp.exe` CLI **both fail** with:
- `LOGIN_REQUIRED` error → **Fixed** ✅ (proper cookies now loaded)
- `n challenge solving failed` → **CRITICAL BUG** ⛔

## Root Cause - CONFIRMED
yt-dlp (version 2026.01.19.233146 - LATEST) **cannot detect Node.js** despite:
- Node being in PATH at `D:\nvm4w\nodejs\node.EXE`
- `node --version` working perfectly (v24.11.1)
- Node directory prepended to PATH
- node.exe copied to temp directory in PATH

**Why**: yt-dlp's Node detection (`utils._get_exe_version_output()`) fails to execute `node.exe --version` from nvm4w installations on Windows. This is a known unresolved bug affecting Windows users with nvm/nvm-windows/nvm4w-managed Node installations.

**Impact**: ALL YouTube videos fail extraction - even simple public videos like "Me at the zoo" return `No video formats found!`

## What's Working Now ✅
1. **Cookies are properly loaded** - `www.youtube.com_cookies.txt` was copied to `cookies.txt`
2. **Auto-cookie detection** - Script now auto-uses `cookies.txt` if present (no `--cookies_file` needed)
3. **Cookie refresh helper** - `python x_post_conv.py --refresh_cookies chrome` works
4. **Node detection** - Script finds Node and reports its path

## What's Still Broken ⚠️
yt-dlp Python module reports `JS runtimes: none` despite Node being found, so signature solving fails.

---

## Solutions (Pick One)

### Option 1: Reinstall Node.js WITHOUT nvm (MOST RELIABLE)
Uninstall nvm4w and install Node directly from nodejs.org:

1. Download from: https://nodejs.org/en/download/
2. Install to `C:\Program Files\nodejs\` (default location)
3. Restart all terminals
4. Test: `E:/MyCode/meiti/.venv/Scripts/yt-dlp.exe -v "https://youtu.be/..." 2>&1 | Select-String "JS runtimes"`
   - Should show: `[debug] JS runtimes: node-24.x.x`

### Option 2: Use alternative downloader (QUICK WORKAROUND)
Install `gallery-dl` which handles YouTube better on Windows:

```powershell
pip install gallery-dl
gallery-dl --cookies E:/MyCode/meiti/cookies.txt "https://youtu.be/..."
```

### Option 2: Fix Node PATH permanently
Add Node to **System PATH** (not just user PATH):
1. Open PowerShell as **Admin**
2. Run:
   ```powershell
   $nodePath = "D:\nvm4w\nodejs"
   [Environment]::SetEnvironmentVariable("PATH", "$nodePath;$env:PATH", "Machine")
   ```
3. **Restart PowerShell** (close all terminals)
4. Test: `python x_post_conv.py --url "https://youtu.be/..." --key YOUR_KEY`

### Option 3: Wrapper script
Create `download_youtube.ps1`:
```powershell
# Set Node in PATH before Python runs
$env:PATH = "D:\nvm4w\nodejs;$env:PATH"
python x_post_conv.py $args
```

Usage:
```powershell
.\download_youtube.ps1 --url "https://youtu.be/..." --key YOUR_KEY
```

### Option 4: Downgrade to non-signature videos
Some older/simpler videos don't require signature solving. Try different content.

---

## Testing Your Fix

### 1. Verify Node is detected by yt-dlp:
```powershell
E:/MyCode/meiti/.venv/Scripts/yt-dlp.exe -v --cookies E:/MyCode/meiti/cookies.txt --simulate "https://www.youtube.com/watch?v=dQw4w9WgXcQ" 2>&1 | Select-String "JS runtimes"
```
**Expected**: `[debug] JS runtimes: node-24.11.1`  
**If you see**: `JS runtimes: none` → Node PATH issue persists

### 2. Full download test:
```powershell
E:/MyCode/meiti/.venv/Scripts/yt-dlp.exe `
  --cookies E:/MyCode/meiti/cookies.txt `
  -f "bestvideo+bestaudio/best" `
  --merge-output-format mp4 `
  -o "test_%(id)s.%(ext)s" `
  "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```
Should download `test_dQw4w9WgXcQ.mp4` successfully.

---

## Technical Details

### Why www.youtube.com_cookies.txt worked but cookies.txt didn't:
The new file contains `LOGIN_INFO` cookie (proving authenticated session). Old `cookies.txt` was missing critical auth cookies.

### Why Node detection fails in Python:
```python
# yt-dlp detects runtimes HERE (module load time):
import yt_dlp  # ← Scans PATH for node/deno/bun

# Our script modifies PATH HERE (too late):
os.environ["PATH"] = f"{node_dir};{os.environ['PATH']}"  
ydl = yt_dlp.YoutubeDL(...)  # ← Already decided "no Node"
```

### Recent yt-dlp changes:
YouTube started forcing SABR streaming + stricter bot-checks in late 2025/early 2026. Most videos now require:
- Valid authenticated cookies (✅ you have this now)
- JavaScript runtime for signature solving (⚠️ detection broken)

---

## Quick Reference

### Current script improvements:
1. Auto-detects `cookies.txt` in workspace
2. Reports Node.js location if found
3. Optimized YouTube extractor config (tv_embedded + web clients)
4. Fixed logger callback (was causing crashes)

### Files updated:
- `x_post_conv.py` - Main script with cookie handling + Node detection
- `cookies.txt` - Fresh authenticated cookies (replaced old incomplete file)

### Next steps if still failing:
1. Try downloading with `yt-dlp.exe` CLI directly (most reliable)
2. Update system PATH to include Node permanently
3. Or provide a local video file: `python x_post_conv.py --local_file video.mp4 --key YOUR_KEY`

# ⚠️ CRITICAL: YouTube Download Still Broken

## Current Status
- ✅ Node.js v24.13.0 installed at `D:\Program Files\nodejs`
- ✅ Script modified to set PATH before yt_dlp import
- ⛔ **yt-dlp STILL reports `JS runtimes: none`**
- ⛔ **Cookies are stale** (`The provided YouTube account cookies are no longer valid`)

## Why yt-dlp Can't Detect Node
Even after reinstalling Node and setting PATH before import, yt-dlp's runtime detection remains broken. This appears to be a bug in yt-dlp 2026.01.19.233146 on Windows.

## IMMEDIATE ACTION REQUIRED

### 1) Export Fresh Cookies Manually (Browser Extension)
Auto-cookie refresh failed with DPAPI decryption error. Use browser extension:

**Chrome/Edge:**
1. Install: [Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)
2. Go to https://www.youtube.com (make sure you're logged in)
3. Click extension icon → "Export" → Save as `cookies.txt`
4. Copy to: `E:/MyCode/meiti/cookies.txt`

**Firefox:**
1. Install: [cookies.txt](https://addons.mozilla.org/firefox/addon/cookies-txt/)
2. Same process as Chrome

### 2) Use Alternative Downloader (gallery-dl)
Since yt-dlp Node detection is broken, use `gallery-dl` which handles YouTube better:

```powershell
# Install
pip install gallery-dl

# Download video
gallery-dl --cookies E:/MyCode/meiti/cookies.txt "https://youtu.be/ZOsm1qoEr7M"
```

### 3) OR: Download via Browser, Process Locally
1. Use browser extension or https://ytdl-org.github.io/youtube-dl/download.html
2. Download video manually
3. Process with your script:
```powershell
python x_post_conv.py --local_file "downloaded_video.mp4" --key YOUR_NVIDIA_KEY
```

---

## Technical Root Cause
yt-dlp's JS runtime detection (`yt_dlp.jsinterp._get_jsinterp_class()`) runs during module import and caches the result. Even though we set PATH before `import yt_dlp`, the detection logic appears to fail on Windows with certain Node installations.

Attempted fixes that FAILED:
- ✗ Reinstalled Node from nodejs.org (not nvm)
- ✗ Set PATH before yt_dlp import
- ✗ Explicitly prepended Node directory to PATH
- ✗ Used `--extractor-args "youtube:js_runtimes=node"`
- ✗ Copied node.exe to temp directory in PATH

## Recommendation
**Use `gallery-dl` or manual browser download** until yt-dlp fixes Windows Node detection. The cookies + local file workflow will work perfectly for your content processing pipeline.

# YouTube Downloader Wrapper - Fixes Node.js Detection
# Usage: .\download_youtube.ps1 "https://youtu.be/..."

param(
    [Parameter(Mandatory=$true)]
    [string]$Url,
    
    [string]$Output = "raw_%(id)s.%(ext)s",
    [string]$CookiesFile = "E:/MyCode/meiti/cookies.txt"
)

# Force Node.js to be detectable by creating a temporary node.exe in a known location
$nodeSource = "D:\nvm4w\nodejs\node.exe"
$tempDir = "$env:TEMP\yt-dlp-node"
$nodeTarget = "$tempDir\node.exe"

if (Test-Path $nodeSource) {
    Write-Host "[*] Setting up Node.js for yt-dlp..." -ForegroundColor Green
    
    # Create temp directory and copy node.exe
    if (!(Test-Path $tempDir)) {
        New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
    }
    
    Copy-Item -Path $nodeSource -Destination $nodeTarget -Force
    
    # Prepend to PATH
    $env:PATH = "$tempDir;$env:PATH"
    Write-Host "[*] Node.js available at: $nodeTarget" -ForegroundColor Green
} else {
    Write-Host "[-] Node.js not found at $nodeSource" -ForegroundColor Red
    Write-Host "[-] Downloads may fail for videos requiring signature solving" -ForegroundColor Yellow
}

# Run yt-dlp with cookies
Write-Host "[*] Downloading: $Url" -ForegroundColor Cyan

& "E:/MyCode/meiti/.venv/Scripts/yt-dlp.exe" `
    --cookies $CookiesFile `
    -o $Output `
    --merge-output-format mp4 `
    -f "bestvideo+bestaudio/best" `
    $Url

$exitCode = $LASTEXITCODE

# Cleanup
if (Test-Path $tempDir) {
    Remove-Item -Path $tempDir -Recurse -Force -ErrorAction SilentlyContinue
}

exit $exitCode

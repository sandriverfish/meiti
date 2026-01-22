import os
import sys
import subprocess

# CRITICAL: Set PATH before importing yt_dlp so it can detect Node.js runtime
# yt-dlp detects JS runtimes at import time, not when YoutubeDL() runs
node_dirs = [
    r"D:\Program Files\nodejs",  # Standard install location
    r"C:\Program Files\nodejs",  # Alternative install location
]
for node_dir in node_dirs:
    if os.path.isdir(node_dir) and node_dir not in os.environ.get("PATH", ""):
        os.environ["PATH"] = f"{node_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        break

import json
import datetime
import requests
import yt_dlp
import whisper
from openai import OpenAI
from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip, AudioFileClip
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import re
import emoji
import textwrap
import shutil
from deep_translator import GoogleTranslator


class XPostSkill:
    def __init__(
        self,
        url,
        nvidia_key,
        target_lang="zh",
        model_name="meta/llama-3.1-405b-instruct",
        cookies_browser=None,
        cookies_file=None,
        local_file=None,
        whisper_model="medium",
    ):
        self.url = url
        self.nvidia_key = nvidia_key
        self.target_lang = target_lang
        self.model_name = model_name
        self.cookies_browser = cookies_browser
        self.cookies_file = cookies_file
        self.local_file = local_file
        self.whisper_model = whisper_model
        self.task_dir = None
        self.client = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1", 
            api_key=self.nvidia_key,
            timeout=30.0
        )
        # Font setup
        self.font_path = "arial.ttf"
        possible_fonts = [
            r"C:\Windows\Fonts\msyh.ttc",  # Microsoft YaHei
            r"C:\Windows\Fonts\simhei.ttf",  # SimHei
            r"C:\Windows\Fonts\msyhl.ttc",
        ]
        for f in possible_fonts:
            if os.path.exists(f):
                self.font_path = f
                break
        print(f"[*] Using font: {self.font_path}")

    def _yt_dlp_logger(self, msg):
        if isinstance(msg, dict):
            level = msg.get("level", "info")
            message = msg.get("msg", str(msg))
            if level == "debug":
                print(f"[yt-dlp debug] {message}")
            elif level == "info":
                print(f"[yt-dlp info] {message}")
            elif level == "warning":
                print(f"[yt-dlp warning] {message}")
            elif level == "error":
                print(f"[yt-dlp error] {message}")
        else:
            print(f"[yt-dlp] {msg}")

    @staticmethod
    def refresh_cookies(browser="chrome", output_file="cookies.txt"):
        """Refresh YouTube cookies from browser. Call this when downloads fail due to auth issues."""
        import subprocess

        print(f"[*] Refreshing cookies from {browser}...")
        try:
            # Prefer the current Python environment's yt-dlp module to avoid PATH issues
            # (common when users run inside a venv on Windows).
            cmd = [
                sys.executable,
                "-m",
                "yt_dlp",
                "--cookies-from-browser",
                browser,
                "--cookies",
                output_file,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"[*] Cookies refreshed successfully: {output_file}")
                return True
            else:
                print(f"[-] Failed to refresh cookies: {result.stderr}")
                return False
        except FileNotFoundError:
            print(
                "[-] Python/yt-dlp not found in this environment. Install with: pip install yt-dlp"
            )
            return False

    def run(self):
        print(f"[*] Starting processing for {self.url}")

        # 1. Download (or use local)
        data = self._download()
        if not data:
            print("[-] Download/Local file setup failed.")
            return

        # Setup Folder
        date_str = datetime.datetime.now().strftime("%Y%m%d")
        # Sanitize summary for folder name
        safe_content = re.sub(r'[\\/*?:"<>|\n\r]', "", data["content"]).strip()
        safe_summary = (
            (safe_content[:20] + "_more") if len(safe_content) > 20 else safe_content
        )
        safe_summary = safe_summary.replace(" ", "_")

        self.task_dir = os.path.join("tasks", f"{date_str}_{safe_summary}")
        os.makedirs(self.task_dir, exist_ok=True)
        print(f"[*] Task directory: {self.task_dir}")

        # Save Raw Metadata
        with open(os.path.join(self.task_dir, "raw.json"), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        # 2. Translate Text (Cleaned)
        clean_content = self._clean_text(data["content"])
        translated_text = self._translate(clean_content)
        print(f"[*] Translated Text: {translated_text}")

        # 3. Process Media
        media_files = []
        if data.get("video_path"):
            processed_video, srt_path = self._process_video(
                data["video_path"], translated_text
            )
            media_files.append(processed_video)
            if srt_path:
                print(f"[*] SRT generated: {srt_path}")

        # 4. Create Markdown
        self._create_markdown(data, translated_text, media_files)
        print("[*] Done!")

    def _download(self):
        print("[*] Checking content...")

        # Handle Local File
        if self.local_file:
            print(f"[*] Using local file: {self.local_file}")
            if not os.path.exists(self.local_file):
                print(f"[-] Local file not found: {self.local_file}")
                return None

            # Create a dummy metadata object from video info if possible, or generic
            return {
                "id": "local_video",
                "content": f"Processing local video: {os.path.basename(self.local_file)}",
                "video_path": os.path.abspath(self.local_file),
                "uploader": "Local User",
                "upload_date": datetime.datetime.now().strftime("%Y%m%d"),
            }

        try:
            import imageio_ffmpeg

            ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
            print(f"[*] Found ffmpeg at: {ffmpeg_path}")
        except ImportError:
            ffmpeg_path = None
            print("[-] imageio_ffmpeg not found, relying on system PATH")

        ydl_opts = {
            "format": "bestvideo+bestaudio/best",
            "merge_output_format": "mp4",
            "outtmpl": "temp_%(id)s.%(ext)s",
            "quiet": False,
            "verbose": True,
        }

        if ffmpeg_path:
            ydl_opts["ffmpeg_location"] = os.path.dirname(ffmpeg_path)

        # Detect Node.js for YouTube signature decryption (required for many videos)
        # yt-dlp's subprocess detection often fails; add Node dir to PATH explicitly.
        if "youtube.com" in self.url or "youtu.be" in self.url:
            node_path = shutil.which("node")
            if node_path:
                node_dir = os.path.dirname(node_path)
                print(f"[*] Found Node.js at: {node_path}")
                # Prepend Node directory to PATH so yt-dlp's subprocess can find it
                current_path = os.environ.get("PATH", "")
                if node_dir not in current_path:
                    os.environ["PATH"] = f"{node_dir}{os.pathsep}{current_path}"
                    print(f"[*] Added Node directory to PATH for yt-dlp")
            else:
                print(
                    "[-] Warning: Node.js not found in PATH. Some YouTube videos may fail."
                )
                print(
                    "[-] Install Node.js: https://nodejs.org/ or winget install OpenJS.NodeJS.LTS"
                )

        if self.cookies_file:
            cookie_path = os.path.abspath(self.cookies_file)
            if not os.path.exists(cookie_path):
                print(f"[-] Cookies file not found: {cookie_path}")
                return None
            ydl_opts["cookiefile"] = cookie_path
            print(f"[*] Using cookies from file: {cookie_path}")
        elif self.cookies_browser:
            ydl_opts["cookiesfrombrowser"] = (self.cookies_browser, None, None, None)
            print(f"[*] Using cookies from browser: {self.cookies_browser}")

        # YouTube extractor: use tv_embedded client which often bypasses bot checks
        # and doesn't require signature solving (no JS runtime needed).
        # Falls back to web client if tv_embedded fails.
        if "youtube.com" in self.url or "youtu.be" in self.url:
            extractor_args = ydl_opts.get("extractor_args") or {}
            youtube_args = extractor_args.get("youtube") or {}
            youtube_args.setdefault("player_client", ["tv_embedded", "web"])
            extractor_args["youtube"] = youtube_args
            ydl_opts["extractor_args"] = extractor_args

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # 1. Fetch Metadata first (fast)
                info = ydl.extract_info(self.url, download=False)

                content = info.get("description") or info.get("title") or ""
                predicted_filename = ydl.prepare_filename(info)
                final_video_name = os.path.basename(predicted_filename)

                # PREDICT TASK DIR to check for existing RAW file
                # Logic must match run()
                date_str = datetime.datetime.now().strftime("%Y%m%d")
                safe_content = re.sub(r'[\\/*?:"<>|\n\r]', "", content).strip()
                safe_summary = (
                    (safe_content[:20] + "_more")
                    if len(safe_content) > 20
                    else safe_content
                )
                safe_summary = safe_summary.replace(" ", "_")
                predicted_task_dir = os.path.join("tasks", f"{date_str}_{safe_summary}")

                # Check for "raw_{filename}" in task dir
                existing_raw_path = os.path.join(
                    predicted_task_dir, f"raw_{final_video_name}"
                )
                if os.path.exists(existing_raw_path):
                    print(
                        f"[*] Found existing RAW file in task dir: {existing_raw_path}"
                    )
                    # Return absolute path so it can be used
                    return {
                        "id": info.get("id"),
                        "content": content,
                        "video_path": os.path.abspath(existing_raw_path),
                        "uploader": info.get("uploader"),
                        "upload_date": info.get("upload_date"),
                    }

                # Check if we have it in CWD (temp from interrupted run)
                import glob

                temp_files = glob.glob(f"temp_{info.get('id', '*')}.*")
                if temp_files:
                    print(f"[*] Found existing temp file: {temp_files[0]}")
                    return {
                        "id": info.get("id"),
                        "content": content,
                        "video_path": temp_files[0],
                        "uploader": info.get("uploader"),
                        "upload_date": info.get("upload_date"),
                    }

                print("[*] Downloading media...")
                error_code = ydl.download([self.url])

                if error_code != 0:
                    print(f"[-] yt-dlp download failed with error code: {error_code}")
                    return None

                import glob

                temp_files = glob.glob(f"temp_{info.get('id', '*')}.*")
                if temp_files:
                    actual_filename = temp_files[0]
                    print(f"[*] Found downloaded file: {actual_filename}")
                    return {
                        "id": info.get("id"),
                        "content": content,
                        "video_path": actual_filename,
                        "uploader": info.get("uploader"),
                        "upload_date": info.get("upload_date"),
                    }

                print(
                    f"[-] Download completed but file not found. Expected: {predicted_filename}"
                )
                return None
        except Exception as e:
            print(f"[-] Download error: {e}")
            return None

    def _translate(self, text):
        # Using Deep Translator (Google) instead of NVIDIA/OpenAI
        print("[*] Translating text (Google)...")
        if not text:
            return ""
        try:
            # target_lang is 'zh', but GoogleTranslator uses 'zh-CN' usually or 'zh-TW'.
            # 'zh' maps to Simplified Chinese in Google Translate usually.
            translator = GoogleTranslator(source='auto', target='zh-CN')
            return translator.translate(text)
        except Exception as e:
            print(f"[-] Translation error: {e}")
            return text

    def _translate_batch(self, texts):
        """
        Translate a batch of texts using the LLM.
        Now attempts to identify speakers and improve quality.
        Returns a list of dicts: [{'translated': '...', 'speaker': 'A'}, ...]
        """
        print(f"[*] Translating {len(texts)} segments in batch...")
        
        system_prompt = (
            "You are a professional subtitle translator. Translate the following English subtitles to Chinese (Simplified).\n"
            "Rules:\n"
            "1. Output must be a VALID JSON list of objects.\n"
            "2. Each object must have: 'original' (str), 'translated' (str), and 'speaker' (str).\n"
            "3. 'speaker' should be 'A' for the main/first speaker, 'B' for a second speaker (if detected), etc. "
            "If unsure or monologue, default to 'A'.\n"
            "4. Keep the translation concise and natural. Do not summarize.\n"
            "5. Maintain the same number of items as the input.\n"
            "6. Input will be a JSON list of strings.\n"
        )

        # Split into chunks to avoid context limit (approx 50 segments per chunk)
        chunk_size = 50
        all_results = []

        for i in range(0, len(texts), chunk_size):
            chunk = texts[i : i + chunk_size]
            user_content = json.dumps(chunk, ensure_ascii=False)

            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content},
                    ],
                    temperature=0.3,
                    max_tokens=4000,
                )
                
                # ... (Existing batch logic using LLM is removed/replaced)
                # Google Translate doesn't support complex JSON batching in the same way 
                # effectively without risking blocks or needing iterators.
                # We will fall back to individual translation for quality/safety with deep-translator
                # or simple list iteration.
                
                # Legacy cleanup
                pass
            except Exception:
                pass
        
        # Override to just use loop since we dropped LLM
        return self._translate_individual(texts)


        # Ensure alignment
        if len(all_results) != len(texts):
            print(f"[-] Warning: Translation count mismatch ({len(all_results)} vs {len(texts)}). adjusting...")
            # Pad or truncate if necessary (simple fallback)
            if len(all_results) < len(texts):
                for k in range(len(all_results), len(texts)):
                    all_results.append({"translated": texts[k], "speaker": "A"})
            else:
                all_results = all_results[:len(texts)]

        return all_results

    def _translate_individual(self, texts):
        print(f"[*] Translating {len(texts)} segments individually...")
        results = []
        for i, t in enumerate(texts):
            if (i + 1) % 5 == 0:
                print(f"[*] Progress: {i + 1}/{len(texts)}")
            results.append(self._translate(t))
        return results

    def _transcribe(self, audio_path):
        print(f"[*] Transcribing audio (using '{self.whisper_model}' model)...")
        try:
            model = whisper.load_model(self.whisper_model)
            # Force English to avoid hallucination/language drift
            result = model.transcribe(audio_path, language="en")
            return result
        except Exception as e:
            print(f"[-] Transcription error: {e}")
            return None

    def _clean_text(self, text):
        # Remove URLs
        text = re.sub(r"https?://\S+", "", text)
        # Remove Emojis
        text = emoji.replace_emoji(text, replace="")
        # Remove extra whitespace
        text = re.sub(r"\s+", " ", text).strip()
        return text


    def _generate_srt(self, segments, output_path):
        print(f"[*] Generating SRT: {output_path}")

        def format_time(seconds):
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            seconds = seconds % 60
            millis = int((seconds - int(seconds)) * 1000)
            return f"{hours:02}:{minutes:02}:{int(seconds):02},{millis:03}"

        try:
            with open(output_path, "w", encoding="utf-8") as f:
                for i, seg in enumerate(segments):
                    start = format_time(seg["start"])
                    end = format_time(seg["end"])
                    text = seg["translated"]
                    f.write(f"{i + 1}\n")
                    f.write(f"{start} --> {end}\n")
                    f.write(f"{text}\n\n")
            return output_path
        except Exception as e:
            print(f"[-] SRT generation error: {e}")
            return None

    def _format_time_ass(self, seconds):
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        centis = int((secs - int(secs)) * 100)
        return f"{hours}:{minutes:02}:{int(secs):02}.{centis:02}"

    def _generate_ass(self, segments, output_path, margin_v=50):
        print(f"[*] Generating ASS: {output_path} (MarginV={margin_v})")
        
        header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 1

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Microsoft YaHei,60,&H0000FFFF,&H000000FF,&H00000000,&H60000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,{margin_v},1
Style: SpeakerA,Microsoft YaHei,60,&H0000FFFF,&H000000FF,&H00000000,&H60000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,{margin_v},1
Style: SpeakerB,Microsoft YaHei,60,&H00FFFF00,&H000000FF,&H00000000,&H60000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,{margin_v},1
Style: SpeakerC,Microsoft YaHei,60,&H0000FF00,&H000000FF,&H00000000,&H60000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(header)
                for seg in segments:
                    start = self._format_time_ass(seg["start"])
                    end = self._format_time_ass(seg["end"])
                    text = seg["translated"]
                    speaker = seg.get("speaker", "A")
                    
                    style = "SpeakerA"
                    if speaker == "B":
                        style = "SpeakerB"
                    elif speaker == "C":
                        style = "SpeakerC"
                    elif speaker == "A":
                        style = "SpeakerA"
                    else:
                        style = "Default"
                    
                    text = text.replace("\n", " ").strip()
                    line = f"Dialogue: 0,{start},{end},{style},,0,0,0,,{text}\n"
                    f.write(line)
            return output_path
        except Exception as e:
            print(f"[-] ASS generation error: {e}")
            return None

    def _burn_subtitles_ffmpeg(self, video_path, sub_path, output_path):
        print(f"[*] Burning subtitles with FFMPEG...")
        print(f"Input: {video_path}")
        print(f"Subtitles: {sub_path}")
        
        # We use relative paths to avoid Windows path escaping hell in filters
        cwd = os.path.dirname(os.path.abspath(output_path)) # Execute in task dir
        
        # Ensure files are available relative to cwd
        # Ideally video_path and sub_path are in cwd or absolute.
        # If they are absolute and on different drives, relpath fails.
        # So we'll try to rely on them being in the same task_dir usually.
        
        try:
             # Ensure absolute paths for FFMPEG to avoid ambiguity
             abs_input = os.path.abspath(video_path)
             abs_sub = os.path.abspath(sub_path)
             # Windows FFMPEG filter path escaping:
             # 1. Drive letter colon (C:) -> C\:
             # 2. Backslashes (\) -> /
             abs_sub_escaped = abs_sub.replace("\\", "/").replace(":", "\\:")
             
             rel_output = os.path.basename(output_path)
             
             # Verify files exist
             if not os.path.exists(abs_input):
                 print(f"[-] Input video missing: {abs_input}")
                 return False
             if not os.path.exists(abs_sub):
                 print(f"[-] Subtitle file missing: {abs_sub}")
                 return False

             cmd = [
                "ffmpeg",
                "-y",
                "-i", abs_input,
                "-vf", f"subtitles='{abs_sub_escaped}'",
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "23",
                "-c:a", "copy",
                rel_output
             ]
             
             print(f"Command: {' '.join(cmd)}")
             subprocess.run(cmd, cwd=cwd, check=True)
             print(f"[*] FFMPEG success: {output_path}")
             return True
             
        except Exception as e:
             print(f"[-] FFMPEG error: {e}")
             return False

    def _process_video(self, video_path, summary_text):
        print(f"[*] Processing video: {video_path}")

        final_video_name = os.path.basename(video_path)
        # Handle case where input is already 'raw_...' (don't double prefix)
        if final_video_name.startswith("raw_"):
            final_video_name = final_video_name[4:]

        # Create unique task directory based on filename and date
        clean_name = re.sub(r'[\\/*?:"<>|]', "", final_video_name)
        clean_name = clean_name.replace(" ", "_").replace(".mp4", "")
        # Limit length
        if len(clean_name) > 30:
            clean_name = clean_name[:30] + "_etc"
            
        date_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.task_dir = os.path.join("tasks", f"{date_str}_{clean_name}")
        os.makedirs(self.task_dir, exist_ok=True)
        print(f"[*] Task directory: {self.task_dir}")
        
        # Audio Extraction Path
        audio_path = os.path.join(self.task_dir, "audio.mp3")
        
        # Detect Aspect Ratio
        margin_v = 50 # Default Landscape
        try:
             import imageio_ffmpeg
             # Simple probe using ffmpeg to get width/height
             # We rely on previous ffmpeg knowledge or we can use moviepy
             # Since we use VideoFileClip below, let's use that.
             # Postpone open to here
             print("[*] Extracting audio and checking AR...")
             video_clip = VideoFileClip(video_path)
             w, h = video_clip.size
             if h > w:
                 print(f"[*] Portrait Video Detected ({w}x{h}). Adjusting subtitles.")
                 margin_v = 350 # Higher margin for portrait
             else:
                 print(f"[*] Landscape/Square Video Detected ({w}x{h}).")
             
             if video_clip.audio:
                 video_clip.audio.write_audiofile(audio_path, verbose=False, logger=None)
             video_clip.close()
        except Exception as e:
            print(f"[-] Audio/AR check failed: {e}")
            return None, None

        # Check for Manual Translation Override
        manual_json_path = os.path.join(self.task_dir, "translation_check.json")

        try:
            # NORMAL FLOW
            # Transcribe with timestamps
            transcript_result = self._transcribe(audio_path)
            
            final_segments_for_render = []

            if (
                transcript_result
                and "segments" in transcript_result
                and transcript_result["segments"]
            ):
                print("[*] Using transcript for subtitles...")

                segments = transcript_result["segments"]
                original_texts = [
                    self._clean_text(seg["text"])
                    for seg in segments
                    if self._clean_text(seg["text"])
                ]

                # Translate with Speaker ID
                translated_results = []
                if original_texts:
                    translated_results = self._translate_batch(original_texts)

                # Validation & Retry Logic for Empty Translations
                print("[*] Validating translations...")
                for i, item in enumerate(translated_results):
                    needs_retry = False
                    if isinstance(item, dict):
                        if not item.get("translated"):
                             needs_retry = True
                             print(f"[-] Empty translation at index {i}. Retrying...")
                    else:
                         # Likely string fallback or weird format
                         if not item:
                             needs_retry = True
                    
                    if needs_retry:
                        # Retry individual
                        retry_text = original_texts[i]
                        try:
                           retry_res = self._translate(retry_text)
                           if isinstance(item, dict):
                               item["translated"] = retry_res
                           else:
                               # If it was a string or something else, update the list 
                               # Note: logic below expects dict or string, 
                               # but _translate_batch is supposed to return dicts.
                               # If we are here, we modify the item in place if dict.
                               pass 
                           # Force update in list if it was strictly empty string
                           if not isinstance(item, dict):
                               translated_results[i] = {"translated": retry_res, "speaker": "A"}
                        except Exception as e:
                           print(f"[-] Retry failed for index {i}: {e}")

                # Use results
                text_idx = 0
                debug_data = []

                for seg in segments:
                    original_txt = self._clean_text(seg["text"])
                    if not original_txt:
                        continue
                    
                    # Default
                    display_txt = original_txt
                    speaker = "A"
                    
                    if text_idx < len(translated_results):
                        item = translated_results[text_idx]
                        if isinstance(item, dict):
                            display_txt = item.get("translated", original_txt)
                            speaker = item.get("speaker", "A")
                        else:
                            display_txt = str(item) # Fallback

                    debug_data.append(
                        {
                            "start": seg["start"],
                            "end": seg["end"],
                            "original": original_txt,
                            "translated": display_txt,
                            "speaker": speaker
                        }
                    )
                    
                    text_idx += 1
                
                final_segments_for_render = debug_data

                # Write debug file
                with open(
                    os.path.join(self.task_dir, "translation_check.json"),
                    "w",
                    encoding="utf-8",
                ) as f:
                    json.dump(debug_data, f, indent=2, ensure_ascii=False)

            else:
                # Fallback: Overlay translated summary (single segment)
                print(
                    "[*] No transcript found (silent video?). Creating summary subtitle..."
                )
                clean_summary = self._clean_text(summary_text)
                display_text = (
                    clean_summary[:50] + "..."
                    if len(clean_summary) > 50
                    else clean_summary
                )
                
                # We need duration. MoviePy clip provided it.
                # Re-open or use ffmpeg probe (skipping probe for complexity, re-open minimal)
                try:
                     vc = VideoFileClip(video_path)
                     duration = vc.duration
                     vc.close()
                except:
                     duration = 10 # Fallback
                
                final_segments_for_render = [{
                    "start": 0,
                    "end": duration,
                    "translated": display_text,
                    "speaker": "A"
                }]

            # GENERATE SUBTITLES (ASS)
            ass_path = os.path.join(self.task_dir, "captions.ass")
            self._generate_ass(final_segments_for_render, ass_path, margin_v=margin_v)
            
            # GENERATE SRT (for optional use)
            srt_path = os.path.join(self.task_dir, "captions.srt")
            self._generate_srt(final_segments_for_render, srt_path)

            # RENDER VIDEO (FFMPEG)
            output_path = os.path.join(self.task_dir, f"processed_{final_video_name}")
            
            success = self._burn_subtitles_ffmpeg(video_path, ass_path, output_path)
            if not success:
                print("[-] FFMPEG rendering failed. Attempting legacy MoviePy method not supported anymore.")
            
            # Cleanup Raw: Attempt to move
            input_abs = os.path.abspath(video_path)
            raw_dest_abs = os.path.abspath(
                os.path.join(self.task_dir, f"raw_{final_video_name}")
            )

            if input_abs != raw_dest_abs:
                try:
                    if os.path.exists(raw_dest_abs):
                        os.remove(raw_dest_abs)
                    if os.path.exists(video_path): # Ensure source exists
                         os.rename(video_path, raw_dest_abs)
                except Exception as e:
                    print(f"[-] Warning: Failed to move raw file: {e}")

            return output_path, srt_path

        except Exception as e:
            print(f"[-] Video processing error: {e}")
            import traceback
            traceback.print_exc()
            target_path = os.path.join(self.task_dir, final_video_name) if self.task_dir else None
            return target_path, None


    def _create_markdown(self, data, translated_text, media_files):
        print("[*] Creating Markdown...")
        md_content = f"""# {data["content"][:50]}...

**Date**: {data["upload_date"]}
**Uploader**: {data["uploader"]}
**Original URL**: {self.url}

## Content
### Original
{self._clean_text(data["content"])}

### Translation ({self.target_lang})
{translated_text}

## Media
"""
        for m in media_files:
            md_content += f"![Video]({os.path.basename(m)})\n"

        with open(os.path.join(self.task_dir, "post.md"), "w", encoding="utf-8") as f:
            f.write(md_content)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--url", help="Twitter/X URL")
    parser.add_argument("--key", help="Nvidia API Key")
    parser.add_argument(
        "--cookies_browser", help="Browser to load cookies from (e.g. chrome, firefox)"
    )
    parser.add_argument(
        "--cookies_file", help="Path to Netscape formatted cookies.txt file"
    )
    parser.add_argument(
        "--local_file", help="Path to local video file to process (skips download)"
    )
    parser.add_argument(
        "--refresh_cookies",
        help="Refresh YouTube cookies from browser",
        metavar="BROWSER",
    )
    parser.add_argument(
        "--model_size",
        help="Whisper model size (tiny, base, small, medium, large)",
        default="medium"
    )
    args = parser.parse_args()

    if args.refresh_cookies:
        XPostSkill.refresh_cookies(args.refresh_cookies)
        exit(0)

    if not args.url or not args.key:
        parser.error("the following arguments are required: --url and --key")

    # Convenience: if user already has a Netscape cookies.txt in CWD, use it by default
    # unless an explicit cookie source was provided.
    if not args.cookies_file and not args.cookies_browser:
        default_cookie = os.path.join(os.getcwd(), "cookies.txt")
        if os.path.exists(default_cookie):
            args.cookies_file = default_cookie
            print(f"[*] Auto-using cookies file: {default_cookie}")

    skill = XPostSkill(
        args.url,
        args.key,
        cookies_browser=args.cookies_browser,
        cookies_file=args.cookies_file,
        local_file=args.local_file,
        whisper_model=args.model_size,
    )
    skill.run()

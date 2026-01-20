import os
import sys
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

class XPostSkill:
    def __init__(self, url, nvidia_key, target_lang='zh', model_name="minimaxai/minimax-m2"):
        self.url = url
        self.nvidia_key = nvidia_key
        self.target_lang = target_lang
        self.model_name = model_name
        self.task_dir = None
        self.client = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=self.nvidia_key
        )
        # Font setup
        self.font_path = "arial.ttf"
        possible_fonts = [
            r"C:\Windows\Fonts\msyh.ttc", # Microsoft YaHei
            r"C:\Windows\Fonts\simhei.ttf", # SimHei
            r"C:\Windows\Fonts\msyhl.ttc",
        ]
        for f in possible_fonts:
            if os.path.exists(f):
                self.font_path = f
                break
        print(f"[*] Using font: {self.font_path}")

    def run(self):
        print(f"[*] Starting processing for {self.url}")
        
        # 1. Download
        data = self._download()
        if not data:
            print("[-] Download failed.")
            return

        # Setup Folder
        date_str = datetime.datetime.now().strftime("%Y%m%d")
        # Sanitize summary for folder name
        safe_content = re.sub(r'[\\/*?:"<>|\n\r]', "", data['content']).strip()
        safe_summary = (safe_content[:20] + '_more') if len(safe_content) > 20 else safe_content
        safe_summary = safe_summary.replace(" ", "_")
        
        self.task_dir = os.path.join("tasks", f"{date_str}_{safe_summary}")
        os.makedirs(self.task_dir, exist_ok=True)
        print(f"[*] Task directory: {self.task_dir}")

        # Save Raw Metadata
        with open(os.path.join(self.task_dir, "raw.json"), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        # 2. Translate Text
        translated_text = self._translate(data['content'])
        print(f"[*] Translated Text: {translated_text}")

        # 3. Process Media
        media_files = []
        if data.get('video_path'):
            processed_video = self._process_video(data['video_path'], translated_text)
            media_files.append(processed_video)
        
        # 4. Create Markdown
        self._create_markdown(data, translated_text, media_files)
        print("[*] Done!")

    def _download(self):
        print("[*] Checking content...")
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': 'temp_%(id)s.%(ext)s',
            'quiet': True,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # 1. Fetch Metadata first
                info = ydl.extract_info(self.url, download=False)
                
                # Check for existing
                content = info.get('description') or info.get('title') or ""
                safe_content = re.sub(r'[\\/*?:"<>|\n\r]', "", content).strip()
                safe_summary = (safe_content[:20] + '_more') if len(safe_content) > 20 else safe_content
                safe_summary = safe_summary.replace(" ", "_")
                date_str = datetime.datetime.now().strftime("%Y%m%d")
                
                # Predict Task Dir (Note: date might differ if crossed midnight, but good enough for immediate re-run)
                # To be safer, we could search for any folder matching the summary part?
                # For now, strict match or just check temp file in CWD
                
                predicted_filename = ydl.prepare_filename(info)
                final_video_name = os.path.basename(predicted_filename)
                
                # Check if we have it in CWD (temp)
                if os.path.exists(predicted_filename):
                    print(f"[*] Found existing temp file: {predicted_filename}")
                    return {
                        "id": info.get('id'),
                        "content": content,
                        "video_path": predicted_filename,
                        "uploader": info.get('uploader'),
                        "upload_date": info.get('upload_date')
                    }
                    
                # Check if we have it in a task folder?
                # Complex because date changes. 
                # Let's rely on CWD check for "just now" re-runs or download it.
                # User asked "check if video have downloaded"
                
                print("[*] Downloading media...")
                error_code = ydl.download([self.url])
                
                if os.path.exists(predicted_filename):
                    return {
                        "id": info.get('id'),
                        "content": content,
                        "video_path": predicted_filename,
                        "uploader": info.get('uploader'),
                        "upload_date": info.get('upload_date')
                    }
                return None
        except Exception as e:
            print(f"[-] Download error: {e}")
            return None

    def _translate(self, text):
        print("[*] Translating text...")
        if not text:
            return ""
        try:
            prompt = f"Translate the following text to {self.target_lang}. Only return the translated text.\n\nText: {text}"
            completion = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            content = completion.choices[0].message.content.strip()
            if "</think>" in content:
                content = content.split("</think>")[-1].strip()
            return content
        except Exception as e:
            print(f"[-] Translation error: {e}")
            return text

    def _transcribe(self, audio_path):
        print("[*] Transcribing audio...")
        try:
            model = whisper.load_model("base")
            result = model.transcribe(audio_path)
            return result
        except Exception as e:
            print(f"[-] Transcription error: {e}")
            return None

    def _clean_text(self, text):
        # Remove URLs
        text = re.sub(r'https?://\S+', '', text)
        # Remove Emojis
        text = emoji.replace_emoji(text, replace='')
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _create_subtitle_clip(self, text, start_time, duration, video_size):
        # Create PIL image
        w, h = video_size
        img = Image.new('RGBA', (w, h), (0,0,0,0))
        draw = ImageDraw.Draw(img)
        
        # Load font
        fontsize = int(h / 20) # dynamic size
        try:
            font = ImageFont.truetype(self.font_path, fontsize)
        except:
            font = ImageFont.load_default()

        # Wrap text? Simplistic wrapping for now or just single line
        # Use textbbox to center
        # Only simple wrapping: if text is too long, break?
        # Let's assume whisper segments are short enough or just draw
        
        # Draw text at bottom center
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        
        x = (w - text_w) / 2
        y = h - text_h - 50 # 50px padding from bottom
        
        # Draw outline for better visibility?
        outline_color = 'black'
        text_color = 'yellow' # Requirement
        
        # Simple outline via offsets
        for adj in [(1,1), (-1,-1), (1,-1), (-1,1)]:
            draw.text((x+adj[0], y+adj[1]), text, font=font, fill=outline_color)
            
        draw.text((x, y), text, font=font, fill=text_color)
        
        # Convert to MoviePy ImageClip
        txt_clip = ImageClip(np.array(img)).set_start(start_time).set_duration(duration)
        return txt_clip

    def _process_video(self, video_path, summary_text):
        print(f"[*] Processing video: {video_path}")
        
        final_video_name = os.path.basename(video_path)
        
        # Transcribe with timestamps
        transcript_result = self._transcribe(video_path)
        
        try:
            clip = VideoFileClip(video_path)
            subtitles = []
            
            # If transcript is valid and has segments, use them
            if transcript_result and 'segments' in transcript_result and transcript_result['segments']:
                print("[*] Using transcript for subtitles...")
                for seg in transcript_result['segments']:
                    start = seg['start']
                    end = seg['end']
                    txt = self._clean_text(seg['text'])
                    if not txt: continue
                    sub = self._create_subtitle_clip(txt, start, end-start, clip.size)
                    subtitles.append(sub)
            else:
                # Fallback: Overlay translated summary if no audio/transcript
                print("[*] No transcript found (silent video?). Overlaying summary text...")
                clean_summary = self._clean_text(summary_text)
                
                # Split usage simple chunking or just display
                display_text = clean_summary[:50] + "..." if len(clean_summary) > 50 else clean_summary
                sub = self._create_subtitle_clip(display_text, 0, clip.duration, clip.size)
                subtitles.append(sub)
                
            final_clip = CompositeVideoClip([clip] + subtitles)
            output_path = os.path.join(self.task_dir, f"processed_{final_video_name}")
            
            # Check if audio exists
            fps = getattr(clip, 'fps', 24)
            if clip.audio:
                final_clip.write_videofile(output_path, codec='libx264', audio_codec='aac', fps=fps)
            else:
                final_clip.write_videofile(output_path, codec='libx264', audio=False, fps=fps)
            
            # Move raw
            os.rename(video_path, os.path.join(self.task_dir, f"raw_{final_video_name}"))
            
            return output_path
            
        except Exception as e:
            print(f"[-] Video processing error: {e}")
            target_path = os.path.join(self.task_dir, final_video_name)
            if os.path.exists(video_path):
                 os.rename(video_path, target_path)
            return target_path

    def _create_markdown(self, data, translated_text, media_files):
        print("[*] Creating Markdown...")
        md_content = f"""# {data['content'][:50]}...

**Date**: {data['upload_date']}
**Uploader**: {data['uploader']}
**Original URL**: {self.url}

## Content
### Original
{data['content']}

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
    parser.add_argument("--url", required=True, help="Twitter/X URL")
    parser.add_argument("--key", required=True, help="Nvidia API Key")
    args = parser.parse_args()
    
    skill = XPostSkill(args.url, args.key)
    skill.run()

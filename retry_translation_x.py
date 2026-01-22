import os
import json
import subprocess
from openai import OpenAI

# Configuration
TASK_DIR = r"d:\MyCode\meiti\tasks\20260121_204633_temp_2011551143554662402"
JSON_PATH = os.path.join(TASK_DIR, "translation_check.json")
ASS_PATH = os.path.join(TASK_DIR, "captions.ass")
RAW_VIDEO = os.path.join(TASK_DIR, "raw_temp_2011551143554662402.mp4")
OUTPUT_VIDEO = os.path.join(TASK_DIR, "processed_final_translated_yellow.mp4")
NVIDIA_KEY = "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"
MODEL = "meta/llama-3.1-405b-instruct"

def format_time_ass(seconds):
    """Format seconds to ASS time format: h:mm:ss.cc"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    centis = int((secs - int(secs)) * 100)
    return f"{hours}:{minutes:02}:{int(secs):02}.{centis:02}"

def generate_ass(segments, output_path):
    print(f"[*] Generating ASS: {output_path}")
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 1

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Microsoft YaHei,60,&H0000FFFF,&H000000FF,&H00000000,&H60000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,50,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(header)
            for seg in segments:
                start = format_time_ass(seg["start"])
                end = format_time_ass(seg["end"])
                # Use translated text
                text = seg["translated"].replace("\n", " ").strip()
                line = f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}\n"
                f.write(line)
        return True
    except Exception as e:
        print(f"[-] ASS generation error: {e}")
        return False

def translate_segments(segments):
    client = OpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=NVIDIA_KEY,
        timeout=60.0
    )
    
    # Filter segments that need translation
    to_translate = []
    indices = []
    
    for i, seg in enumerate(segments):
        # Heuristic: if translated == original, it needs translation
        if seg["translated"] == seg["original"]:
            to_translate.append(seg["original"])
            indices.append(i)
            
    if not to_translate:
        print("[*] No segments need translation.")
        return segments

    print(f"[*] Translating {len(to_translate)} segments...")
    
    # Batch processing
    batch_size = 20
    delimiter = " ||| "
    
    for i in range(0, len(to_translate), batch_size):
        batch = to_translate[i:i+batch_size]
        batch_indices = indices[i:i+batch_size]
        
        print(f"  - Batch {i//batch_size + 1}: {len(batch)} items")
        combined_text = delimiter.join(batch)
        
        prompt = (
            f"Translate the following text segments to Simplified Chinese for subtitles. "
            f"Keep the segments separated by '{delimiter}'. "
            "Translate the full meaning of each segment directly. "
            "Do NOT summarize. Do NOT shorten. Do NOT omit details. "
            "Return only the translated string joined by the delimiter.\n\n"
            f"Text: {combined_text}"
        )
        
        try:
            completion = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=2048
            )
            content = completion.choices[0].message.content.strip()
            translated_batch = content.split(delimiter.strip())
            
            # Map back
            for j, idx in enumerate(batch_indices):
                if j < len(translated_batch):
                    segments[idx]["translated"] = translated_batch[j].strip()
                else:
                    print(f"[-] Warning: Batch mismatch at index {j}, original was: {batch[j]}")
                    
        except Exception as e:
            print(f"[-] Batch translation failed: {e}")
            
    return segments

def main():
    if not os.path.exists(JSON_PATH):
        print(f"[-] JSON not found: {JSON_PATH}")
        return

    print(f"[*] Reading: {JSON_PATH}")
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        segments = json.load(f)

    # Translate
    segments = translate_segments(segments)
    
    # Save JSON
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(segments, f, indent=2, ensure_ascii=False)
    print(f"[*] Updated JSON saved.")

    # Generate ASS
    if generate_ass(segments, ASS_PATH):
        print(f"[*] ASS saved: {ASS_PATH}")
        
        # Render
        # Note: Need fully qualified ffmpeg path and escape ASS path carefully
        ffmpeg_exe = r"D:\MyCode\meiti\venv\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg.exe"
        # ASS path logic for FFMPEG filter
        # Windows paths in ffmpeg filters need escaping: \ -> / and : -> \:
        ass_path_filter = ASS_PATH.replace("\\", "/").replace(":", "\\:")
        
        cmd = [
            ffmpeg_exe, "-y",
            "-i", RAW_VIDEO,
            "-vf", f"subtitles='{ass_path_filter}'",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-c:a", "copy",
            OUTPUT_VIDEO
        ]
        
        print(f"[*] Running FFMPEG...")
        try:
            subprocess.run(cmd, check=True)
            print(f"[*] Done! Video: {OUTPUT_VIDEO}")
        except subprocess.CalledProcessError as e:
            print(f"[-] FFMPEG Error: {e}")

if __name__ == "__main__":
    main()

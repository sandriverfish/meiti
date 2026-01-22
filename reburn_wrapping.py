import os
import json
import subprocess
import textwrap

# Configuration
TASK_DIR = r"d:\MyCode\meiti\tasks\20260122_055914_temp_2013997562957594624"
JSON_PATH = os.path.join(TASK_DIR, "translation_check.json")
ASS_PATH = os.path.join(TASK_DIR, "captions_wrapped.ass")
RAW_VIDEO = os.path.join(TASK_DIR, "raw_temp_2013997562957594624.mp4")
OUTPUT_VIDEO = os.path.join(TASK_DIR, "processed_temp_2013997562957594624_v2.mp4")

# Parameters
MARGIN_V = 100  # Small value to position at bottom of portrait video
MAX_CHARS_PER_LINE = 12  # Tighter wrapping to prevent overflow
FONT_SIZE = 48  # Smaller font for portrait videos

def format_time_ass(seconds):
    """Format seconds to ASS time format: h:mm:ss.cc"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    centis = int((secs - int(secs)) * 100)
    return f"{hours}:{minutes:02}:{int(secs):02}.{centis:02}"

def wrap_text(text, width):
    """Wrap text manually for ASS (using \\N), keeping English words together"""
    import re
    
    # Tokenize into English words and Chinese characters
    # Pattern: sequences of ASCII letters/numbers (English words) or individual characters
    tokens = re.findall(r'[a-zA-Z0-9]+|[^\sa-zA-Z0-9]', text)
    
    lines = []
    current_line = ""
    current_count = 0
    
    for token in tokens:
        # Estimate width: ASCII=0.5, CJK/other=1
        if re.match(r'^[a-zA-Z0-9]+$', token):
            token_width = len(token) * 0.5
        else:
            token_width = sum(0.5 if ord(c) < 128 else 1 for c in token)
        
        # Check if adding this token would exceed width
        if current_count + token_width > width and current_line:
            # Start new line
            lines.append(current_line.strip())
            current_line = token
            current_count = token_width
        else:
            current_line += token
            current_count += token_width
    
    if current_line:
        lines.append(current_line.strip())
    
    return "\\N".join(lines)

def generate_ass(segments, output_path):
    print(f"[*] Generating ASS: {output_path}")
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 1

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Microsoft YaHei,{FONT_SIZE},&H0000FFFF,&H000000FF,&H00000000,&H60000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,{MARGIN_V},1
Style: SpeakerA,Microsoft YaHei,{FONT_SIZE},&H0000FFFF,&H000000FF,&H00000000,&H60000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,{MARGIN_V},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(header)
            for seg in segments:
                start = format_time_ass(seg["start"])
                end = format_time_ass(seg["end"])
                original_text = seg["translated"].strip()
                
                # Wrap text
                text = wrap_text(original_text, MAX_CHARS_PER_LINE)
                
                # Speaker style (simplify to A/Default)
                style = "SpeakerA"
                
                line = f"Dialogue: 0,{start},{end},{style},,0,0,0,,{text}\n"
                f.write(line)
        return True
    except Exception as e:
        print(f"[-] ASS generation error: {e}")
        return False

def main():
    if not os.path.exists(JSON_PATH):
        print(f"[-] JSON not found: {JSON_PATH}")
        return

    print(f"[*] Reading: {JSON_PATH}")
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        segments = json.load(f)

    # Generate ASS
    if generate_ass(segments, ASS_PATH):
        print(f"[*] ASS saved: {ASS_PATH}")
        
        # Render
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        
        # Windows paths escaping
        ass_path_filter = os.path.abspath(ASS_PATH).replace("\\", "/").replace(":", "\\:")
        
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

import os
import json
import subprocess
import datetime
import shutil

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
Style: Default,Microsoft YaHei,60,&H00FFFFFF,&H000000FF,&H00000000,&H60000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,50,1
Style: SpeakerA,Microsoft YaHei,60,&H0000FFFF,&H000000FF,&H00000000,&H60000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,50,1
Style: SpeakerB,Microsoft YaHei,60,&H00FFFF00,&H000000FF,&H00000000,&H60000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,50,1
Style: SpeakerC,Microsoft YaHei,60,&H0000FF00,&H000000FF,&H00000000,&H60000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,50,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    # Colors (A=Yellow, B=Cyan, C=Green)
    # ASS Order: &H(Alpha)(Blue)(Green)(Red)
    # Yellow: R=FF, G=FF, B=00 -> 00FFFF
    # Cyan:   R=00, G=FF, B=FF -> FFFF00
    
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(header)
            for seg in segments:
                start = format_time_ass(seg["start"])
                end = format_time_ass(seg["end"])
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
                
                # Sanitize text for ASS (remove newlines if any, or convert to \N)
                text = text.replace("\n", " ").strip()
                
                line = f"Dialogue: 0,{start},{end},{style},,0,0,0,,{text}\n"
                f.write(line)
        return output_path
    except Exception as e:
        print(f"[-] ASS generation error: {e}")
        return None

def main():
    task_dir = r"e:\MyCode\meiti\tasks\20260121_054038_Hassabis_on_an_AI_Shift_Bigger_etc"
    json_path = os.path.join(task_dir, "translation_check.json")
    ass_path = os.path.join(task_dir, "captions_colored.ass")
    
    # Input Video (Raw)
    input_video = os.path.join(task_dir, "raw_Hassabis on an AI Shift Bigger Than Industrial Age.mp4")
    # Output Video
    output_video = os.path.join(task_dir, "processed_v3_ffmpeg_Hassabis.mp4")
    
    if not os.path.exists(json_path):
        print(f"[-] JSON not found: {json_path}")
        return

    print(f"[*] Reading translation data: {json_path}")
    with open(json_path, "r", encoding="utf-8") as f:
        segments = json.load(f)
        
    print(f"[*] Found {len(segments)} segments.")
    
    # 1. Generate ASS
    generate_ass(segments, ass_path)
    
    # 2. Render with ffmpeg
    if not os.path.exists(input_video):
        print(f"[-] Input video not found: {input_video}")
        return

    print(f"[*] Rendering video using FFMPEG...")
    print(f"Input: {input_video}")
    print(f"Subs:  {ass_path}")
    print(f"Output: {output_video}")
    
    cwd = task_dir
    rel_input = os.path.basename(input_video)
    rel_ass = os.path.basename(ass_path)
    rel_output = os.path.basename(output_video)
    
    cmd = [
        "ffmpeg",
        "-y",
        "-i", rel_input,
        "-vf", f"subtitles='{rel_ass}'",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-c:a", "copy",
        rel_output
    ]
    
    print(f"Command: {' '.join(cmd)}")
    
    try:
        subprocess.run(cmd, cwd=cwd, check=True)
        print(f"[*] Done! New video: {output_video}")
    except subprocess.CalledProcessError as e:
        print(f"[-] FFMPEG error: {e}")

if __name__ == "__main__":
    main()

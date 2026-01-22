import os
import json
import sys
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip, ImageClip
from PIL import Image, ImageDraw, ImageFont
import numpy as np
from x_post_conv import XPostSkill

def reprocess(task_dir, video_filename):
    print(f"[*] Reprocessing task: {task_dir}")
    
    json_path = os.path.join(task_dir, "translation_check.json")
    if not os.path.exists(json_path):
        print(f"[-] JSON not found: {json_path}")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # key from hardcode or file (using the known key)
    key = "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"
    skill = XPostSkill(url="", nvidia_key=key) # minimal init
    
    # Extract originals
    originals = [item["original"] for item in data]
    print(f"[*] Found {len(originals)} segments to re-translate.")
    
    # Re-translate
    new_translations = skill._translate_batch(originals)
    
    # Update data
    for i, item in enumerate(data):
        if i < len(new_translations):
            trans_item = new_translations[i]
            if isinstance(trans_item, dict):
                 item["translated"] = trans_item.get("translated", item["original"])
                 item["speaker"] = trans_item.get("speaker", "A") # Update speaker too if changed
            else:
                 item["translated"] = str(trans_item)
    
    # Save updated JSON
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print("[*] Updated translation_check.json")

    # Re-generate SRT
    srt_path = os.path.join(task_dir, "captions_reprocessed.srt")
    skill._generate_srt(data, srt_path)
    print(f"[*] Generated SRT: {srt_path}")

    # Re-render Video
    video_path = os.path.join(task_dir, f"raw_{video_filename}")
    if not os.path.exists(video_path):
        # check if processed exists and use that as base? No, need raw.
        # check if input argument file exists
        search_path = os.path.join(task_dir, video_filename) # maybe it wasn't renamed to raw_ yet?
        if os.path.exists(search_path):
             video_path = search_path
        else:
             print(f"[-] Raw video not found at {video_path}")
             return

    print(f"[*] Rendering video using: {video_path}")
    clip = VideoFileClip(video_path)
    subtitles = []
    
    for seg in data:
        text = seg["translated"]
        speaker = seg.get("speaker", "A")
        
        # Determine Color
        color = "yellow"
        if speaker == "B":
            color = "#00FFFF" # Cyan
        elif speaker == "C":
            color = "#00FF00" # Green

        # Use skill's method if possible, but need to bind it? 
        # skill._create_subtitle_clip uses self.font_path
        sub = skill._create_subtitle_clip(
            text, seg["start"], seg["end"] - seg["start"], clip.size, color=color
        )
        subtitles.append(sub)

    final_clip = CompositeVideoClip([clip] + subtitles)
    final_clip.duration = clip.duration
    
    output_path = os.path.join(task_dir, f"processed_v2_{video_filename}")
    
    if clip.audio:
        final_clip.write_videofile(
            output_path, codec="libx264", audio_codec="aac", fps=clip.fps or 24
        )
    else:
        final_clip.write_videofile(
             output_path, codec="libx264", audio=False, fps=clip.fps or 24
        )
    
    print(f"[*] Done! New video: {output_path}")

if __name__ == "__main__":
    task_dir = r"tasks/20260121_054038_Hassabis_on_an_AI_Shift_Bigger_etc"
    video_filename = "Hassabis on an AI Shift Bigger Than Industrial Age.mp4"
    reprocess(task_dir, video_filename)

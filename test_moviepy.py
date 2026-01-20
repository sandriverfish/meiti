from moviepy.editor import ColorClip, TextClip, CompositeVideoClip

try:
    # Create a simple red background
    clip = ColorClip(size=(640, 480), color=(255, 0, 0), duration=2)
    
    # Create a text clip
    # Try generic font first, then YaHei
    txt_clip = TextClip("Test Subtitle", fontsize=70, color='yellow')
    txt_clip = txt_clip.set_position('center').set_duration(2)
    
    video = CompositeVideoClip([clip, txt_clip])
    video.write_videofile("test_moviepy.mp4", fps=24)
    print("SUCCESS: Video generated.")
except Exception as e:
    print(f"FAILURE: {e}")

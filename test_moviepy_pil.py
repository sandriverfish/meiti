from moviepy.editor import ColorClip, ImageClip, CompositeVideoClip
from PIL import Image, ImageDraw, ImageFont
import numpy as np

def create_text_clip_pil(text, fontsize=50, color='yellow', bg_color=(0,0,0,0), size=(640, 480)):
    # Create valid image with PIL
    img = Image.new('RGBA', size, bg_color)
    draw = ImageDraw.Draw(img)
    
    # Load default font or try to find arial
    try:
        font = ImageFont.truetype("arial.ttf", fontsize)
    except:
        font = ImageFont.load_default()
        
    # Draw centered text (approximate)
    # textbbox is cleaner but verify PIL version
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    x = (size[0] - text_width) / 2
    y = (size[1] - text_height) / 2
    
    draw.text((x, y), text, font=font, fill=color)
    
    # Convert to numpy for MoviePy
    return ImageClip(np.array(img)).set_duration(2)

try:
    # 1. Background
    bg = ColorClip(size=(640, 480), color=(0, 0, 255), duration=2) # Blue bg
    
    # 2. Text via PIL
    txt_clip = create_text_clip_pil("Pillow Text Test", fontsize=60)
    
    # 3. Composite
    video = CompositeVideoClip([bg, txt_clip])
    video.write_videofile("test_moviepy_pil.mp4", fps=24)
    print("SUCCESS: Video generated with PIL.")
except Exception as e:
    print(f"FAILURE: {e}")

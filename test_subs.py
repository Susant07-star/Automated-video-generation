import json
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import ImageClip
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
from video_assembler import create_karaoke_subtitle_image, create_dynamic_subtitles

clips = create_dynamic_subtitles("temp_voice.mp3.json", 1080, 1920, target_duration=60)
print(f"Generated {len(clips)} subtitle clips")

if len(clips) > 0:
    first_clip = clips[0]
    frame = first_clip.get_frame(first_clip.start + 0.1)
    print(f"Frame shape: {frame.shape}")
    if first_clip.mask is not None:
        mask_frame = first_clip.mask.get_frame(first_clip.start + 0.1)
        print(f"Mask max val: {np.max(mask_frame)}")
    else:
        print("No mask!")

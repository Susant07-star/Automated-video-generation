import os
import json
import textwrap
import subprocess
from PIL import Image, ImageDraw, ImageFont
import numpy as np
from moviepy.editor import (
    VideoFileClip, AudioFileClip, CompositeAudioClip, CompositeVideoClip,
    ImageClip, ColorClip, VideoClip, vfx
)
import moviepy.audio.fx.all as afx

# Resolve ffmpeg binary (works even if not in system PATH)
try:
    import imageio_ffmpeg
    FFMPEG_BIN = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    FFMPEG_BIN = "ffmpeg"  # fallback: hope it's in PATH

# Monkey-patch Image.ANTIALIAS for moviepy 1.0.3 compatibility with Pillow 10+
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.LANCZOS

MIN_DURATION = 15
CHANNEL_HANDLE = os.getenv("CHANNEL_HANDLE", "@nextgenthoughts")
TARGET_W, TARGET_H = 1080, 1920  # Standard Reels/Shorts resolution
CPU_THREADS = max(2, (os.cpu_count() or 4))  # Auto-detect all cores


def preprocess_video_ffmpeg(input_path: str, output_path: str):
    """
    Uses ffmpeg directly (C-speed) to:
      1. Resize to 1080x1920 (portrait 9:16)
      2. Center-crop if the aspect ratio doesn't match exactly
    This runs in seconds vs. minutes inside MoviePy/Python.
    """
    print(f"   [ffmpeg] Pre-processing video to {TARGET_W}x{TARGET_H}...")
    cmd = [
        FFMPEG_BIN, "-y",
        "-i", input_path,
        "-vf", (
            f"scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=increase,"
            f"crop={TARGET_W}:{TARGET_H}"
        ),
        "-an",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "23",
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"   [ffmpeg] pre-process warning: {result.stderr[-200:]}")
        print("   Falling back to MoviePy resize...")
        return False
    print(f"   [ffmpeg] Pre-processing complete → {output_path}")
    return True

def get_font(size=70):
    """
    Tries multiple common bold font paths so the video renders correctly
    on Windows (Arial), Linux/GitHub Actions (Liberation/DejaVu), and macOS.
    """
    font_candidates = [
        # Windows
        "arialbd.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf",
        # Linux / GitHub Actions (install fonts-liberation in workflow)
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        # macOS
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial Bold.ttf",
    ]
    for path in font_candidates:
        try:
            return ImageFont.truetype(path, size)
        except (IOError, OSError):
            continue
    # Absolute last resort - load_default supports size in Pillow 10+
    try:
        return ImageFont.load_default(size=max(size, 30))
    except TypeError:
        return ImageFont.load_default()

def create_text_image(text, W, H, fontsize=85):
    """
    Creates a transparent image with centered white text and black stroke.
    Auto-shrinks font size and word-wraps to guarantee text stays within
    a safe zone (80px padding from each side). Text is never cut off.
    """
    SAFE_PADDING = 80  # pixels from left/right edge
    max_text_w = W - (SAFE_PADDING * 2)

    # Auto-reduce font size until ALL lines fit within safe zone.
    # Font shrinks by 5px per iteration, down to a minimum of 20px.
    # Words are NEVER split — wrapping only happens at spaces.
    while fontsize >= 20:
        font = get_font(fontsize)
        wrapped_lines = _wrap_text(text, font, max_text_w)
        all_fit = all(
            (ImageDraw.Draw(Image.new('RGBA', (W, H))).textbbox((0, 0), line, font=font)[2]
             - ImageDraw.Draw(Image.new('RGBA', (W, H))).textbbox((0, 0), line, font=font)[0])
            <= max_text_w
            for line in wrapped_lines
        )
        if all_fit:
            break
        fontsize -= 5
    # At fontsize=20, accept whatever wrapping we have (words intact, may be slightly wide)

    font = get_font(fontsize)
    wrapped_lines = _wrap_text(text, font, max_text_w)

    img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Calculate total block height for vertical centering
    line_heights = []
    for line in wrapped_lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_heights.append(bbox[3] - bbox[1])
    line_spacing = int(fontsize * 0.25)
    total_h = sum(line_heights) + line_spacing * (len(wrapped_lines) - 1)

    # Center the text block at 55% of the screen height
    y_start = int(H * 0.55) - total_h // 2

    stroke_color = (0, 0, 0)
    stroke_width = 4

    current_y = y_start
    for i, line in enumerate(wrapped_lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        text_w = bbox[2] - bbox[0]
        x = (W - text_w) / 2

        # Draw stroke
        for dx in range(-stroke_width, stroke_width + 1):
            for dy in range(-stroke_width, stroke_width + 1):
                draw.text((x + dx, current_y + dy), line, font=font, fill=stroke_color)

        # Draw main text
        draw.text((x, current_y), line, font=font, fill="white")
        current_y += line_heights[i] + line_spacing

    return np.array(img)


def _wrap_text(text, font, max_width):
    """
    Breaks text into lines that each fit within max_width pixels.
    IMPORTANT: Words are NEVER split in the middle. If a single word
    is too wide, it is placed on its own line and the outer font-size
    loop will shrink the font until it fits. No hyphens, no cuts.
    """
    words = text.split()
    if not words:
        return [text]

    lines = []
    current_line = []
    tmp_img = Image.new('RGBA', (1, 1))
    tmp_draw = ImageDraw.Draw(tmp_img)

    for word in words:
        test_line = " ".join(current_line + [word])
        bbox = tmp_draw.textbbox((0, 0), test_line, font=font)
        line_width = bbox[2] - bbox[0]

        if line_width <= max_width:
            # Word fits on the current line — add it
            current_line.append(word)
        else:
            # Word doesn't fit — flush current line and start a new one
            if current_line:
                lines.append(" ".join(current_line))
            # The word itself goes on its own new line (never split)
            current_line = [word]

    if current_line:
        lines.append(" ".join(current_line))

    return lines if lines else [text]



def apply_ken_burns(clip, zoom_ratio=1.1):
    """Applies a smooth zoom-in effect over the clip duration."""
    def zoom(t):
        progress = t / clip.duration
        current_zoom = 1.0 + (zoom_ratio - 1.0) * progress
        return current_zoom

    # moviepy resize accepts a function of time
    zoomed_clip = clip.resize(zoom)
    # Center crop back to original size
    zoomed_clip = zoomed_clip.crop(x_center=clip.w/2, y_center=clip.h/2, width=clip.w, height=clip.h)
    return zoomed_clip

def make_vignette(W, H):
    """Creates a dark radial gradient for cinematic vignette."""
    X, Y = np.meshgrid(np.linspace(-1, 1, W), np.linspace(-1, 1, H))
    radius = np.sqrt(X**2 + Y**2)
    # Vignette strength and size
    vignette = np.clip(1.5 - radius, 0, 1)
    
    # Convert to RGBA
    img = np.zeros((H, W, 4), dtype=np.uint8)
    img[:, :, 3] = (255 * (1 - vignette)).astype(np.uint8) # Alpha channel
    # Color is black
    return img

def create_karaoke_subtitle_image(words_in_chunk, active_idx, W, H, fontsize=90):
    """
    Creates a single RGBA image showing a chunk of words side by side.
    - Words spoken BEFORE active_idx: light grey
    - Word AT active_idx: bright yellow (highlighted)
    - Words AFTER active_idx: white (upcoming)
    This is the Hormozi/viral karaoke style.
    """
    font = get_font(fontsize)
    SAFE_PADDING = 80
    max_text_w = W - (SAFE_PADDING * 2)

    # Auto-shrink font until all words fit in one line
    while fontsize >= 30:
        font = get_font(fontsize)
        full_line = " ".join(words_in_chunk)
        tmp_img = Image.new('RGBA', (1, 1))
        tmp_draw = ImageDraw.Draw(tmp_img)
        bbox = tmp_draw.textbbox((0, 0), full_line, font=font)
        if (bbox[2] - bbox[0]) <= max_text_w:
            break
        fontsize -= 5

    font = get_font(fontsize)
    img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Measure each word's width to compute total line width
    tmp_img2 = Image.new('RGBA', (1, 1))
    tmp_draw2 = ImageDraw.Draw(tmp_img2)
    space_bbox = tmp_draw2.textbbox((0, 0), " ", font=font)
    space_w = space_bbox[2] - space_bbox[0]

    word_widths = []
    word_heights = []
    for w in words_in_chunk:
        bbox = tmp_draw2.textbbox((0, 0), w, font=font)
        word_widths.append(bbox[2] - bbox[0])
        word_heights.append(bbox[3] - bbox[1])

    total_w = sum(word_widths) + space_w * (len(words_in_chunk) - 1)
    line_h = max(word_heights) if word_heights else fontsize

    # Center the whole line horizontally, position at 58% of screen height
    x_start = (W - total_w) / 2
    y = int(H * 0.58) - line_h // 2

    stroke_width = 5
    stroke_color = (0, 0, 0)

    x_cursor = x_start
    for i, word in enumerate(words_in_chunk):
        if i < active_idx:
            fill_color = (180, 180, 180)   # light grey — already spoken
        elif i == active_idx:
            fill_color = (255, 230, 0)     # bright yellow — currently speaking
        else:
            fill_color = (255, 255, 255)   # white — upcoming

        # Draw thick black stroke for legibility
        for dx in range(-stroke_width, stroke_width + 1):
            for dy in range(-stroke_width, stroke_width + 1):
                draw.text((x_cursor + dx, y + dy), word, font=font, fill=stroke_color)
        # Draw the word
        draw.text((x_cursor, y), word, font=font, fill=fill_color)
        x_cursor += word_widths[i] + space_w

    return np.array(img)


def create_dynamic_subtitles(timestamps_file, W, H, target_duration, voice_offset=0.5):
    """
    Karaoke-style subtitles using ElevenLabs word timestamps.
    - Words are grouped into chunks of 4.
    - Within each chunk, the currently-speaking word is highlighted yellow.
    - Previous words turn grey. Next words are white.
    - Each highlighted word gets its own ImageClip at its exact timestamp.
    """
    if not os.path.exists(timestamps_file):
        return []

    with open(timestamps_file, 'r') as f:
        words = json.load(f)

    if not words:
        return []

    CHUNK_SIZE = 4
    GAP = 0.05  # 50ms gap between chunks

    # Build chunks of 4 words
    chunks = []
    for i in range(0, len(words), CHUNK_SIZE):
        chunk_words = words[i:i + CHUNK_SIZE]
        chunks.append(chunk_words)

    clips = []

    for chunk_idx, chunk_words in enumerate(chunks):
        word_texts = [w['word'] for w in chunk_words]

        # Cap the last word of this chunk at the start of the next chunk
        if chunk_idx < len(chunks) - 1:
            next_chunk_start = chunks[chunk_idx + 1][0]['start']
            # Fix the end time of the last word in this chunk
            chunk_words[-1]['end'] = min(chunk_words[-1]['end'], next_chunk_start - GAP)

        # For each word in the chunk, render the full chunk with that word highlighted
        for active_idx, word_data in enumerate(chunk_words):
            start_t = word_data['start'] + voice_offset
            # End time = next word's start OR end of word + small buffer
            if active_idx < len(chunk_words) - 1:
                end_t = chunk_words[active_idx + 1]['start'] + voice_offset - GAP
            else:
                # Last word in chunk — show until next chunk begins (or video ends)
                if chunk_idx < len(chunks) - 1:
                    end_t = chunks[chunk_idx + 1][0]['start'] + voice_offset - GAP
                else:
                    end_t = word_data['end'] + voice_offset + 0.3

            if start_t >= target_duration:
                break
            end_t = min(end_t, target_duration)

            if end_t - start_t < 0.04:
                continue

            text_img = create_karaoke_subtitle_image(word_texts, active_idx, W, H, fontsize=90)
            clip = (ImageClip(text_img)
                    .set_start(start_t)
                    .set_end(end_t)
                    .set_position(('center', 'center')))
            clips.append(clip)

    return clips


from moviepy.editor import concatenate_videoclips

def assemble_video(bg_video_paths, audio_path, text, output_path="final_reel.mp4", bg_music_path=None, whoosh_path=None):
    print("Assembling cinematic multi-clip video...")
    
    try:
        voice_audio = AudioFileClip(audio_path)
        
        music_audio = None
        if bg_music_path and os.path.exists(bg_music_path):
            music_audio = AudioFileClip(bg_music_path)
        else:
            print("Warning: No background music loaded.")
            
        whoosh_audio = None
        if whoosh_path and os.path.exists(whoosh_path):
            whoosh_audio = AudioFileClip(whoosh_path).fx(afx.volumex, 0.4)
    except Exception as e:
        print(f"Error loading media files: {e}")
        return

    # Calculate target duration (must be at least MIN_DURATION)
    audio_duration = voice_audio.duration
    target_duration = max(MIN_DURATION, audio_duration + 1.0) # 1 second padding

    # Process all video clips
    import random
    processed_clips = []
    num_clips = len(bg_video_paths)
    
    # Calculate randomized segment durations proportionally
    # This guarantees the target_duration is distributed smoothly among ANY number of clips
    raw_weights = [random.uniform(0.7, 1.3) for _ in range(num_clips)]
    total_weight = sum(raw_weights)
    segment_durations = [(w / total_weight) * target_duration for w in raw_weights]
    
    for i, vp in enumerate(bg_video_paths):
        seg_dur = segment_durations[i]
        try:
            preprocessed_path = vp + ".processed.mp4"
            ffmpeg_ok = preprocess_video_ffmpeg(vp, preprocessed_path)
            
            if ffmpeg_ok and os.path.exists(preprocessed_path):
                clip = VideoFileClip(preprocessed_path)
            else:
                clip = VideoFileClip(vp)
                if clip.w > TARGET_W:
                    clip = clip.resize(width=TARGET_W)
            
            # Apply 1.5x speed multiplier for faster, more dynamic visual pacing
            clip = clip.fx(vfx.speedx, 1.5)
                    
            if clip.duration < seg_dur:
                clip = clip.fx(vfx.loop, duration=seg_dur)
            else:
                clip = clip.subclip(0, seg_dur)
                
            processed_clips.append(clip)
        except Exception as e:
            print(f"Error processing video {vp}: {e}")

    if not processed_clips:
        print("Failed to load any video clips. Aborting.")
        return

    # Add random visual transitions between clips
    for i in range(1, len(processed_clips)):
        transition_type = random.choice(["hard_cut", "dip_to_black", "flash_white"])
        print(f"   Applying transition: {transition_type} between clip {i} and {i+1}")
        if transition_type == "dip_to_black":
            processed_clips[i-1] = processed_clips[i-1].fx(vfx.fadeout, 0.4, final_color=[0, 0, 0])
            processed_clips[i] = processed_clips[i].fx(vfx.fadein, 0.4, initial_color=[0, 0, 0])
        elif transition_type == "flash_white":
            processed_clips[i-1] = processed_clips[i-1].fx(vfx.fadeout, 0.3, final_color=[255, 255, 255])
            processed_clips[i] = processed_clips[i].fx(vfx.fadein, 0.3, initial_color=[255, 255, 255])

    base_clip = concatenate_videoclips(processed_clips, method="compose")

    # Audio Mix
    audio_tracks = []
    
    if music_audio:
        if music_audio.duration < target_duration:
            music_audio = music_audio.fx(afx.audio_loop, duration=target_duration)
        else:
            music_audio = music_audio.subclip(0, target_duration)
        music_audio = music_audio.fx(afx.volumex, 0.05) # Lowered from 0.10 to 0.05 so music stays in the background
        audio_tracks.append(music_audio)
        
    audio_tracks.append(voice_audio.set_start(0.5))
    
    # Add whoosh sound at transition points
    if whoosh_audio:
        current_time = 0
        for i in range(num_clips - 1):
            current_time += segment_durations[i]
            audio_tracks.append(whoosh_audio.set_start(current_time - 0.2)) # Lead the transition slightly
            
    final_audio = CompositeAudioClip(audio_tracks)
    # Audio fade out at the end so it doesn't end abruptly (USER REQUESTED)
    final_audio = final_audio.fx(afx.audio_fadeout, 0.2)
    
    base_clip = base_clip.set_audio(final_audio)
    layers = [base_clip]

    # Cinematic Color Grading (Teal overlay)
    color_overlay = (ColorClip(size=(TARGET_W, TARGET_H), color=(0, 20, 50))
                     .set_opacity(0.3)
                     .set_duration(target_duration))
    layers.append(color_overlay)

    # Vignette
    vignette_arr = make_vignette(TARGET_W, TARGET_H)
    vignette_clip = ImageClip(vignette_arr).set_duration(target_duration)
    layers.append(vignette_clip)

    # Dynamic Subtitles
    timestamps_file = audio_path + ".json"
    subtitle_clips = create_dynamic_subtitles(
        timestamps_file, TARGET_W, TARGET_H, target_duration, voice_offset=0.5
    )

    if subtitle_clips:
        for c in subtitle_clips:
            layers.append(c)
    else:
        text_img = create_text_image(textwrap.fill(text, width=25), TARGET_W, TARGET_H)
        txt_clip = (ImageClip(text_img)
                    .set_duration(target_duration)
                    .set_position('center')
                    .crossfadein(1.2))
        layers.append(txt_clip)



    # Progress Bar
    bar_height = 10

    def make_progress_bar_frame(t):
        progress = min(1.0, t / target_duration)
        w = max(1, int(TARGET_W * progress))
        img = np.zeros((bar_height, TARGET_W, 3), dtype=np.uint8)
        img[:, :w] = [255, 50, 50]  # Red bar
        return img

    def make_progress_bar_mask(t):
        progress = min(1.0, t / target_duration)
        w = max(1, int(TARGET_W * progress))
        mask = np.zeros((bar_height, TARGET_W))
        mask[:, :w] = 1.0
        return mask

    progress_bar_clip = VideoClip(make_progress_bar_frame, duration=target_duration)
    progress_bar_mask = VideoClip(make_progress_bar_mask, duration=target_duration, ismask=True)
    progress_clip = (progress_bar_clip
                      .set_mask(progress_bar_mask)
                      .set_position(('center', 'bottom')))
    layers.append(progress_clip)


    # Composite everything
    final_video = CompositeVideoClip(layers)

    # Subtle video fade in/out
    final_video = final_video.fadein(0.5).fadeout(0.8)

    print(f"\n   🖥️  Rendering on {CPU_THREADS} CPU threads @ 24fps...")
    print(f"   Resolution : {TARGET_W}x{TARGET_H}   Duration : {target_duration:.1f}s")
    print(f"   Estimated time : ~{int(target_duration * 24 / 60 / 1.5)} min (varies by CPU)\n")

    final_video.write_videofile(
        output_path,
        fps=24,               # 24fps = 20% fewer frames than 30fps
        codec="libx264",
        audio_codec="aac",
        threads=CPU_THREADS,  # Use ALL available CPU cores
        preset="ultrafast",
        ffmpeg_params=["-crf", "23"],  # CRF 23 = good quality + fast
        logger="bar"
    )

    # Clean up the ffmpeg-preprocessed temp videos
    for vp in bg_video_paths:
        preprocessed_path = vp + ".processed.mp4"
        if os.path.exists(preprocessed_path):
            try:
                os.remove(preprocessed_path)
            except Exception:
                pass

    print(f"\n✅ Video saved: {output_path} ({target_duration:.1f}s @ 24fps, {TARGET_W}x{TARGET_H})")

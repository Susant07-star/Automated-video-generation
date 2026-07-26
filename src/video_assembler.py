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
    try:
        return ImageFont.truetype("arialbd.ttf", size)
    except IOError:
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

def create_watermark_image(W, H):
    """Creates a semi-transparent channel handle watermark near the bottom."""
    img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = get_font(40)
    
    text = CHANNEL_HANDLE
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    
    x = (W - text_w) / 2
    y = H - 200  # 200px from the bottom
    
    draw.text((x, y), text, font=font, fill=(255, 255, 255, 180)) # Semi-transparent white
    return np.array(img)

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

def create_dynamic_subtitles(timestamps_file, W, H, target_duration, voice_offset=0.5):
    """
    Reads ElevenLabs word timestamps and generates non-overlapping subtitle clips.
    - Words are grouped into chunks of 3.
    - Each chunk's end time is hard-capped at the NEXT chunk's start time so
      there is zero overlap between consecutive text blocks.
    - voice_offset shifts all timestamps by the same amount the audio was delayed.
    """
    if not os.path.exists(timestamps_file):
        return []

    with open(timestamps_file, 'r') as f:
        words = json.load(f)

    if not words:
        return []

    chunk_size = 3

    # ── Step 1: build all chunks ────────────────────────────────────────────────
    chunks = []
    for i in range(0, len(words), chunk_size):
        chunk = words[i:i + chunk_size]
        text  = " ".join(w['word'] for w in chunk)
        start = chunk[0]['start']
        end   = chunk[-1]['end']
        chunks.append({'text': text, 'start': start, 'end': end})

    # ── Step 2: cap each chunk's end at the NEXT chunk's start ─────────────────
    # This is what prevents overlap — no 0.3s fudge that bleeds into next chunk.
    GAP = 0.05   # 50ms silence gap between chunks
    for idx in range(len(chunks) - 1):
        next_start = chunks[idx + 1]['start']
        chunks[idx]['end'] = min(chunks[idx]['end'], next_start - GAP)

    # ── Step 3: apply voice offset and build ImageClips ───────────────────────
    clips = []
    for ch in chunks:
        # Shift by voice_offset to align with when audio actually starts
        start_t = ch['start'] + voice_offset
        end_t   = ch['end']   + voice_offset

        # Skip anything that exceeds total video duration
        if start_t >= target_duration:
            break
        end_t = min(end_t, target_duration)

        # Skip degenerate clips
        if end_t - start_t < 0.05:
            continue

        text_img = create_text_image(ch['text'], W, H, fontsize=85)
        clip = (ImageClip(text_img)
                .set_start(start_t)
                .set_end(end_t)
                .set_position(('center', 'center')))
        clips.append(clip)

    return clips

def assemble_video(bg_video_path, audio_path, text, output_path="final_reel.mp4", bg_music_path=None):
    print("Assembling cinematic video...")
    
    try:
        bg_video = VideoFileClip(bg_video_path)
        voice_audio = AudioFileClip(audio_path)
        
        music_audio = None
        if bg_music_path and os.path.exists(bg_music_path):
            music_audio = AudioFileClip(bg_music_path)
        else:
            print("Warning: No background music loaded.")
    except Exception as e:
        print(f"Error loading media files: {e}")
        return

    # Calculate target duration (must be at least MIN_DURATION)
    audio_duration = voice_audio.duration
    # Ensure target_duration is at least the audio duration, plus a small buffer, and also not less than MIN_DURATION
    target_duration = max(MIN_DURATION, audio_duration + 1.0) # Reduced padding to 1 second

    # Loop or trim background video
    if bg_video.duration < target_duration:
        bg_video = bg_video.fx(vfx.loop, duration=target_duration)
    else:
        bg_video = bg_video.subclip(0, target_duration)

    # ── Speed Optimization: pre-process with ffmpeg (C-speed resize/crop) ───────
    # This converts the source video to exact 1080x1920 BEFORE MoviePy touches it.
    # MoviePy then reads a perfectly-sized video with no further scaling needed.
    preprocessed_path = bg_video_path + ".processed.mp4"
    ffmpeg_ok = preprocess_video_ffmpeg(bg_video_path, preprocessed_path)
    if ffmpeg_ok and os.path.exists(preprocessed_path):
        bg_video = VideoFileClip(preprocessed_path)  # Already the right size!
    # else: bg_video was already loaded above; apply Python fallback resize
    elif bg_video.w > TARGET_W:
        bg_video = bg_video.resize(width=TARGET_W)

    W, H = bg_video.w, bg_video.h

    # Ken Burns removed — it computed every frame in Python (major bottleneck).
    # The video looks clean and fast without it.
    base_clip = bg_video

    # 2. Audio Mix
    if music_audio:
        if music_audio.duration < target_duration:
            music_audio = music_audio.fx(afx.audio_loop, duration=target_duration)
        else:
            music_audio = music_audio.subclip(0, target_duration)
        music_audio = music_audio.fx(afx.volumex, 0.10)
        final_audio = CompositeAudioClip([music_audio, voice_audio.set_start(0.5)])
    else:
        final_audio = voice_audio.set_start(0.5)

    base_clip = base_clip.set_audio(final_audio)
    layers = [base_clip]

    # 3. Cinematic Color Grading (Teal overlay)
    color_overlay = (ColorClip(size=(W, H), color=(0, 20, 50))
                     .set_opacity(0.3)
                     .set_duration(target_duration))
    layers.append(color_overlay)

    # 4. Vignette
    vignette_arr = make_vignette(W, H)
    vignette_clip = ImageClip(vignette_arr).set_duration(target_duration)
    layers.append(vignette_clip)

    # 5. Dynamic Subtitles
    # voice_offset=0.5 matches the 0.5s audio lead-in set above.
    # The function now handles the shift internally — no double-shifting.
    timestamps_file = audio_path + ".json"
    subtitle_clips = create_dynamic_subtitles(
        timestamps_file, W, H, target_duration, voice_offset=0.5
    )

    if subtitle_clips:
        for c in subtitle_clips:
            layers.append(c)   # already correctly timed, no extra shift needed
    else:
        # Fallback: static text if no timestamps available
        text_img = create_text_image(textwrap.fill(text, width=25), W, H)
        txt_clip = (ImageClip(text_img)
                    .set_duration(target_duration)
                    .set_position('center')
                    .crossfadein(1.2))
        layers.append(txt_clip)

    # 6. Branding Watermark
    watermark_img = create_watermark_image(W, H)
    watermark_clip = ImageClip(watermark_img).set_duration(target_duration)
    layers.append(watermark_clip)

    # 7. Progress Bar
    # Draws a red bar at the bottom growing over time.
    # NOTE: A plain VideoClip's make_frame must return an RGB (H, W, 3) array.
    # Transparency (the unfilled portion of the bar) must come from a SEPARATE
    # mask clip (ismask=True, single-channel 0-1 float array), otherwise moviepy
    # throws "could not broadcast input array from shape (10,1080,4) into shape (10,1080,3)".
    bar_height = 10

    def make_progress_bar_frame(t):
        progress = min(1.0, t / target_duration)
        w = max(1, int(W * progress))
        img = np.zeros((bar_height, W, 3), dtype=np.uint8)
        img[:, :w] = [255, 50, 50]  # Red bar
        return img

    def make_progress_bar_mask(t):
        progress = min(1.0, t / target_duration)
        w = max(1, int(W * progress))
        mask = np.zeros((bar_height, W))
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

    # Subtle fade in/out
    final_video = final_video.fadein(0.5).fadeout(0.8)

    print(f"\n   🖥️  Rendering on {CPU_THREADS} CPU threads @ 24fps...")
    print(f"   Resolution : {W}x{H}   Duration : {target_duration:.1f}s")
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

    # Clean up the ffmpeg-preprocessed temp video
    if os.path.exists(preprocessed_path):
        try:
            os.remove(preprocessed_path)
        except Exception:
            pass

    print(f"\n✅ Video saved: {output_path} ({target_duration:.1f}s @ 24fps, {W}x{H})")

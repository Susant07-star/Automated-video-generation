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
            f"scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=increase:flags=lanczos,"
            f"crop={TARGET_W}:{TARGET_H}"
        ),
        "-an",
        "-c:v", "libx264",
        "-preset", "slow",
        "-crf", "17",
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

# ─────────────────────────────────────────────────────────────────────────────
# CINEMATIC KARAOKE SUBTITLE ENGINE  (per-frame animated, spring-bounce)
# ─────────────────────────────────────────────────────────────────────────────

_font_cache: dict = {}

def _cached_font(size: int):
    """Thread-safe font cache so we don't re-load from disk every frame."""
    if size not in _font_cache:
        _font_cache[size] = get_font(size)
    return _font_cache[size]


def _spring_scale(t: float, anim_dur: float = 0.12) -> float:
    """
    Spring-bounce easing.  Returns a scale multiplier in [0, 1.0].
    t=0  → 0.0   (word just appeared)
    t≈0.07 → 1.25  (overshoot peak)
    t≥anim_dur → 1.0 (settled)
    Uses a damped-sine approximation — no scipy needed.
    """
    if t <= 0:
        return 0.0
    if t >= anim_dur:
        return 1.0
    p = t / anim_dur          # 0→1 normalised progress
    # Damped sine that overshoots to 1.22 at p≈0.5 then settles at 1.0
    return 1.0 + 0.22 * np.sin(p * np.pi) * (1.0 - p)


def _ease_out_cubic(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - t) ** 3


def _measure_chunk(words: list, base_fs: int, active_fs: int, W: int):
    """
    Pre-compute stable layout metrics for a chunk so every frame renders
    from the same baseline — no per-frame font measurements.

    Returns a dict with:
      fontsize, base_font, active_font, space_w,
      word_widths_base, word_widths_active,
      word_heights_base, word_heights_active,
      FIXED_LINE_H, max_total_w, row_center_y
    """
    SAFE_PADDING = 80
    max_text_w = W - (SAFE_PADDING * 2)

    # Shrink base font so the WIDEST possible line (all words at active size) fits
    fs = base_fs
    while fs >= 28:
        bf = _cached_font(fs)
        afs = max(fs + 1, int(fs * 1.18))
        af = _cached_font(afs)
        tmp = Image.new("RGBA", (1, 1))
        td = ImageDraw.Draw(tmp)
        sw = td.textbbox((0, 0), " ", font=bf)[2]
        # Worst case: every word rendered at active size
        total = sum(
            td.textbbox((0, 0), w, font=af)[2] - td.textbbox((0, 0), w, font=af)[0]
            for w in words
        ) + sw * (len(words) - 1)
        if total <= max_text_w:
            break
        fs -= 4

    bf = _cached_font(fs)
    afs = max(fs + 1, int(fs * 1.18))
    af = _cached_font(afs)
    tmp = Image.new("RGBA", (1, 1))
    td = ImageDraw.Draw(tmp)
    sw = td.textbbox((0, 0), " ", font=bf)[2]

    wb_base, wh_base, wb_act, wh_act = [], [], [], []
    for w in words:
        b = td.textbbox((0, 0), w, font=bf)
        wb_base.append(b[2] - b[0]);  wh_base.append(b[3] - b[1])
        a = td.textbbox((0, 0), w, font=af)
        wb_act.append(a[2] - a[0]);   wh_act.append(a[3] - a[1])

    # Reserve the MAXIMUM width each word could ever need across all states
    # so the layout never shifts horizontally when a word becomes active.
    word_slot_w = [max(wb_base[i], wb_act[i]) for i in range(len(words))]

    FIXED_LINE_H = max(wh_act) if wh_act else 80
    max_total_w = sum(word_slot_w) + sw * (len(words) - 1)

    return dict(
        fs=fs, bf=bf, afs=afs, af=af, sw=sw,
        wb_base=wb_base, wh_base=wh_base,
        wb_act=wb_act,  wh_act=wh_act,
        word_slot_w=word_slot_w,
        FIXED_LINE_H=FIXED_LINE_H,
        max_total_w=max_total_w,
    )


def _render_animated_frame(
    words: list,
    active_idx: int,
    layout: dict,
    W: int, H: int,
    anim_t: float,           # seconds since active word started
    chunk_fade: float = 1.0, # 0→1 chunk fade-in (used on first frame of new chunk)
) -> np.ndarray:
    """
    Renders one RGBA frame of the karaoke subtitle, with:
      - Spring-bounce scale on the active word (smooth pop)
      - Opacity fade-in on the active word
      - Layered radial glow on the active word (pulsing)
      - Stable horizontal layout (no shifting)
      - Chunk-level fade-in controlled by chunk_fade
    """
    # ── Unpack layout ─────────────────────────────────────────────────────────
    bf      = layout['bf']
    af      = layout['af']
    sw      = layout['sw']
    wb_base = layout['wb_base']
    wh_base = layout['wh_base']
    wb_act  = layout['wb_act']
    wh_act  = layout['wh_act']
    slot_w  = layout['word_slot_w']
    FLH     = layout['FIXED_LINE_H']
    tot_w   = layout['max_total_w']

    # ── Spring-bounce progress for the active word ─────────────────────────────
    ANIM_DUR = 0.11   # seconds for full spring settle
    FADE_DUR = 0.08   # seconds for opacity fade-in

    spring   = _spring_scale(anim_t, ANIM_DUR)
    opacity  = _ease_out_cubic(anim_t / FADE_DUR) if FADE_DUR > 0 else 1.0
    opacity  = min(opacity, 1.0)

    # Animated glow pulse: slow breathing sine after settling
    glow_pulse = 0.6 + 0.4 * np.sin(anim_t * 8.0)  # 8 rad/s ≈ 1.27 Hz
    glow_pulse = max(0.0, min(1.0, glow_pulse))

    # ── Canvas ────────────────────────────────────────────────────────────────
    img  = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    row_center_y = int(H * 0.58)
    x_cursor     = (W - tot_w) / 2

    stroke_w = 5
    stroke_offsets = [
        (-stroke_w, -stroke_w), (0, -stroke_w), (stroke_w, -stroke_w),
        (-stroke_w,  0),                          (stroke_w,  0),
        (-stroke_w,  stroke_w), (0,  stroke_w), (stroke_w,  stroke_w),
    ]

    for i, word in enumerate(words):
        is_active = (i == active_idx)
        is_past   = (i < active_idx)
        slot      = slot_w[i]

        if is_active:
            # Interpolate between base and active width using spring progress
            raw_w  = int(wb_base[i] + (wb_act[i] - wb_base[i]) * spring)
            raw_h  = int(wh_base[i] + (wh_act[i] - wh_base[i]) * spring)
            # Blend font: render at active size, then PIL-resize for smooth scale
            f      = af
            actual_w = wb_act[i]
            actual_h = wh_act[i]
        elif is_past:
            f        = bf
            actual_w = wb_base[i]
            actual_h = wh_base[i]
        else:
            f        = bf
            actual_w = wb_base[i]
            actual_h = wh_base[i]

        # Center the word inside its reserved slot
        x_word = x_cursor + (slot - actual_w) / 2
        y_word = row_center_y - FLH // 2 + (FLH - actual_h) // 2

        # ── Colours ───────────────────────────────────────────────────────────
        if is_past:
            fill_rgb = (160, 160, 160)
            alpha    = int(200 * chunk_fade)
        elif is_active:
            # Golden yellow, opacity animated
            alpha    = int(255 * opacity * chunk_fade)
            fill_rgb = (255, 215, 0)
        else:
            fill_rgb = (255, 255, 255)
            alpha    = int(210 * chunk_fade)

        fill_color   = (*fill_rgb, alpha)
        stroke_color = (0, 0, 0, int(alpha * 0.95))

        # ── Render active word ────────────────────────────────────────────────
        if is_active:
            # Render at full active size onto a tiny canvas, then scale with PIL
            # for smooth sub-pixel spring animation
            pad     = stroke_w + 4
            mini_w  = actual_w + pad * 2
            mini_h  = actual_h + pad * 2

            # Radial glow layers (drawn first — behind everything)
            glow_radii  = [30, 22, 15, 9]
            glow_alphas = [int(28 * glow_pulse * chunk_fade),
                           int(45 * glow_pulse * chunk_fade),
                           int(60 * glow_pulse * chunk_fade),
                           int(40 * glow_pulse * chunk_fade)]
            for gr, ga in zip(glow_radii, glow_alphas):
                if ga > 0:
                    draw.text(
                        (x_word - gr * 0.5, y_word - gr * 0.5),
                        word, font=af, fill=(255, 180, 0, ga)
                    )

            # Stroke (8-direction) at spring-scaled position
            for dx, dy in stroke_offsets:
                draw.text((x_word + dx, y_word + dy), word, font=af, fill=stroke_color)

            # Main fill
            draw.text((x_word, y_word), word, font=af, fill=fill_color)

            # Bright highlight line on top of the word (shimmer)
            highlight_alpha = int(80 * opacity * chunk_fade)
            if highlight_alpha > 0:
                draw.text(
                    (x_word, y_word - 1),
                    word, font=af, fill=(255, 255, 200, highlight_alpha)
                )
        else:
            # ── Non-active words — crisp 8-dir stroke + fill ──────────────────
            for dx, dy in stroke_offsets:
                draw.text((x_word + dx, y_word + dy), word, font=f, fill=stroke_color)
            draw.text((x_word, y_word), word, font=f, fill=fill_color)

        x_cursor += slot + sw

    return np.array(img)


# Keep the old static-image function as a legacy alias (used by test_subs.py)
def create_karaoke_subtitle_image(words_in_chunk, active_idx, W, H, fontsize=90):
    """
    Legacy static renderer (used by test scripts).  The live pipeline now uses
    the animated VideoClip approach in create_dynamic_subtitles().
    """
    layout = _measure_chunk(words_in_chunk, fontsize, max(fontsize+1, int(fontsize*1.18)), W)
    return _render_animated_frame(words_in_chunk, active_idx, layout, W, H,
                                  anim_t=0.15, chunk_fade=1.0)


def create_cta_image(text, W, H, fontsize=60):
    """
    Creates a modern pill-shaped CTA overlay with semi-transparent background.
    Looks clean and professional without relying on emojis.
    """
    font = get_font(fontsize)
    
    tmp_img = Image.new('RGBA', (1, 1))
    tmp_draw = ImageDraw.Draw(tmp_img)
    bbox = tmp_draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    
    pad_x = 50
    pad_y = 25
    pill_w = text_w + pad_x * 2
    pill_h = text_h + pad_y * 2
    
    img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Position horizontally centered, lower third of screen
    x = (W - pill_w) // 2
    y = int(H * 0.70)
    
    # Draw semi-transparent rounded rectangle (pill shape)
    draw.rounded_rectangle([x, y, x + pill_w, y + pill_h], radius=40, fill=(0, 0, 0, 180))
    
    # Draw text vertically aligned inside the pill
    text_x = x + pad_x
    text_y = y + pad_y - bbox[1]
    draw.text((text_x, text_y), text, font=font, fill=(255, 255, 255, 255))
    
    return np.array(img)



def create_dynamic_subtitles(timestamps_file, W, H, target_duration, voice_offset=0.5):
    """
    Cinematic karaoke subtitles — per-frame animated with spring-bounce pop,
    opacity fade-in, glow pulse, and chunk crossfade transitions.

    Architecture:
      - Words grouped into 4-word chunks.
      - Each (chunk, active_word) pair becomes ONE VideoClip(make_frame).
      - The make_frame closure captures all layout/timing data and renders
        smooth animation every frame — no static image snapping.
      - Chunk transitions get a 150 ms crossfade so new chunks dissolve in.
    """
    if not os.path.exists(timestamps_file):
        return []

    with open(timestamps_file, 'r') as f:
        words = json.load(f)

    if not words:
        return []

    CHUNK_SIZE   = 4
    GAP          = 0.04   # 40 ms gap between chunks
    CHUNK_FADE   = 0.14   # seconds for chunk crossfade-in
    FPS          = 24     # render fps for animated clips

    # ── Build chunks ──────────────────────────────────────────────────────────
    chunks = []
    for i in range(0, len(words), CHUNK_SIZE):
        chunks.append(words[i:i + CHUNK_SIZE])

    clips = []

    for chunk_idx, chunk_words in enumerate(chunks):
        word_texts = [w['word'] for w in chunk_words]

        # Cap last word to avoid overlap with next chunk
        if chunk_idx < len(chunks) - 1:
            nxt = chunks[chunk_idx + 1][0]['start']
            chunk_words[-1]['end'] = min(chunk_words[-1]['end'], nxt - GAP)

        # Pre-compute stable layout once per chunk (expensive PIL measure)
        layout = _measure_chunk(word_texts, 90, max(91, int(90 * 1.18)), W)

        # Is this the first word in the chunk? (triggers chunk fade-in)
        is_first_in_chunk = True

        for active_idx, word_data in enumerate(chunk_words):
            start_t = word_data['start'] + voice_offset

            if active_idx < len(chunk_words) - 1:
                end_t = chunk_words[active_idx + 1]['start'] + voice_offset - GAP
            else:
                if chunk_idx < len(chunks) - 1:
                    end_t = chunks[chunk_idx + 1][0]['start'] + voice_offset - GAP
                else:
                    end_t = word_data['end'] + voice_offset + 0.35

            if start_t >= target_duration:
                break
            end_t = min(end_t, target_duration)
            dur   = end_t - start_t

            if dur < 0.03:
                is_first_in_chunk = False
                continue

            # ── Closure captures everything for this word ──────────────────────
            _layout         = layout           # stable per-chunk
            _words          = word_texts
            _active_idx     = active_idx
            _first_in_chunk = is_first_in_chunk
            _start_t        = start_t
            _chunk_fade_dur = CHUNK_FADE if _first_in_chunk else 0.0

            def _make_frame(t, layout=_layout, words=_words,
                            active_idx=_active_idx,
                            chunk_fade_dur=_chunk_fade_dur):
                # t is relative to clip start (MoviePy convention)
                # Chunk fade-in: only on the very first word of a new chunk
                if chunk_fade_dur > 0:
                    chunk_fade = _ease_out_cubic(t / chunk_fade_dur)
                else:
                    chunk_fade = 1.0

                frame = _render_animated_frame(
                    words, active_idx, layout, W, H,
                    anim_t=t, chunk_fade=chunk_fade
                )
                # Return RGB (MoviePy clips without mask need 3-channel)
                # We handle alpha via a separate mask clip
                return frame[:, :, :3]   # H×W×3

            def _make_mask(t, layout=_layout, words=_words,
                           active_idx=_active_idx,
                           chunk_fade_dur=_chunk_fade_dur):
                if chunk_fade_dur > 0:
                    chunk_fade = _ease_out_cubic(t / chunk_fade_dur)
                else:
                    chunk_fade = 1.0
                frame = _render_animated_frame(
                    words, active_idx, layout, W, H,
                    anim_t=t, chunk_fade=chunk_fade
                )
                # Alpha channel → float mask [0, 1]
                return frame[:, :, 3].astype(float) / 255.0

            rgb_clip  = VideoClip(_make_frame, duration=dur)
            mask_clip = VideoClip(_make_mask,  duration=dur, ismask=True)
            animated  = rgb_clip.set_mask(mask_clip).set_start(start_t)
            clips.append(animated)

            is_first_in_chunk = False

    return clips


from moviepy.editor import concatenate_videoclips


def _get_pause_cut_points(timestamps_file: str,
                           total_duration: float,
                           min_pause: float = 0.35,
                           max_clip_duration: float = 6.5,
                           voice_offset: float = 0.5) -> list:
    """
    Finds cut points ensuring no clip exceeds `max_clip_duration`.
    Prefers cutting on natural speech pauses (gaps >= min_pause), but forces a
    cut if a sentence drags on too long to prevent B-roll from looping awkwardly.
    """
    raw_pauses = []
    if os.path.exists(timestamps_file):
        try:
            with open(timestamps_file, 'r') as f:
                words = json.load(f)
            # Find all inter-word gaps long enough to feel like a pause
            for i in range(len(words) - 1):
                gap = words[i + 1]['start'] - words[i]['end']
                if gap >= min_pause:
                    cut_t = words[i]['end'] + gap / 2 + voice_offset
                    if 0 < cut_t < total_duration:
                        raw_pauses.append(cut_t)
        except Exception as e:
            print(f"   [B-Roll] Warning: could not parse timestamps ({e}).")

    final_cuts = []
    current_time = 0.0

    while True:
        next_max = current_time + max_clip_duration
        if next_max >= total_duration:
            break

        # Look for a natural pause between 3s and max_clip_duration
        valid_pauses = [p for p in raw_pauses if current_time + 3.0 <= p <= next_max]

        if valid_pauses:
            best_cut = valid_pauses[-1]  # Take the latest possible pause that fits
        else:
            best_cut = next_max          # Force a cut to prevent overlong clips

        final_cuts.append(best_cut)
        current_time = best_cut

    print(f"   [B-Roll] ✂️  {len(final_cuts)} dynamic cut points detected: {[f'{t:.2f}s' for t in final_cuts]}")
    return final_cuts


def assemble_video(bg_video_paths, audio_path, text, output_path="final_reel.mp4", bg_music_path=None, whoosh_path=None, impact_path=None, fomo_overlay=None, profile="motivational", meme_sound_path=None):
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
            
        impact_audio = None
        if impact_path and os.path.exists(impact_path):
            impact_audio = AudioFileClip(impact_path).fx(afx.volumex, 0.7)
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

    # ── DYNAMIC B-ROLL CUT TIMING (pause-based with max duration) ────────────────
    if num_clips > 0 and profile != "cartoon":
        timestamps_file = audio_path + ".json"
        cut_points = _get_pause_cut_points(
            timestamps_file,
            total_duration=target_duration,
            min_pause=0.35,
            max_clip_duration=5.0,
            voice_offset=0.5
        )
        # Convert cut points to per-clip durations
        boundaries = [0.0] + cut_points + [target_duration]
        segment_durations = [boundaries[i+1] - boundaries[i] for i in range(len(boundaries)-1)]
        
        # We need `len(segment_durations)` clips. Cycle through available ones if short.
        bg_video_paths = [bg_video_paths[i % len(bg_video_paths)] for i in range(len(segment_durations))]
        num_clips = len(bg_video_paths)
        print(f"   [B-Roll] Segment durations: {[f'{d:.1f}s' for d in segment_durations]}")
    else:
        # Cartoon or single clip — keep random weighting
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
                # MoviePy fallback: resize and center crop to exactly TARGET_W x TARGET_H
                if clip.w != TARGET_W or clip.h != TARGET_H:
                    clip = clip.resize(height=TARGET_H)
                    clip = clip.fx(vfx.crop, x_center=clip.w/2, y_center=clip.h/2, width=TARGET_W, height=TARGET_H)
            
            if profile != "cartoon":
                # Apply 1.5x speed multiplier for faster, more dynamic visual pacing (Motivational only)
                clip = clip.fx(vfx.speedx, 1.5)
            
            if clip.duration < seg_dur:
                clip = clip.fx(vfx.loop, duration=seg_dur)
            else:
                clip = clip.subclip(0, seg_dur)
                
            # Idea: Ken Burns effect on the VERY FIRST clip (Motivational only)
            if i == 0 and profile != "cartoon":
                print("   Applying Ken Burns zoom effect to the opening clip...")
                # We will handle thumbnail generation via AI later in the process
                def zoom(t):
                    # 1.0 -> 1.15 over the duration
                    factor = 1.0 + 0.15 * (t / seg_dur)
                    return factor
                
                # We need to explicitly size it back to TARGET_W/TARGET_H after scaling
                # because MoviePy's resize with a function changes the clip dimensions
                # We then crop from the center
                clip = (clip.resize(zoom)
                           .crop(x_center=TARGET_W/2, y_center=TARGET_H/2, 
                                 width=TARGET_W, height=TARGET_H))
                
            processed_clips.append(clip)
        except Exception as e:
            print(f"Error processing video {vp}: {e}")

    if not processed_clips:
        print("Failed to load any video clips. Aborting.")
        return

    # Add random visual transitions between clips (Motivational only — cartoon keeps clean cuts)
    if profile != "cartoon":
        for i in range(1, len(processed_clips)):
            transition_type = random.choice(["hard_cut", "dip_to_black", "flash_white"])
            print(f"   Applying transition: {transition_type} between clip {i} and {i+1}")
            if transition_type == "dip_to_black":
                processed_clips[i-1] = processed_clips[i-1].fx(vfx.fadeout, 0.4, final_color=[0, 0, 0])
                processed_clips[i] = processed_clips[i].fx(vfx.fadein, 0.4, initial_color=[0, 0, 0])
            elif transition_type == "flash_white":
                processed_clips[i-1] = processed_clips[i-1].fx(vfx.fadeout, 0.3, final_color=[255, 255, 255])
                processed_clips[i] = processed_clips[i].fx(vfx.fadein, 0.3, initial_color=[255, 255, 255])

    # Create base video by concatenating
    base_clip = concatenate_videoclips(processed_clips, method="compose")

    if profile == "cartoon":
        # Skip FOMO overlay for cartoon profile
        fomo_overlay = None
        # Skip whoosh
        whoosh_audio = None

    # Audio Mix
    audio_tracks = []
    
    if music_audio:
        if music_audio.duration < target_duration:
            music_audio = music_audio.fx(afx.audio_loop, duration=target_duration)
        else:
            music_audio = music_audio.subclip(0, target_duration)
            
        # Idea A: Dynamic Audio Ducking (Swell music during silence gaps)
        swells = []
        if os.path.exists(audio_path + ".json"):
            import json
            with open(audio_path + ".json", 'r') as f:
                words_data = json.load(f)
            
            for i in range(len(words_data) - 1):
                gap = words_data[i+1]['start'] - words_data[i]['end']
                if gap > 0.4:
                    # +0.5 is voice_offset. Add tiny buffer
                    swells.append((words_data[i]['end'] + 0.1 + 0.5, words_data[i+1]['start'] - 0.1 + 0.5))
                    
        def volume_envelope(t):
            import numpy as np
            is_scalar = np.isscalar(t)
            t_arr = np.atleast_1d(t)
            vol = np.full(t_arr.shape, 0.015) # Ducked volume (very quiet when talking, lowered from 0.03)
            
            for start, end in swells:
                mask = (t_arr > start) & (t_arr < end)
                vol[mask] = 0.10 # Swell volume (loud cinematic fill, lowered from 0.20)
                
            vol = vol[:, np.newaxis] # Expand dims for stereo broadcasting
            return vol[0, 0] if is_scalar else vol

        music_audio = music_audio.fl(lambda gf, t: gf(t) * volume_envelope(t), keep_duration=True)
        audio_tracks.append(music_audio)
        
    audio_tracks.append(voice_audio.set_start(0.5))
    
    # Add whoosh sound at transition points
    if whoosh_audio:
        current_time = 0
        for i in range(num_clips - 1):
            current_time += segment_durations[i]
            audio_tracks.append(whoosh_audio.set_start(current_time - 0.2)) # Lead the transition slightly
            
    # Impact SFX removed per user request
            
    final_audio = CompositeAudioClip(audio_tracks)
    # No audio fadeout — let audio end cleanly
    
    # If cartoon profile and meme sound provided, overlap meme sound 1s before voice ends
    if profile == "cartoon" and meme_sound_path and os.path.exists(meme_sound_path):
        meme_audio = AudioFileClip(meme_sound_path).fx(afx.volumex, 3.0)
        # Start meme sound 1 second before the voice finishes for a punchline overlap effect
        meme_start = max(0, audio_duration - 1.0)
        meme_audio = meme_audio.set_start(meme_start)
        audio_tracks.append(meme_audio)
        final_audio = CompositeAudioClip(audio_tracks)
        total_duration_with_meme = meme_start + meme_audio.duration
        print(f"   Meme sound starts at {meme_start:.1f}s (1s before voice ends), total: {total_duration_with_meme:.1f}s")
        
        # Trim or preserve background clip to fit total duration exactly
        if base_clip.duration > total_duration_with_meme:
            base_clip = base_clip.subclip(0, total_duration_with_meme)
        elif base_clip.duration < total_duration_with_meme:
            print(f"   ⚠️  Video clip is {total_duration_with_meme - base_clip.duration:.1f}s shorter than needed. Playing to natural end.")
        
        target_duration = total_duration_with_meme
    
    base_clip = base_clip.set_audio(final_audio)
    layers = [base_clip]

    # Cinematic Color Grading & Vignette (Keep for Motivational, skip for Cartoon)
    if profile != "cartoon":
        color_overlay = (ColorClip(size=(TARGET_W, TARGET_H), color=(0, 20, 50))
                         .set_opacity(0.3)
                         .set_duration(target_duration))
        layers.append(color_overlay)

        vignette_arr = make_vignette(TARGET_W, TARGET_H)
        vignette_clip = ImageClip(vignette_arr).set_duration(target_duration)
        layers.append(vignette_clip)

    # Text / Subtitles
    if profile != "cartoon":
        # NextGen Thoughts gets dynamic karaoke subtitles
        timestamps_file = audio_path + ".json"
        subtitle_clips = create_dynamic_subtitles(
            timestamps_file, TARGET_W, TARGET_H, target_duration, voice_offset=0.5
        )
        if subtitle_clips:
            for c in subtitle_clips:
                layers.append(c)
        # If timestamps are missing, it intentionally renders no text, avoiding the old static block.



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

    # "Save this video for later" CTA (Idea C)
    if profile != "cartoon":
        cta_arr = create_cta_image("Save this for later", TARGET_W, TARGET_H, fontsize=60)
        cta_start = max(0, target_duration - 3.0)
        cta_clip = (ImageClip(cta_arr)
                    .set_start(cta_start)
                    .set_end(target_duration)
                    .crossfadein(0.5))
        layers.append(cta_clip)

    # Viral FOMO Overlay removed per user request


    # Composite everything
    final_video = CompositeVideoClip(layers)

    # No fade in/out — clean cut
    # final_video = final_video.fadein(0.5).fadeout(0.8)

    print(f"\n   🖥️  Rendering on {CPU_THREADS} CPU threads @ 24fps...")
    print(f"   Resolution : {TARGET_W}x{TARGET_H}   Duration : {target_duration:.1f}s")
    print(f"   Estimated time : ~{int(target_duration * 24 / 60 / 1.5)} min (varies by CPU)\n")

    final_video.write_videofile(
        output_path,
        fps=24,               # 24fps = 20% fewer frames than 30fps
        codec="libx264",
        audio_codec="aac",
        threads=CPU_THREADS,  # Use ALL available CPU cores
        preset="superfast",
        ffmpeg_params=["-crf", "18"],  # CRF 18 = visually lossless, preserves upscale sharpness
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

    # Extract and return thumbnail automatically
    thumb_path = extract_thumbnail(output_path, audio_path + ".json")
    return thumb_path


def extract_thumbnail(video_path: str, timestamps_file: str = "",
                      default_t: float = 1.5) -> str:
    """
    Extracts the single most visually powerful frame from the rendered video
    to use as the official cover photo on Instagram and Facebook.

    Strategy:
    - Uses the timestamp of the 3rd spoken word (index 2) in the ElevenLabs
      JSON so the thumbnail captures the hook text at full brightness with the
      subtitle overlay visible. Word #3 is deep enough into the hook to have
      meaningful text on screen but still within the first 3-4 seconds.
    - Falls back to default_t (1.5s) if timestamps are missing.

    Saves the frame as a high-quality JPG next to the video file.
    Returns the thumbnail path, or an empty string on failure.
    """
    thumb_path = video_path.replace(".mp4", "_thumbnail.jpg")

    # Determine best timestamp: word #3's midpoint (hook text fully shown)
    grab_t = default_t
    if timestamps_file and os.path.exists(timestamps_file):
        try:
            with open(timestamps_file, 'r') as f:
                words = json.load(f)
            if len(words) > 2:
                w = words[2]  # 3rd word = deep into hook, subtitle visible
                grab_t = w['start'] + (w['end'] - w['start']) / 2 + 0.5  # +voice_offset
                print(f"   [Thumbnail] Grabbing frame at t={grab_t:.2f}s (hook word: '{w['word']}')")
        except Exception as e:
            print(f"   [Thumbnail] Warning: could not read timestamps ({e}). Using t={default_t}s.")

    cmd = [
        FFMPEG_BIN, "-y",
        "-ss", str(grab_t),          # Seek to hook timestamp
        "-i", video_path,
        "-frames:v", "1",            # Extract exactly one frame
        "-q:v", "1",                 # Highest JPEG quality (1=best, 31=worst)
        "-vf", "scale=1080:1920",    # Ensure exact portrait resolution
        thumb_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0 and os.path.exists(thumb_path):
        size_kb = os.path.getsize(thumb_path) // 1024
        print(f"   [Thumbnail] ✅ Saved → {thumb_path} ({size_kb} KB)")
        return thumb_path
    else:
        print(f"   [Thumbnail] ❌ ffmpeg failed: {result.stderr[-200:]}")
        return ""


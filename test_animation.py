# -*- coding: utf-8 -*-
import sys, os, argparse, json, tempfile, multiprocessing
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))
from PIL import Image
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.LANCZOS
from moviepy.editor import CompositeVideoClip, ColorClip
from video_assembler import create_dynamic_subtitles

W_WORDS = [
    {'word': 'Your',         'start': 0.00, 'end': 0.18},
    {'word': 'closest',     'start': 0.20, 'end': 0.55},
    {'word': 'friend',      'start': 0.57, 'end': 0.85},
    {'word': 'might',       'start': 0.87, 'end': 1.10},
    {'word': 'be',          'start': 1.20, 'end': 1.35},
    {'word': 'your',        'start': 1.37, 'end': 1.55},
    {'word': 'biggest',     'start': 1.57, 'end': 1.90},
    {'word': 'threat',      'start': 1.92, 'end': 2.30},
    {'word': 'Robert',      'start': 2.55, 'end': 2.80},
    {'word': 'Greene',      'start': 2.82, 'end': 3.10},
    {'word': 'called',      'start': 3.12, 'end': 3.38},
    {'word': 'this',        'start': 3.40, 'end': 3.55},
    {'word': 'Law',         'start': 3.65, 'end': 3.82},
    {'word': 'Fourteen',    'start': 3.84, 'end': 4.22},
    {'word': 'Pose',        'start': 4.30, 'end': 4.55},
    {'word': 'as',          'start': 4.57, 'end': 4.68},
    {'word': 'a',           'start': 4.78, 'end': 4.85},
    {'word': 'Friend',      'start': 4.87, 'end': 5.15},
    {'word': 'Work',        'start': 5.22, 'end': 5.45},
    {'word': 'as',          'start': 5.47, 'end': 5.60},
    {'word': 'a',           'start': 5.68, 'end': 5.74},
    {'word': 'Spy',         'start': 5.76, 'end': 6.15},
    {'word': 'This',        'start': 6.30, 'end': 6.50},
    {'word': 'is',          'start': 6.52, 'end': 6.85},
    {'word': 'friendship',  'start': 7.00, 'end': 7.45},
    {'word': 'its',         'start': 7.50, 'end': 7.68},
    {'word': 'pure',        'start': 7.70, 'end': 7.95},
    {'word': 'intelligence','start': 7.97, 'end': 8.55},
    {'word': 'gathering',   'start': 8.60, 'end': 9.10},
    {'word': 'Guard',       'start': 9.20, 'end': 9.48},
    {'word': 'your',        'start': 9.50, 'end': 9.65},
    {'word': 'insights',    'start': 9.67, 'end': 9.98},
]


def parse_args():
    p = argparse.ArgumentParser(description='Animation preview test')
    p.add_argument('--out', default='animation_preview.mp4')
    p.add_argument('--duration', type=float, default=10.5)
    p.add_argument('--fps', type=int, default=24)
    p.add_argument('--w', type=int, default=1080)
    p.add_argument('--h', type=int, default=1920)
    p.add_argument('--bg', default='dark', choices=['dark', 'blue', 'black'])
    return p.parse_args()


def main():
    args = parse_args()
    W, H = args.w, args.h
    DUR = args.duration

    print('=== NextGen Thoughts Animation Preview ===')
    print(f'  {W}x{H}  {DUR}s  {args.fps}fps  -> {args.out}')

    fd, ts = tempfile.mkstemp(suffix='.json', prefix='anim_test_')
    with os.fdopen(fd, 'w') as f:
        json.dump(W_WORDS, f)

    bg_map = {'dark': [12, 12, 20], 'blue': [5, 15, 40], 'black': [0, 0, 0]}
    bg = ColorClip(size=(W, H), color=bg_map[args.bg], duration=DUR)

    print('Building animated subtitle clips...')
    subs = create_dynamic_subtitles(ts, W, H, DUR, voice_offset=0.0)
    print(f'  {len(subs)} animated clips ready')

    final = CompositeVideoClip([bg] + subs)
    threads = max(2, multiprocessing.cpu_count())
    print(f'  Rendering on {threads} threads @ {args.fps}fps...')

    final.write_videofile(
        args.out, fps=args.fps, codec='libx264',
        audio=False, threads=threads, preset='ultrafast',
        ffmpeg_params=['-crf', '22'], logger='bar',
    )

    try:
        os.remove(ts)
    except Exception:
        pass

    size_mb = os.path.getsize(args.out) / 1024 / 1024
    print(f'  Saved: {args.out} ({size_mb:.1f} MB)')


if __name__ == '__main__':
    main()

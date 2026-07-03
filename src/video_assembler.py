from moviepy.editor import VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip, CompositeAudioClip
from moviepy.video.fx.all import loop
import textwrap

def create_video(video_path: str, voice_path: str, music_path: str, text: str, output_path="final_video.mp4"):
    print("Assembling video...")
    
    # Load clips
    bg_video = VideoFileClip(video_path)
    voice_audio = AudioFileClip(voice_path)
    
    try:
        music_audio = AudioFileClip(music_path)
    except Exception as e:
        print(f"Warning: Failed to load background music: {e}")
        music_audio = None
        
    # The final video length is determined by the voiceover duration + 1 second padding
    target_duration = voice_audio.duration + 1.0
    
    # Ensure background video is long enough
    if bg_video.duration < target_duration:
        # Loop background video
        bg_video = bg_video.loop(duration=target_duration)
    else:
        bg_video = bg_video.subclip(0, target_duration)
        
    # Process audio
    if music_audio:
        # Loop music if too short
        if music_audio.duration < target_duration:
            # We can use audio_loop, or since it's typically long enough, just handle if it's short
            from moviepy.audio.fx.all import audio_loop
            music_audio = audio_loop(music_audio, duration=target_duration)
        else:
            music_audio = music_audio.subclip(0, target_duration)
            
        # Lower music volume (ducking)
        music_audio = music_audio.volumex(0.15) # 15% volume
        
        # Combine voice and music. Start voice 0.5 seconds in.
        final_audio = CompositeAudioClip([music_audio, voice_audio.set_start(0.5)])
    else:
        final_audio = voice_audio.set_start(0.5)
        
    bg_video = bg_video.set_audio(final_audio)
    
    # Create text overlay
    # Wrap text to fit screen
    wrapped_text = "\n".join(textwrap.wrap(text, width=25))
    
    # MoviePy's TextClip requires ImageMagick to be installed.
    # If this fails, the user will need to install ImageMagick and configure MoviePy.
    txt_clip = TextClip(
        wrapped_text, 
        fontsize=70, 
        color='white', 
        font='Arial-Bold',
        stroke_color='black',
        stroke_width=2,
        align='center',
        size=(bg_video.w * 0.9, None), # 90% of screen width
        method='caption'
    )
    
    txt_clip = txt_clip.set_position('center').set_duration(target_duration)
    
    # Combine video and text
    final_video = CompositeVideoClip([bg_video, txt_clip])
    
    # Write result
    final_video.write_videofile(
        output_path,
        fps=30,
        codec="libx264",
        audio_codec="aac",
        threads=4,
        preset="ultrafast"
    )
    
    print(f"Video saved to {output_path}")
    return output_path

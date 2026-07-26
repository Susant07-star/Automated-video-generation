# Goal Description

The user wants to level up the video generation to match real professional editors. Specifically:
1. **Multiple B-Rolls**: Attach different video footages that match what Adam (the AI voice) is saying at that exact moment.
2. **Sound Effects (SFX)**: Add professional transitions (like whooshes or risers) when the video cuts to a new scene.

This is a significant architectural change that shifts the pipeline from a "single background video" to a "multi-clip timeline with synchronized audio and transition effects."

## User Review Required

> [!IMPORTANT]  
> **Generation Cost & Time:** Fetching 3-4 different videos per reel instead of 1 will increase the generation time by about 2-3 minutes per video (because it has to download and process 4 separate 4K/1080p videos). It will also consume your Pexels API rate limit faster (though Pexels has a generous limit). 

> [!TIP]
> **Audio Generation Approach:** To ensure the video cuts *exactly* when Adam finishes a sentence or thought, I plan to split the script into 3-4 "segments". I will generate the voiceover for each segment individually. This ensures perfect sync without having to do complex word-level timestamp math. Is this acceptable?

## Proposed Changes

### `src/content_generator.py`
- Modify the Gemini prompt and Pydantic schema to return an array of `ScriptSegment` objects instead of a single quote.
- Each segment will have:
  - `text`: The sentence Adam will speak.
  - `visual_keyword`: The specific Pexels search term for that sentence (e.g., "dark gym", "sunrise", "running").

### `src/media_fetcher.py`
- Update `download_pexels_video` to handle an array of keywords and return a list of downloaded video paths.
- Add a new function `download_pixabay_sfx()` to fetch transition sound effects (like a "whoosh" or "impact" sound) using Pixabay's `media_type=effects` endpoint.

### `src/audio_generator.py`
- Update the ElevenLabs function to accept a list of segments and generate an audio file for each segment (e.g., `segment_1.mp3`, `segment_2.mp3`).

### `src/video_assembler.py`
- [MODIFY] Major rewrite required to handle multi-clip timelines.
- For each segment:
  1. Load the corresponding video and audio.
  2. Set the video duration to exactly match the audio duration.
  3. Apply the Ken Burns zoom.
- Concatenate all segments together using Moviepy's `concatenate_videoclips`.
- Overlay the "Whoosh" SFX track precisely at the timestamp where each clip transitions.
- Apply the global background music and vignette.

## Verification Plan

### Manual Verification
- We will run `python main.py` and manually review the resulting `final_reel.mp4`. 
- Check that the video cuts exactly when the topic changes.
- Check that the transition sound effect plays exactly on the cut.

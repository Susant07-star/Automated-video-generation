import asyncio
import edge_tts

async def _generate_voiceover_async(text: str, output_filename: str):
    # 'en-US-ChristopherNeural' is a solid, deep male voice good for motivation.
    # Others: 'en-US-GuyNeural', 'en-GB-RyanNeural', 'en-US-SteffanNeural'
    voice = "en-US-ChristopherNeural"
    communicate = edge_tts.Communicate(text, voice, rate="+5%")
    await communicate.save(output_filename)

def generate_voiceover(text: str, output_filename="temp_voice.mp3"):
    """
    Generates a voiceover from text using edge-tts and saves it to a file.
    """
    print("Generating AI voiceover...")
    asyncio.run(_generate_voiceover_async(text, output_filename))
    return output_filename

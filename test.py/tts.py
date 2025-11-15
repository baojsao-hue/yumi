# tts.py
import os
import tempfile
from gtts import gTTS
import subprocess
import shutil

# Tự tìm ffmpeg trong PATH, nếu không thì dùng biến môi trường FFMPEG_PATH
def get_ffmpeg_path():
    custom_path = os.getenv("FFMPEG_PATH")
    if custom_path and os.path.exists(custom_path):
        return custom_path
    found = shutil.which("ffmpeg")
    if found:
        return found
    raise FileNotFoundError("❌ Không tìm thấy ffmpeg. Hãy cài ffmpeg hoặc set FFMPEG_PATH")

FFMPEG_PATH = get_ffmpeg_path()

def text_to_speech(text, filename="yumi_voice.wav", lang="vi"):
    try:
        tts = gTTS(text=text, lang=lang)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_mp3:
            mp3_path = tmp_mp3.name
            tts.save(mp3_path)

        # Convert sang WAV chuẩn cho Discord (16-bit PCM, 48kHz mono)
        subprocess.run(
            [FFMPEG_PATH, "-y", "-i", mp3_path, "-ac", "1", "-ar", "48000", "-acodec", "pcm_s16le", filename],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        os.remove(mp3_path)
        return filename
    except Exception as e:
        print(f"❌ Lỗi TTS: {e}")
        return None

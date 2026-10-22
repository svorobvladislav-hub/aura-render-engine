#!/usr/bin/env python3
import os
import sys
import json
import time
import urllib.parse
import subprocess
import requests
import asyncio
import edge_tts

PAYLOAD_STR = os.getenv("RENDER_PAYLOAD") or (sys.argv[1] if len(sys.argv) > 1 else "{}")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CALLBACK_URL = os.getenv("CALLBACK_URL")
INTERNAL_SECRET = os.getenv("INTERNAL_API_SECRET")

WORK_DIR = os.path.join(os.getcwd(), "temp_render")
os.makedirs(WORK_DIR, exist_ok=True)

VOICE_PROFILES = {
    "ru_blogger": {"engine_voice": "ru-RU-DmitryNeural", "rate": "+14%", "pitch": "+3Hz"},
    "ru_cinema":  {"engine_voice": "ru-RU-DmitryNeural", "rate": "-7%",  "pitch": "-5Hz"},
    "ru_doc":     {"engine_voice": "ru-RU-DmitryNeural", "rate": "+0%",  "pitch": "+0Hz"},
    "ru_mystery": {"engine_voice": "ru-RU-SvetlanaNeural", "rate": "-8%", "pitch": "-3Hz"},
    "en_blogger": {"engine_voice": "en-US-GuyNeural", "rate": "+12%", "pitch": "+2Hz"},
    "en_cinema":  {"engine_voice": "en-US-ChristopherNeural", "rate": "-6%", "pitch": "-4Hz"}
}

async def synthesize_edge_profile(text: str, profile_key: str, output_path: str):
    profile = VOICE_PROFILES.get(profile_key, VOICE_PROFILES["ru_blogger"])
    comm = edge_tts.Communicate(text, profile["engine_voice"], rate=profile["rate"], pitch=profile["pitch"])
    await comm.save(output_path)

def get_audio_duration(audio_path: str) -> float:
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", audio_path]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
    return float(res.stdout.strip())

def download_shot_image(prompt: str, index: int, aspect_ratio: str, output_path: str):
    w, h = (1280, 720) if aspect_ratio == "16:9" else (768, 1344)
    encoded = urllib.parse.quote(prompt.strip().replace("\n", " "))
    seed = int(time.time() * 1000) % 100000 + index
    url = f"https://image.pollinations.ai/prompt/{encoded}?width={w}&height={h}&nologo=true&seed={seed}&model=flux"
    for _ in range(3):
        try:
            r = requests.get(url, timeout=30)
            if r.status_code == 200 and len(r.content) > 5000:
                with open(output_path, "wb") as f:
                    f.write(r.content)
                return
        except Exception:
            time.sleep(2)
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=0x0f0f17:s={w}x{h}:d=1", "-vframes", "1", output_path])

def format_ass_time(seconds: float) -> str:
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centis = int(round((seconds - int(seconds)) * 100))
    return f"{hrs:d}:{mins:02d}:{secs:02d}.{centis:02d}"

def generate_subtitles_ass(shots: list, shot_duration: float, output_path: str, width: int, height: int):
    font_size = 40 if width < 1000 else 54
    margin_v = int(height * 0.22)
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: MrBeast,Liberation Sans,{font_size},&H0000FFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,2,0,1,5,3,2,25,25,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    cur = 0.0
    for s in shots:
        txt = (s.get("text_ru") or "").strip().upper()
        if txt:
            events.append(f"Dialogue: 0,{format_ass_time(cur)},{format_ass_time(cur + shot_duration)},MrBeast,,0,0,0,,{txt}")
        cur += shot_duration
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(header + "\n".join(events))

def assemble_video_ffmpeg(image_paths: list, audio_path: str, ass_path: str, output_path: str, total_duration: float, aspect_ratio: str, is_watermark: bool):
    w, h = (1280, 720) if aspect_ratio == "16:9" else (720, 1280)
    shot_dur = total_duration / len(image_paths)
    fps = 25
    frames = int(shot_dur * fps)
    clips = []
    for i, img in enumerate(image_paths):
        cp = os.path.join(WORK_DIR, f"clip_{i}.mp4")
        zf = f"scale=8000:-1,zoompan=z='min(zoom+0.0015,1.25)':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={w}x{h},fps={fps}"
        subprocess.run(["ffmpeg", "-y", "-loop", "1", "-i", img, "-vf", zf, "-t", str(shot_dur), "-c:v", "libx264", "-pix_fmt", "yuv420p", cp], check=True)
        clips.append(cp)

    concat_txt = os.path.join(WORK_DIR, "concat.txt")
    with open(concat_txt, "w") as f:
        for c in clips:
            f.write(f"file '{c}'\n")

    ass_esc = ass_path.replace("\\", "/").replace(":", "\\:")
    vf = f"subtitles='{ass_esc}'"
    if is_watermark:
        vf += ",drawtext=text='@AuraStudioProBot':fontsize=26:fontcolor=white@0.6:box=1:boxcolor=black@0.4:boxborderw=4:x=w-tw-24:y=h-th-36"

    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_txt, "-i", audio_path,
        "-vf", vf, "-c:v", "libx264", "-preset", "fast", "-crf", "22", "-c:a", "aac", "-b:a", "192k",
        "-shortest", "-movflags", "+faststart", output_path
    ], check=True)

def main():
    data = json.loads(PAYLOAD_STR)
    render_id = data.get("render_id", f"rnd_{int(time.time())}")
    chat_id = data.get("chat_id")
    title = data.get("title", "AURA AI Video")
    voiceover = data.get("voiceover", "")
    shots = data.get("shots", [])
    voice = data.get("voice", "ru_blogger")
    aspect_ratio = data.get("aspect_ratio", "9:16")
    is_watermark = bool(data.get("is_watermark", True))
    target_bot = data.get("target_bot", "public")

    try:
        audio_file = os.path.join(WORK_DIR, "voiceover.mp3")
        asyncio.run(synthesize_edge_profile(voiceover, voice, audio_file))
        duration = get_audio_duration(audio_file)

        image_paths = []
        for i, shot in enumerate(shots):
            p = os.path.join(WORK_DIR, f"shot_{i}.jpg")
            download_shot_image(shot.get("prompt_en", "Cinematic 8k"), i + 1, aspect_ratio, p)
            image_paths.append(p)

        ass_file = os.path.join(WORK_DIR, "subs.ass")
        w, h = (720, 1280) if aspect_ratio == "9:16" else (1280, 720)
        generate_subtitles_ass(shots, duration / len(image_paths), ass_file, w, h)

        final_mp4 = os.path.join(WORK_DIR, f"{render_id}.mp4")
        assemble_video_ffmpeg(image_paths, audio_file, ass_file, final_mp4, duration, aspect_ratio, is_watermark)

        with open(final_mp4, "rb") as vf:
            requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendVideo",
                files={"video": vf},
                data={"chat_id": chat_id, "caption": f"🎬 **{title}**\n✨ Создано в @AuraStudioProBot", "supports_streaming": True, "parse_mode": "Markdown"},
                timeout=180
            )

        if CALLBACK_URL:
            requests.post(f"{CALLBACK_URL.rstrip('/')}/internal/render-status", json={"render_id": render_id, "status": "completed", "target_bot": target_bot}, headers={"Authorization": f"Bearer {INTERNAL_SECRET}"})
    except Exception as err:
        if CALLBACK_URL:
            requests.post(f"{CALLBACK_URL.rstrip('/')}/internal/render-status", json={"render_id": render_id, "status": "failed", "error_message": str(err), "target_bot": target_bot}, headers={"Authorization": f"Bearer {INTERNAL_SECRET}"})
        sys.exit(1)

if __name__ == "__main__":
    main()

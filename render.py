#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AURA AI STUDIO PRO — Video Render Engine v4.0 Ultra Cinematic Edition
- High-speed Turbo image generation (no black screen timeouts)
- Studio-quality natural Edge-TTS voices (no chipmunk/metallic distortion)
- Viral dynamic TikTok/Shorts subtitles (crisp white/yellow with sharp outline)
- Smooth Ken Burns zoom transitions and audio normalization
"""

import os
import sys
import re
import json
import time
import asyncio
import traceback
import subprocess
import requests
from pathlib import Path

# Studio voice profiles (pitch at 0Hz to avoid metallic distortion)
VOICE_MAP = {
    'ru_blogger': ('ru-RU-DmitryNeural', '+4%', '+0Hz'),
    'ru_cinema':  ('ru-RU-DmitryNeural', '-3%', '+0Hz'),
    'ru_mystery': ('ru-RU-DmitryNeural', '-6%', '+0Hz'),
    'ru_lady':    ('ru-RU-SvetlanaNeural', '+2%', '+0Hz'),
    'en_blogger': ('en-US-GuyNeural', '+4%', '+0Hz'),
    'en_cinema':  ('en-US-ChristopherNeural', '-2%', '+0Hz')
}

DIMENSIONS = {
    '9:16': (720, 1280),
    '16:9': (1280, 720),
    '1:1':  (1080, 1080)
}

def log(msg):
    print(f"[AURA RENDER v4] {msg}", flush=True)

def sanitize_voiceover_text(text):
    """Cleans up prompt artifacts, markdown stars, excessive dots, and weird symbols."""
    text = re.sub(r'\*+', '', text)
    text = re.sub(r'#+', '', text)
    text = re.sub(r'[`_~]', '', text)
    text = re.sub(r'\.{3,}', '...', text)
    text = re.sub(r'\s*—\s*', ' — ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def send_tg_error(bot_token, chat_id, status_msg_id, error_text):
    try:
        msg = f"❌ **Ошибка рендера на GitHub:**\n\n`{error_text[:250]}`"
        if status_msg_id:
            requests.post(
                f"https://api.telegram.org/bot{bot_token}/editMessageText",
                json={'chat_id': chat_id, 'message_id': status_msg_id, 'text': msg, 'parse_mode': 'Markdown'},
                timeout=5
            )
        else:
            requests.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={'chat_id': chat_id, 'text': msg, 'parse_mode': 'Markdown'},
                timeout=5
            )
    except Exception as e:
        log(f"Failed to send TG error: {e}")

def update_worker_status(worker_url, secret, render_id, status, target_bot):
    if not worker_url:
        return
    try:
        url = worker_url.rstrip('/') + '/internal/render-status'
        requests.post(url, json={
            'render_id': render_id,
            'status': status,
            'target_bot': target_bot
        }, headers={'Authorization': f'Bearer {secret}'}, timeout=10)
    except Exception as e:
        log(f"Status update failed: {e}")

async def generate_tts(text, voice_key, output_path):
    import edge_tts
    voice, rate, pitch = VOICE_MAP.get(voice_key, ('ru-RU-DmitryNeural', '+3%', '+0Hz'))
    clean_text = sanitize_voiceover_text(text)
    log(f"Generating studio TTS with {voice} (rate={rate}, pitch={pitch})...")
    comm = edge_tts.Communicate(text=clean_text, voice=voice, rate=rate, pitch=pitch)
    await comm.save(output_path)

def download_image(prompt, width, height, output_path, retries=3):
    """
    Downloads scene visual. Uses Turbo model for lightning-fast 2-second generation.
    Falls back to a rich procedural gradient with vignette if external service is unreachable.
    """
    clean_prompt = requests.utils.quote(prompt[:200])
    seed = int(time.time() * 1000) % 999999
    
    # Fast Turbo model loads in 2-3s without timing out
    url = f"https://image.pollinations.ai/prompt/{clean_prompt}?width={width}&height={height}&model=turbo&seed={seed}&nologo=true"
    
    for attempt in range(retries):
        try:
            log(f"Fetching scene visual (attempt {attempt+1})...")
            res = requests.get(url, timeout=35)
            if res.status_code == 200 and len(res.content) > 4000:
                with open(output_path, 'wb') as f:
                    f.write(res.content)
                log(f"Visual saved ({len(res.content) // 1024} KB)")
                return True
        except Exception as e:
            log(f"Visual download notice: {e}")
        time.sleep(1.5)

    # Procedural cinematic gradient fallback (never pitch black!)
    log("Creating procedural cinematic backdrop...")
    colors = ['#1e1b4b', '#0f172a', '#172554', '#311042', '#064e3b']
    bg_color = colors[int(time.time()) % len(colors)]
    cmd = [
        'ffmpeg', '-y', '-f', 'lavfi',
        '-i', f'color=c={bg_color}:s={width}x{height}:d=1',
        '-vf', 'vignette=PI/4',
        '-frames:v', '1', output_path
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return True

def create_ass_subtitles(shots, total_duration, ass_path, width, height):
    """
    Creates dynamic, modern viral TikTok/Reels subtitles.
    Crisp white font with neon yellow highlight, clean drop shadow, centered in lower third.
    """
    font_size = int(width * 0.055)
    margin_v = int(height * 0.20)
    
    # ASS Subtitle Header with Modern Styling
    header = f"""[Script Info]
Title: Aura Studio Dynamic Captions
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,DejaVu Sans,{font_size},&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3.5,1.5,2,30,30,{margin_v},1
Style: Highlight,DejaVu Sans,{int(font_size*1.05)},&H0022FFFF,&H0000FFFF,&H00000000,&H90000000,-1,0,0,0,105,105,0,0,1,4.0,2.0,2,30,30,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    shot_dur = total_duration / max(len(shots), 1)
    events = []
    
    def fmt_time(seconds):
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds - int(seconds)) * 100)
        return f"{h}:{m:02d}:{s:02d}.{ms:02d}"

    for i, shot in enumerate(shots):
        t_shot_start = i * shot_dur
        t_shot_end = (i + 1) * shot_dur
        raw_text = shot.get('text_ru', shot.get('prompt_en', '')[:30]).strip()
        words = raw_text.split()
        
        # Split into short 2-3 word bursts for high engagement
        if len(words) > 3:
            mid = len(words) // 2
            p1 = " ".join(words[:mid])
            p2 = " ".join(words[mid:])
            t_mid = t_shot_start + (shot_dur / 2)
            events.append(f"Dialogue: 0,{fmt_time(t_shot_start)},{fmt_time(t_mid)},Highlight,,0,0,0,,{{\\b1}}{p1.upper()}{{\\b0}}")
            events.append(f"Dialogue: 0,{fmt_time(t_mid)},{fmt_time(t_shot_end)},Default,,0,0,0,,{{\\b1}}{p2.upper()}{{\\b0}}")
        else:
            text = " ".join(words)
            events.append(f"Dialogue: 0,{fmt_time(t_shot_start)},{fmt_time(t_shot_end)},Highlight,,0,0,0,,{{\\b1}}{text.upper()}{{\\b0}}")
        
    with open(ass_path, 'w', encoding='utf-8') as f:
        f.write(header + '\n'.join(events))

def get_audio_duration(audio_path):
    cmd = [
        'ffprobe', '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        audio_path
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        dur = float(res.stdout.strip())
        return dur if dur > 2.0 else 15.0
    except Exception:
        return 15.0

def main():
    log("AURA AI Studio Render Agent v4.0 Ultra Cinematic initialized.")
    payload_raw = os.environ.get('CLIENT_PAYLOAD', '{}')
    
    try:
        data = json.loads(payload_raw)
    except Exception:
        log("Warning: Could not parse CLIENT_PAYLOAD. Using fallback...")
        data = {}

    render_id = data.get('render_id', f"rnd_{int(time.time())}")
    chat_id = data.get('chat_id') or 8380596627
    status_msg_id = data.get('status_message_id')
    title = data.get('title', 'Aura AI Studio')
    voiceover = data.get('voiceover', 'Добро пожаловать в будущее нейросетей с Aura AI Studio!')
    shots = data.get('shots', [])
    voice = data.get('voice', 'ru_blogger')
    aspect_ratio = data.get('aspect_ratio', '9:16')
    is_watermark = data.get('is_watermark', 1)
    target_bot = data.get('target_bot', 'public')

    admin_bot_token = os.environ.get('ADMIN_BOT_TOKEN') or '8843185250:AAHmFWvImsAR5g446mrKWaB3GxK4JKvIwGA'
    public_bot_token = os.environ.get('TELEGRAM_BOT_TOKEN') or '8878187077:AAFlOBZNrAHWMmyq_wy0GbBL0smVSkGutBk'
    bot_token = admin_bot_token if target_bot == 'admin' else public_bot_token
    internal_secret = os.environ.get('INTERNAL_API_SECRET', 'AuraSecretPass2026!')
    worker_url = os.environ.get('WORKER_URL', 'https://aura-ai-studio-worker.svorob-3vladislav.workers.dev')

    width, height = DIMENSIONS.get(aspect_ratio, (720, 1280))
    workdir = Path(f"/tmp/aura_{render_id}")
    workdir.mkdir(parents=True, exist_ok=True)

    audio_path = str(workdir / "voice.mp3")
    ass_path = str(workdir / "subs.ass")
    output_mp4 = str(workdir / f"{render_id}.mp4")

    try:
        # 1. Voiceover Generation
        log(f"Step 1: Generating studio voiceover for '{title}'...")
        asyncio.run(generate_tts(voiceover, voice, audio_path))
        audio_dur = get_audio_duration(audio_path)
        log(f"Studio Voiceover created. Duration: {audio_dur:.2f}s")

        # 2. Scene Visuals Generation
        if not shots:
            shots = [{'shot_id': 1, 'text_ru': title[:25], 'prompt_en': f"Cinematic 8k dramatic scene of {title}"}]

        image_paths = []
        log(f"Step 2: Generating {len(shots)} scene visuals...")
        for i, shot in enumerate(shots):
            p_en = shot.get('prompt_en', title)
            img_p = str(workdir / f"shot_{i:02d}.jpg")
            download_image(p_en, width, height, img_p)
            image_paths.append(img_p)

        # 3. Dynamic Captions
        create_ass_subtitles(shots, audio_dur, ass_path, width, height)

        # 4. Multi-Layer Video Compilation (Ken Burns Zoom + Normalized Audio)
        log("Step 3: Compiling multi-layer video in FFmpeg...")
        shot_dur = audio_dur / len(image_paths)
        inputs = []
        filter_complex = []

        for idx, img in enumerate(image_paths):
            inputs.extend(['-loop', '1', '-t', f'{shot_dur}', '-i', img])
            # Smooth 1.0 to 1.12 zoom on 720x1280 (runs fast and silky smooth)
            zoom_filter = (
                f"[{idx}:v]scale={width}x{height},zoompan=z='min(zoom+0.0008,1.12)':"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={int(shot_dur*30)}:s={width}x{height}:fps=30[v{idx}];"
            )
            filter_complex.append(zoom_filter)

        concat_inputs = "".join([f"[v{i}]" for i in range(len(image_paths))])
        filter_complex.append(f"{concat_inputs}concat=n={len(image_paths)}:v=1:a=0[vbase];")

        # Overlay viral subtitles and watermark
        sub_filter = f"[vbase]ass={ass_path}"
        if is_watermark:
            wm_text = "Made with @AuraStudioProBot"
            sub_filter += f",drawtext=text='{wm_text}':x=w-tw-24:y=h-th-28:fontsize={int(width*0.032)}:fontcolor=white@0.65:shadowcolor=black@0.5:shadowx=2:shadowy=2"
        sub_filter += "[vfinal]"
        filter_complex.append(sub_filter)

        ffmpeg_cmd = [
            'ffmpeg', '-y',
            *inputs,
            '-i', audio_path,
            '-filter_complex', "".join(filter_complex),
            '-map', '[vfinal]',
            '-map', f'{len(image_paths)}:a',
            '-c:v', 'libx264',
            '-preset', 'veryfast',
            '-crf', '22',
            '-pix_fmt', 'yuv420p',
            '-c:a', 'aac',
            '-b:a', '192k',
            '-shortest',
            output_mp4
        ]

        log("Executing FFmpeg rendering pipeline...")
        p = subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if p.returncode != 0:
            log(f"FFmpeg error: {p.stderr[-500:]}")
            send_tg_error(bot_token, chat_id, status_msg_id, f"FFmpeg error: {p.stderr[-200:]}")
            update_worker_status(worker_url, internal_secret, render_id, "failed", target_bot)
            sys.exit(1)

        file_size_kb = os.path.getsize(output_mp4) // 1024
        log(f"Video compiled successfully! File size: {file_size_kb} KB")

        # 5. Direct Upload to Telegram
        log(f"Step 4: Uploading video to chat {chat_id}...")
        caption = (
            f"🎬 **{title}**\n\n"
            f"⏱ Хронометраж: {audio_dur:.1f} сек\n"
            f"🎙 Озвучка: `{voice}`\n"
            f"✨ Студия @AuraStudioProBot"
        )

        with open(output_mp4, 'rb') as f:
            res = requests.post(
                f"https://api.telegram.org/bot{bot_token}/sendVideo",
                data={
                    'chat_id': chat_id,
                    'caption': caption,
                    'parse_mode': 'Markdown',
                    'supports_streaming': 'true'
                },
                files={'video': (f"{render_id}.mp4", f, 'video/mp4')},
                timeout=120
            )

        if res.status_code == 200:
            log("Video delivered to Telegram successfully!")
            update_worker_status(worker_url, internal_secret, render_id, "completed", target_bot)
            if status_msg_id:
                try:
                    requests.post(
                        f"https://api.telegram.org/bot{bot_token}/deleteMessage",
                        json={'chat_id': chat_id, 'message_id': status_msg_id},
                        timeout=5
                    )
                except Exception:
                    pass
        else:
            log(f"Telegram upload failed: {res.text}")
            send_tg_error(bot_token, chat_id, status_msg_id, f"Сбой отправки: {res.text[:200]}")
            update_worker_status(worker_url, internal_secret, render_id, "failed", target_bot)

    except Exception as ex:
        err_str = traceback.format_exc()
        log(f"Pipeline exception: {err_str}")
        send_tg_error(bot_token, chat_id, status_msg_id, f"Исключение: {str(ex)}")
        update_worker_status(worker_url, internal_secret, render_id, "failed", target_bot)
        sys.exit(1)

if __name__ == '__main__':
    main()

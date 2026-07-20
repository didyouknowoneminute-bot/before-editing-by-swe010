import streamlit as st
import os
import subprocess
import math
import concurrent.futures
import asyncio
import edge_tts
import time
import shutil
import gc
import threading


# ─────────────────────────────────────────────
# Timer Utility
# ─────────────────────────────────────────────

def format_time(seconds):
    """Format seconds into mm:ss or mm:ss.ms format."""
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    ms = int((seconds % 1) * 10)
    if mins > 0:
        return f"{mins}:{secs:02d}"
    return f"{secs}.{ms}s"


# ─────────────────────────────────────────────
# Real-time Timer Thread
# ─────────────────────────────────────────────

class LiveTimer:
    """Background timer that updates a Streamlit placeholder in real-time."""

    def __init__(self, placeholder, total_placeholder=None):
        self._stop_event = threading.Event()
        self._start_time = 0
        self._placeholder = placeholder
        self._total_placeholder = total_placeholder
        self._thread = None

    def start(self):
        self._start_time = time.time()
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)

    def elapsed(self):
        return time.time() - self._start_time

    def _run(self):
        while not self._stop_event.is_set():
            elapsed = time.time() - self._start_time
            self._placeholder.markdown(f"⏱️ **Elapsed: {format_time(elapsed)}**")
            self._stop_event.wait(1.0)


# ─────────────────────────────────────────────
# TTS Voices, Recap Styles, and Emotions
# ─────────────────────────────────────────────

@st.cache_resource
def get_voices():
    return [
        {"id": "v1", "name": "V1 ♂", "gender": "Male"},
        {"id": "v2", "name": "V2 ♀", "gender": "Female"},
        {"id": "v3", "name": "V3 ♂", "gender": "Male"},
        {"id": "v4", "name": "V4 ♂", "gender": "Male"},
        {"id": "v5", "name": "V5 ♂", "gender": "Male"},
        {"id": "v6", "name": "V6 ♀", "gender": "Female"},
        {"id": "v7", "name": "V7 ♂", "gender": "Male"},
        {"id": "v8", "name": "V8 ♀", "gender": "Female"},
        {"id": "v9", "name": "V9 ♂", "gender": "Male"},
        {"id": "v10", "name": "V10 ♀", "gender": "Female"},
        {"id": "v11", "name": "V11 ♀", "gender": "Female"},
        {"id": "v12", "name": "V12 ♂", "gender": "Male"},
        {"id": "v13", "name": "V13 ♀", "gender": "Female"},
        {"id": "v14", "name": "V14 ♂", "gender": "Male"}
    ]

@st.cache_resource
def get_recap_styles():
    return [
        {"id": "Normal", "name": "ပုံမှန်အသံ", "speed": 0, "pitch": 0},
        {"id": "NyoGyi_25", "name": "ကျားကြီး ၁", "speed": 0, "pitch": 25},
        {"id": "NyoGyi_35", "name": "ကျားကြီး ၂", "speed": 0, "pitch": 35},
        {"id": "NyoGyi_45", "name": "ကျားကြီး ၃", "speed": 0, "pitch": 45},
        {"id": "Nilar_40", "name": "နီလာ ချွဲသံ", "speed": 0, "pitch": 40},
        {"id": "Combo_15", "name": "ပေါင်းစပ် ၁၅", "speed": 15, "pitch": 15},
        {"id": "Combo_30", "name": "ပေါင်းစပ် ၃၀", "speed": 30, "pitch": 30},
        {"id": "Combo_50", "name": "ပေါင်းစပ် ၅၀", "speed": 50, "pitch": 50},
        {"id": "Pitch_20", "name": "အသံသေး ၂၀", "speed": 0, "pitch": 20},
        {"id": "Pitch_50", "name": "အသံသေး ၅၀", "speed": 0, "pitch": 50}
    ]

@st.cache_resource
def get_emotions():
    return [
        {"id": "EXCITING", "name": "စိတ်လှုပ်ရှား 🤩", "s": 15, "p": 10},
        {"id": "CALM", "name": "တည်ငြိမ် 😌", "s": -10, "p": -5},
        {"id": "PROFESSIONAL", "name": "သတင်း 💼", "s": 0, "p": -2},
        {"id": "NARRATIVE", "name": "ဇာတ်ကြောင်း 📖", "s": -5, "p": 0},
        {"id": "HAPPY", "name": "ပျော်ရွှင် 😊", "s": 10, "p": 15},
        {"id": "SERIOUS", "name": "လေးနက် 😠", "s": -5, "p": -10},
        {"id": "WHISPER", "name": "တီးတိုး 🤫", "s": -15, "p": -20},
        {"id": "SAD", "name": "ဝမ်းနည်း 😢", "s": -15, "p": -15},
        {"id": "SARCASTIC", "name": "ရွဲ့ပြော 🙄", "s": -10, "p": 5},
        {"id": "ANGRY", "name": "ဒေါသထွက် 🤬", "s": 20, "p": -10},
        {"id": "FEAR", "name": "ကြောက်လန့် 😨", "s": 10, "p": 20}
    ]

VOICES = get_voices()
RECAP_STYLES = get_recap_styles()
EMOTIONS = get_emotions()

st.set_page_config(page_title="Video & Text Processor", layout="wide")


def count_paragraphs(text):
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    return paragraphs


# ─────────────────────────────────────────────
# TTS Generation
# ─────────────────────────────────────────────

async def generate_all_tts(paragraphs, audio_dir, voice_id, speed, pitch):
    """Generate TTS for all paragraphs in parallel."""
    tasks = []
    for i, paragraph in enumerate(paragraphs):
        tasks.append(generate_tts_async(paragraph, os.path.join(audio_dir, f"audio_{i}.mp3"), voice_id, speed, pitch))
    await asyncio.gather(*tasks)


VOICE_MAP = {
    "v1": "my-MM-ThihaNeural",
    "v2": "my-MM-NilarNeural",
    "v3": "it-IT-GianniNeural",
    "v4": "en-AU-WilliamMultilingualNeural",
    "v5": "en-US-AndrewMultilingualNeural",
    "v6": "en-US-AvaMultilingualNeural",
    "v7": "en-US-BrianMultilingualNeural",
    "v8": "en-US-EmmaMultilingualNeural",
    "v9": "fr-FR-RemyMultilingualNeural",
    "v10": "fr-FR-VivienneMultilingualNeural",
    "v11": "de-DE-SeraphinaMultilingualNeural",
    "v12": "de-DE-FlorianMultilingualNeural",
    "v13": "pt-BR-ThalitaMultilingualNeural",
    "v14": "ko-KR-HyunsuMultilingualNeural"
}

async def generate_tts_async(text, output_path, voice_id, speed, pitch):
    """Async TTS generation for parallel execution."""
    real_voice = VOICE_MAP.get(voice_id, "my-MM-ThihaNeural")
    rate_str = f"+{speed}%" if speed >= 0 else f"{speed}%"
    pitch_str = f"+{pitch}Hz" if pitch >= 0 else f"{pitch}Hz"
    communicate = edge_tts.Communicate(text, real_voice, rate=rate_str, pitch=pitch_str)
    await communicate.save(output_path)
    return output_path


# ─────────────────────────────────────────────
# Probe Helpers
# ─────────────────────────────────────────────

def get_video_duration(video_path):
    cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
           '-of', 'default=noprint_wrappers=1:nokey=1', video_path]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return float(result.stdout.strip())


def get_video_resolution(video_path):
    cmd = ['ffprobe', '-v', 'error', '-select_streams', 'v:0',
           '-show_entries', 'stream=width,height', '-of', 'csv=s=x:p=0', video_path]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    res = result.stdout.strip().split('x')
    w, h = int(res[0]), int(res[1])
    if w > 1920:
        h = int(h * (1920 / w))
        w = 1920
    return w, h


def get_audio_duration(audio_path):
    cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
           '-of', 'default=noprint_wrappers=1:nokey=1', audio_path]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return float(result.stdout.strip())


# ─────────────────────────────────────────────
# Step 1: Split video into segments (video only, no audio)
# ─────────────────────────────────────────────

def split_video(video_path, num_segments, output_dir):
    """Split video into segments using fast copy (instant, no re-encoding).
    Audio is stripped to avoid conflicts."""
    duration = get_video_duration(video_path)
    segment_duration = duration / num_segments
    segments = []
    for i in range(num_segments):
        start_time = i * segment_duration
        output_path = os.path.join(output_dir, f"segment_{i}.mp4")
        cmd = ['ffmpeg', '-y', '-ss', str(start_time), '-t', str(segment_duration),
               '-i', video_path, '-c:v', 'copy', '-an',
               '-avoid_negative_ts', 'make_zero', output_path]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        segments.append(output_path)
    return segments, segment_duration


# ─────────────────────────────────────────────
# Step 2: Speed-adjust each segment to match TTS audio
# ─────────────────────────────────────────────

def speed_adjust_segment(index, video_segment, audio_path, adjusted_dir):
    """Speed-adjust VIDEO ONLY to match TTS audio duration.
    TTS audio is kept at original speed (no atempo).
    Returns the path to the adjusted segment (video+audio combined).
    Cleans up the original segment after success."""
    audio_duration = get_audio_duration(audio_path)
    orig_duration = get_video_duration(video_segment)
    output_path = os.path.join(adjusted_dir, f"adjusted_{index}.mp4")

    if abs(audio_duration - orig_duration) < 0.5:
        # No speed adjustment needed, just copy video+audio
        cmd = ['ffmpeg', '-y', '-i', video_segment,
               '-i', audio_path, '-c:v', 'copy', '-c:a', 'copy',
               '-shortest', output_path]
    else:
        speed_factor = audio_duration / orig_duration
        filter_complex = f"[0:v]setpts=PTS*{speed_factor}[v_speed];[v_speed][1:a]concat=n=1:v=1:a=1[v_concat][a_concat]"

        cmd = ['ffmpeg', '-y', '-i', video_segment, '-i', audio_path,
               '-filter_complex', filter_complex, '-map', '[v_concat]', '-map', '[a_concat]',
               '-c:v', 'libx264', '-preset', 'ultrafast', '-c:a', 'aac',
               output_path]

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode == 0 and os.path.exists(output_path):
        if os.path.exists(video_segment):
            os.remove(video_segment)
        return output_path
    else:
        raise Exception(f"Speed adjust failed for segment {index}: {result.stderr}")


# ─────────────────────────────────────────────
# Step 3: Merge all speed-adjusted segments
# ─────────────────────────────────────────────

def merge_speed_adjusted_segments(adjusted_segments, output_path):
    """Merge all speed-adjusted segments into a single video."""
    concat_file = output_path + "_concat.txt"
    with open(concat_file, 'w') as f:
        for seg in adjusted_segments:
            f.write(f"file '{os.path.abspath(seg)}'\n")
    cmd = ['ffmpeg', '-y', '-f', 'concat', '-safe', '0',
           '-i', concat_file, '-c', 'copy', output_path]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if os.path.exists(concat_file):
        os.remove(concat_file)
    if result.returncode != 0:
        raise Exception(f"Merge speed-adjusted segments failed: {result.stderr}")
    for seg in adjusted_segments:
        if os.path.exists(seg):
            os.remove(seg)


# ─────────────────────────────────────────────
# Step 4: Split one chunk (for pipeline)
# ─────────────────────────────────────────────

def split_single_chunk(index, merged_path, chunk_duration, total_duration, output_dir):
    """Split a single chunk from merged video using fast copy (instant)."""
    start_time = index * chunk_duration
    remaining = min(chunk_duration, total_duration - start_time)
    output_path = os.path.join(output_dir, f"chunk_{index}.mp4")
    cmd = ['ffmpeg', '-y', '-ss', str(start_time), '-t', str(remaining),
           '-i', merged_path, '-c:v', 'copy', '-c:a', 'copy',
           '-avoid_negative_ts', 'make_zero', output_path]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return output_path, remaining


# ─────────────────────────────────────────────
# Step 5: Apply cycle repeat to a single chunk
# ─────────────────────────────────────────────

def build_cycle_filter(video_path, audio_path, chunk_duration,
                       play_dur, freeze1_dur, freeze2_dur,
                       freeze1_zoom, freeze2_zoom, zoom_dur):
    """Build FFmpeg filter complex for cycle repeat on a chunk."""
    width, height = get_video_resolution(video_path)
    fps = 24
    cycle_duration = play_dur + freeze1_dur + freeze2_dur
    num_cycles = math.ceil(chunk_duration / cycle_duration)

    # Force 720p for performance and RAM safety
    width, height = 1280, 720
    res_str = "1280x720"

    zoom_frames = max(int(zoom_dur * fps), 1)

    def make_zoom_filter(duration_frames, zoom_type):
        if zoom_type == "Zoom In":
            return (f"scale={width}:{height},setsar=1,"
                    f"zoompan=z='min(1+0.15*on/{duration_frames},1.15)':"
                    f"d={duration_frames}:s={res_str}:fps={fps}")
        elif zoom_type == "Zoom Out":
            return (f"scale={width}:{height},setsar=1,"
                    f"zoompan=z='max(1.15-0.15*on/{duration_frames},1.0)':"
                    f"d={duration_frames}:s={res_str}:fps={fps}")
        return None

    f1_z = make_zoom_filter(zoom_frames, freeze1_zoom) if freeze1_zoom != "None" else None
    f2_z = make_zoom_filter(zoom_frames, freeze2_zoom) if freeze2_zoom != "None" else None

    filter_parts = []
    concat_inputs = []

    for i in range(num_cycles):
        curr = i * cycle_duration

        # Play section
        filter_parts.append(
            f"[0:v]trim=start={curr}:end={min(curr + play_dur, chunk_duration)},"
            f"setpts=PTS-STARTPTS[vplay_{i}];")
        concat_inputs.append(f"[vplay_{i}]")

        # Freeze 1
        f1_start = curr + play_dur
        if f1_start < chunk_duration:
            if f1_z:
                filter_parts.append(
                    f"[0:v]trim=start={f1_start},select=eq(n\\,0),"
                    f"setpts=PTS-STARTPTS,{f1_z}[vf1_{i}];")
            else:
                filter_parts.append(
                    f"[0:v]trim=start={f1_start},select=eq(n\\,0),"
                    f"setpts=PTS-STARTPTS,loop=loop=-1:size=1:start=0,"
                    f"trim=duration={freeze1_dur}[vf1_{i}];")
            concat_inputs.append(f"[vf1_{i}]")

        # Freeze 2
        f2_start = curr + play_dur + freeze1_dur
        if f2_start < chunk_duration:
            if f2_z:
                filter_parts.append(
                    f"[0:v]trim=start={f2_start},select=eq(n\\,0),"
                    f"setpts=PTS-STARTPTS,{f2_z}[vf2_{i}];")
            else:
                filter_parts.append(
                    f"[0:v]trim=start={f2_start},select=eq(n\\,0),"
                    f"setpts=PTS-STARTPTS,loop=loop=-1:size=1:start=0,"
                    f"trim=duration={freeze2_dur}[vf2_{i}];")
            concat_inputs.append(f"[vf2_{i}]")

    # Concatenate video parts, then combine with audio
    filter_parts.append(
        f"{''.join(concat_inputs)}concat=n={len(concat_inputs)}:v=1:a=0[vcomb];")
    filter_parts.append(
        f"[vcomb][1:a]concat=n=1:v=1:a=1,trim=duration={chunk_duration}[v]")

    return ''.join(filter_parts)


def process_chunk_with_retry(index, chunk_path, chunk_duration,
                             final_dir,
                             play_dur, freeze1_dur, freeze2_dur,
                             freeze1_zoom, freeze2_zoom, zoom_dur,
                             max_retries=3):
    """Process a single chunk with cycle repeat and zoom effects."""
    audio_path = os.path.join(final_dir, f"chunk_audio_{index}.mp3")
    cmd = ['ffmpeg', '-y', '-i', chunk_path, '-vn', '-acodec', 'libmp3lame',
           '-ab', '128k', audio_path]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    for attempt in range(max_retries):
        try:
            output_path = os.path.join(final_dir, f"chunk_processed_{index}.mp4")
            filter_complex = build_cycle_filter(
                chunk_path, audio_path, chunk_duration,
                play_dur, freeze1_dur, freeze2_dur,
                freeze1_zoom, freeze2_zoom, zoom_dur
            )

            cmd = ['ffmpeg', '-y', '-i', chunk_path, '-i', audio_path,
                   '-filter_complex', filter_complex, '-map', '[v]',
                   '-c:v', 'libx264', '-preset', 'ultrafast', '-c:a', 'aac',
                   '-r', '24', '-s', '1280x720', '-shortest', output_path]
            result = subprocess.run(cmd, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, text=True)

            if result.returncode == 0 and os.path.exists(output_path):
                if os.path.exists(chunk_path):
                    os.remove(chunk_path)
                if os.path.exists(audio_path):
                    os.remove(audio_path)
                return output_path
            else:
                raise Exception(f"FFmpeg failed: {result.stderr}")
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            else:
                raise e


# ─────────────────────────────────────────────
# Step 6: Merge all processed chunks into final video
# ─────────────────────────────────────────────

def merge_videos(video_list, output_path):
    valid_videos = [v for v in video_list if v is not None and os.path.exists(v)]
    if not valid_videos:
        raise Exception("No valid segments to merge.")
    concat_file = "concat_list.txt"
    with open(concat_file, 'w') as f:
        for video in valid_videos:
            f.write(f"file '{os.path.abspath(video)}'\n")
    cmd = ['ffmpeg', '-y', '-f', 'concat', '-safe', '0',
           '-i', concat_file, '-c', 'copy', output_path]
    result = subprocess.run(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True)
    if os.path.exists(concat_file):
        os.remove(concat_file)
    if result.returncode != 0:
        raise Exception(f"Merge Error: {result.stderr}")


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

def main():
    st.title("🎬 Video & Text Processor with TTS")

    with st.sidebar:
        st.header("⚙️ Settings")
        selected_voice = st.selectbox("Select Voice", options=[v["name"] for v in VOICES])
        voice_id = next(v["id"] for v in VOICES if v["name"] == selected_voice)
        col1, col2 = st.columns(2)
        with col1:
            selected_style = st.selectbox("Recap Style", options=[s["name"] for s in RECAP_STYLES])
            style_data = next(s for s in RECAP_STYLES if s["name"] == selected_style)
        with col2:
            selected_emotion = st.selectbox("Emotion", options=[e["name"] for e in EMOTIONS])
            emotion_data = next(e for e in EMOTIONS if e["name"] == selected_emotion)
        final_speed, final_pitch = (style_data["speed"] + emotion_data["s"],
                                    style_data["pitch"] + emotion_data["p"])
        st.caption(f"📊 Speed: {final_speed}%, Pitch: {final_pitch}Hz")
        st.markdown("---")
        play_duration = st.slider("▶️ Play Duration (s)", 1, 5, 3)
        col3, col4 = st.columns(2)
        with col3:
            freeze1_duration = st.slider("❄️ Freeze 1 (s)", 0, 2, 1)
            freeze1_zoom = st.selectbox("Zoom 1", ["None", "Zoom In", "Zoom Out"])
        with col4:
            freeze2_duration = st.slider("❄️ Freeze 2 (s)", 0, 2, 1)
            freeze2_zoom = st.selectbox("Zoom 2", ["None", "Zoom In", "Zoom Out"])
        zoom_duration = st.slider("🔍 Zoom Duration (s)", 0.1, 1.0, 0.5)
        st.markdown("---")
        text_input = st.text_area("📝 Enter Text", height=200)
        if text_input:
            paragraphs = count_paragraphs(text_input)
            st.info(f"📊 Paragraphs: {len(paragraphs)} | Characters: {len(text_input)}")
        video_file = st.file_uploader("🎥 Upload Video", type=["mp4", "mov", "avi"])

    if st.button("🚀 Start Processing"):
        if not text_input or not video_file:
            st.error("❌ Provide text and video.")
            return

        # Setup temp directories
        temp_dir = "temp_processing"
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)

        audio_dir = os.path.join(temp_dir, "audio")
        video_dir = os.path.join(temp_dir, "video")
        adjusted_dir = os.path.join(temp_dir, "adjusted")
        chunks_dir = os.path.join(temp_dir, "chunks")
        final_dir = os.path.join(temp_dir, "final_chunks")
        for d in [audio_dir, video_dir, adjusted_dir, chunks_dir, final_dir]:
            os.makedirs(d, exist_ok=True)

        video_path = os.path.join(video_dir, "input_video.mp4")

        # Chunk-by-chunk write to save RAM
        with open(video_path, "wb") as f:
            while chunk := video_file.read(8192):
                f.write(chunk)

        paragraphs = count_paragraphs(text_input)
        num_paragraphs = len(paragraphs)

        # ── Timer placeholders ──
        timer_placeholder = st.empty()
        progress_bar = st.progress(0)
        step_status_placeholder = st.empty()

        # Free RAM
        del video_file
        gc.collect()

        # Timer tracking
        total_start = time.time()

        # Start live timer
        live_timer = LiveTimer(timer_placeholder)
        live_timer.start()

        try:
            with st.status("🚀 Processing...", expanded=True) as status:

                # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                # STEP 1+2: TTS + Split Video (PARALLEL)
                # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                step_status_placeholder.markdown("**Step 1/5:** Generating TTS audio & splitting video...")
                progress_detail = st.empty()
                step_start = time.time()

                # Generate TTS in parallel with interval progress
                progress_detail.markdown(f"🔊 Generating {num_paragraphs} TTS files in parallel...")
                asyncio.run(generate_all_tts(paragraphs, audio_dir, voice_id, final_speed, final_pitch))
                progress_detail.markdown(f"✅ TTS complete ({num_paragraphs}/{num_paragraphs})")

                # Split video
                progress_detail.markdown(f"✂️ Splitting video into {num_paragraphs} segments...")
                video_segments, _ = split_video(video_path, num_paragraphs, video_dir)
                progress_detail.markdown(f"✅ Split complete ({num_paragraphs} segments)")

                step12_elapsed = time.time() - step_start
                progress_bar.progress(0.15)

                # Delete original uploaded video
                if os.path.exists(video_path):
                    os.remove(video_path)

                progress_detail.markdown(f"✅ TTS + Split complete ({step12_elapsed:.1f}s)")

                # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                # STEP 3: Speed-adjust each segment
                # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                step_status_placeholder.markdown(
                    f"**Step 2/5:** Speed-adjusting {num_paragraphs} segments...")
                step_start = time.time()
                adjusted_segments = [None] * num_paragraphs
                with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                    futures = {
                        executor.submit(
                            speed_adjust_segment,
                            i, video_segments[i],
                            os.path.join(audio_dir, f"audio_{i}.mp3"),
                            adjusted_dir
                        ): i for i in range(num_paragraphs)
                    }
                    for future in concurrent.futures.as_completed(futures):
                        idx = futures[future]
                        try:
                            adjusted_segments[idx] = future.result()
                        except Exception as e:
                            st.error(f"❌ Speed adjust failed for segment {idx+1}: {e}")
                        # Update progress
                        done = sum(1 for x in adjusted_segments if x is not None)
                        progress_bar.progress(0.15 + 0.30 * done / num_paragraphs)
                        progress_detail.markdown(f"⚡ Segment {done}/{num_paragraphs} speed adjusted")

                gc.collect()
                step3_elapsed = time.time() - step_start
                progress_detail.markdown(f"✅ All {num_paragraphs} segments speed-adjusted ({step3_elapsed:.1f}s)")

                # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                # STEP 4: Merge all speed-adjusted segments
                # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                step_status_placeholder.markdown("**Step 3/5:** Merging segments...")
                progress_detail.markdown("🔗 Merging segments...")
                step_start = time.time()
                merged_video = os.path.join(temp_dir, "merged_video.mp4")
                merge_speed_adjusted_segments(adjusted_segments, merged_video)
                progress_bar.progress(0.50)
                step4_elapsed = time.time() - step_start
                progress_detail.markdown(f"✅ Segments merged ({step4_elapsed:.1f}s)")
                gc.collect()

                # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                # STEP 5: Split into chunks + Process
                # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                CHUNK_DURATION = 30
                merged_duration = get_video_duration(merged_video)
                num_chunks = math.ceil(merged_duration / CHUNK_DURATION)

                step_status_placeholder.markdown(
                    f"**Step 4/5:** Processing {num_chunks} chunks with effects...")
                progress_detail.markdown("✂️ Splitting into chunks...")
                step56_start = time.time()

                processed_chunks = [None] * num_chunks

                # Split all chunks first (instant copy)
                for i in range(num_chunks):
                    start_time = i * CHUNK_DURATION
                    remaining = min(CHUNK_DURATION, merged_duration - start_time)
                    chunk_path = os.path.join(chunks_dir, f"chunk_{i}.mp4")
                    cmd = ['ffmpeg', '-y', '-ss', str(start_time), '-t', str(remaining),
                           '-i', merged_video, '-c:v', 'copy', '-c:a', 'copy',
                           '-avoid_negative_ts', 'make_zero', chunk_path]
                    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    progress_detail.markdown(f"✂️ Chunk {i+1}/{num_chunks} split")

                progress_detail.markdown(f"✅ Split into {num_chunks} chunks")

                # Process chunks (1 worker for RAM safety)
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    futures = {
                        executor.submit(
                            process_chunk_with_retry,
                            i, os.path.join(chunks_dir, f"chunk_{i}.mp4"),
                            min(CHUNK_DURATION, merged_duration - i * CHUNK_DURATION),
                            final_dir,
                            play_duration, freeze1_duration, freeze2_duration,
                            freeze1_zoom, freeze2_zoom, zoom_duration
                        ): i for i in range(num_chunks)
                    }
                    for future in concurrent.futures.as_completed(futures):
                        idx = futures[future]
                        try:
                            processed_chunks[idx] = future.result()
                        except Exception as e:
                            st.error(f"❌ Chunk {idx+1} failed: {e}")
                        # Update progress
                        done = sum(1 for x in processed_chunks if x is not None)
                        progress_bar.progress(0.50 + 0.40 * done / num_chunks)
                        progress_detail.markdown(f"🎬 Chunk {done}/{num_chunks} processed with effects")

                gc.collect()
                step56_elapsed = time.time() - step56_start
                progress_detail.markdown(f"✅ All {num_chunks} chunks processed ({step56_elapsed:.1f}s)")

                # Cleanup merged video
                if os.path.exists(merged_video):
                    os.remove(merged_video)

                # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                # STEP 6: Merge processed chunks
                # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                step_status_placeholder.markdown("**Step 5/5:** Merging final video...")
                progress_detail.markdown("🔗 Merging final video...")
                step_start = time.time()
                output_video = "final_output.mp4"
                try:
                    merge_videos(processed_chunks, output_video)
                    progress_bar.progress(1.0)
                    step6_elapsed = time.time() - step_start
                    progress_detail.markdown(f"✅ Final video merged ({step6_elapsed:.1f}s)")
                    status.update(label="✅ Complete!", state="complete")
                except Exception as e:
                    st.error(f"❌ Final merge failed: {e}")
                    status.update(label="❌ Failed", state="error")
                    live_timer.stop()
                    return

                st.write("✅ Final video merged.")

        except Exception as e:
            st.error(f"❌ Processing failed: {e}")
            live_timer.stop()
            return

        # ── Stop live timer ──
        live_timer.stop()

        # ── Final timer summary ──
        total_elapsed = time.time() - total_start
        timer_placeholder.markdown(f"⏱️ **Total: {format_time(total_elapsed)}**")
        step_status_placeholder.markdown("**✅ All steps complete!**")
        st.success(f"🎉 Completed in **{format_time(total_elapsed)}**")

        # Download button
        if os.path.exists(output_video):
            st.download_button(
                "📥 Download Final Video",
                data=open(output_video, "rb"),
                file_name="output_video.mp4",
                mime="video/mp4"
            )

        # Final cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)
        if os.path.exists(output_video):
            os.remove(output_video)


if __name__ == "__main__":
    main()

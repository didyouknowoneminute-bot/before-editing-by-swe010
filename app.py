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

    # Target video duration is rounded up to the nearest 0.5s increment
    # relative to the audio duration (ensuring a buffer of 0 to 0.5s).
    # This prevents audio truncation while keeping the buffer small.
    target_video_duration = math.ceil(audio_duration * 2) / 2
    
    # Ensure the video is at least as long as the audio (handle float precision)
    if target_video_duration < audio_duration:
        target_video_duration = audio_duration
        
    speed_factor = target_video_duration / orig_duration

    # Use a simpler filter complex that only touches video PTS.
    # We map audio directly (1:a) to ensure the TTS audio duration is strictly preserved.
    # We do NOT use -shortest because we want the video to be slightly longer (0-0.5s) than the audio.
    cmd = [
        'ffmpeg', '-y',
        '-i', video_segment,
        '-i', audio_path,
        '-filter_complex', f"[0:v]setpts={speed_factor}*PTS[v]",
        '-map', '[v]',
        '-map', '1:a',
        '-c:v', 'libx264', '-preset', 'ultrafast',
        '-c:a', 'aac',
        output_path
    ]

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
# Step 5: Apply cycle repeat to a single chunk
# ─────────────────────────────────────────────

def build_cycle_filter(video_path, audio_path, chunk_duration,
                       play_dur, freeze1_dur, freeze2_dur,
                       freeze1_zoom, freeze2_zoom, zoom_dur):
    """Build FFmpeg filter complex for cycle repeat on a chunk."""
    fps = 24
    cycle_duration = play_dur + freeze1_dur + freeze2_dur
    num_cycles = math.ceil(chunk_duration / cycle_duration)

    # Use original resolution
    width, height = get_video_resolution(video_path)
    res_str = f"{width}x{height}"

    def make_zoom_filter(zoom_dur, total_dur, zoom_type):
        total_frames = max(int(total_dur * fps), 1)
        zoom_frames = max(int(zoom_dur * fps), 1)
        # Cap zoom_frames at total_frames to avoid overflow
        z_frames = min(zoom_frames, total_frames)
        
        if zoom_type == "Zoom In":
            # Zoom from 1.0 to 1.15 over z_frames, then stay at 1.15
            return (f"zoompan=z='if(lte(on,{z_frames}),min(1+0.15*on/{z_frames},1.15),1.15)':"
                    f"d={total_frames}:s={res_str}:fps={fps}")
        elif zoom_type == "Zoom Out":
            # Zoom from 1.15 to 1.0 over z_frames, then stay at 1.0
            return (f"zoompan=z='if(lte(on,{z_frames}),max(1.15-0.15*on/{z_frames},1.0),1.0)':"
                    f"d={total_frames}:s={res_str}:fps={fps}")
        return None

    f1_z = make_zoom_filter(zoom_dur, freeze1_dur, freeze1_zoom) if freeze1_zoom != "None" else None
    f2_z = make_zoom_filter(zoom_dur, freeze2_dur, freeze2_zoom) if freeze2_zoom != "None" else None

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
            f1_end = min(f1_start + freeze1_dur, chunk_duration)
            f1_actual_dur = f1_end - f1_start
            if f1_actual_dur > 0:
                filter_parts.append(
                    f"[0:v]trim=start={f1_start}:end={f1_end},setpts=PTS-STARTPTS,"
                    f"loop=loop={int(f1_actual_dur * fps)}:size=1:start=0[vf1_{i}];")
                if f1_z:
                    filter_parts.append(f"[vf1_{i}]{f1_z}[vf1z_{i}];")
                    concat_inputs.append(f"[vf1z_{i}]")
                else:
                    concat_inputs.append(f"[vf1_{i}]")

        # Freeze 2
        f2_start = curr + play_dur + freeze1_dur
        if f2_start < chunk_duration:
            f2_end = min(f2_start + freeze2_dur, chunk_duration)
            f2_actual_dur = f2_end - f2_start
            if f2_actual_dur > 0:
                filter_parts.append(
                    f"[0:v]trim=start={f2_start}:end={f2_end},setpts=PTS-STARTPTS,"
                    f"loop=loop={int(f2_actual_dur * fps)}:size=1:start=0[vf2_{i}];")
                if f2_z:
                    filter_parts.append(f"[vf2_{i}]{f2_z}[vf2z_{i}];")
                    concat_inputs.append(f"[vf2z_{i}]")
                else:
                    concat_inputs.append(f"[vf2_{i}]")

    filter_str = "".join(filter_parts)
    filter_str += "".join(concat_inputs) + f"concat=n={len(concat_inputs)}:v=1:a=0[vout]"
    
    return filter_str


def process_chunk_with_retry(index, chunk_path, chunk_duration, output_dir,
                            play_dur, freeze1_dur, freeze2_dur,
                            freeze1_zoom, freeze2_zoom, zoom_dur, retries=2):
    """Process a single chunk with FFmpeg filter complex. Retries on failure."""
    output_path = os.path.join(output_dir, f"processed_{index}.mp4")
    filter_str = build_cycle_filter(chunk_path, chunk_path, chunk_duration,
                                    play_dur, freeze1_dur, freeze2_dur,
                                    freeze1_zoom, freeze2_zoom, zoom_dur)
    
    cmd = [
        'ffmpeg', '-y', '-i', chunk_path,
        '-filter_complex', filter_str,
        '-map', '[vout]', '-map', '0:a',
        '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '23',
        '-c:a', 'copy', output_path
    ]

    for attempt in range(retries + 1):
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode == 0 and os.path.exists(output_path):
            if os.path.exists(chunk_path):
                os.remove(chunk_path)
            return output_path
        time.sleep(1)
    
    raise Exception(f"Chunk {index} failed after {retries} retries: {result.stderr}")


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
        st.markdown("---")
        text_input = st.text_area("📝 Enter Text", height=200)
        if text_input:
            paragraphs = count_paragraphs(text_input)
            st.info(f"📊 Paragraphs: {len(paragraphs)} | Characters: {len(text_input)}")
        video_file = st.file_uploader("🎥 Upload Video", type=["mp4", "mov", "avi"])

    # Initialize session state for tracking
    if 'processing_active' not in st.session_state:
        st.session_state.processing_active = False

    # Start button logic
    if st.button("🚀 Start Processing") and not st.session_state.processing_active:

        if not text_input or not video_file:
            st.error("❌ Provide text and video.")
            return
        
        st.session_state.processing_active = True
        
        # Save inputs to session state
        st.session_state.inputs = {
            "text": text_input,
            "voice_id": voice_id,
            "final_speed": final_speed,
            "final_pitch": final_pitch,
            "play_duration": play_duration,
        }

        # Setup temp directories
        temp_dir = "temp_processing"
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)

        st.session_state.dirs = {
            "temp": temp_dir,
            "audio": os.path.join(temp_dir, "audio"),
            "video": os.path.join(temp_dir, "video"),
            "adjusted": os.path.join(temp_dir, "adjusted"),
        }
        for d in st.session_state.dirs.values():
            os.makedirs(d, exist_ok=True)

        video_path = os.path.join(st.session_state.dirs["video"], "input_video.mp4")
        st.session_state.video_path = video_path

        with open(video_path, "wb") as f:
            while chunk := video_file.read(8192):
                f.write(chunk)

        # Display status and progress
        status = st.status("Processing video...", expanded=True)
        status.write("Starting video processing...")
        progress_bar = status.progress(0, text="Initializing...")
        step_status_placeholder = status.empty()
        progress_detail = status.empty()
        timer_placeholder = status.empty()

        total_start = time.time()

        try:
            inputs = st.session_state.inputs
            dirs = st.session_state.dirs
            video_path = st.session_state.video_path
            paragraphs = count_paragraphs(inputs["text"])
            num_paragraphs = len(paragraphs)

            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # STEP 1+2: Pre-process Video + TTS + Split (PARALLEL)
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            step_status_placeholder.markdown("**Step 1/3:** Pre-processing video & generating TTS...")
            progress_detail.markdown("Initializing...")
            step_start = time.time()

            # Pre-process video: cap at 900p, convert to 24fps
            orig_width, orig_height = get_video_resolution(video_path)
            needs_preprocess = (orig_width > 1600) or (orig_height > 900) or (get_video_duration(video_path) == 0) # Handle zero duration

            if needs_preprocess:
                optimized_video_path = os.path.join(dirs["video"], "optimized_900p_24fps.mp4")
                progress_detail.markdown(f"⚙️ Downscaling to 900p + 24fps (Original: {orig_width}×{orig_height})...")
                cmd = ['ffmpeg', '-y', '-i', video_path, '-vf', "scale='if(gt(iw,ih),1600,-2)':'if(gt(iw,ih),-2,1600)':force_original_aspect_ratio=decrease",
                       '-r', '24', '-c:v', 'libx264', '-preset', 'ultrafast', '-c:a', 'aac', optimized_video_path]
                subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            else:
                optimized_video_path = os.path.join(dirs["video"], "optimized_24fps.mp4")
                progress_detail.markdown(f"⚙️ Converting to 24fps (Resolution: {orig_width}×{orig_height})...")
                cmd = ['ffmpeg', '-y', '-i', video_path, '-r', '24',
                       '-c:v', 'libx264', '-preset', 'ultrafast', '-c:a', 'aac', optimized_video_path]
                subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            if os.path.exists(video_path):
                os.remove(video_path)
            video_path = optimized_video_path
            st.session_state.video_path = video_path

            progress_detail.markdown(f"🔊 Generating {num_paragraphs} TTS files in parallel...")
            asyncio.run(generate_all_tts(paragraphs, dirs["audio"], inputs["voice_id"], inputs["final_speed"], inputs["final_pitch"]))
            progress_detail.markdown(f"✅ TTS complete ({num_paragraphs}/{num_paragraphs})")

            progress_detail.markdown(f"✂️ Splitting video into {num_paragraphs} segments...")
            video_segments, _ = split_video(video_path, num_paragraphs, dirs["video"])
            progress_detail.markdown(f"✅ Split complete ({num_paragraphs} segments)")

            step12_elapsed = time.time() - step_start
            progress_bar.progress(0.33)
            progress_detail.markdown(f"✅ TTS + Split complete ({step12_elapsed:.1f}s)")

            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # STEP 3: Speed-adjust each segment
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            step_status_placeholder.markdown(f"**Step 2/3:** Speed-adjusting {num_paragraphs} segments...")
            step_start = time.time()
            adjusted_segments = [None] * num_paragraphs
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                futures = {
                    executor.submit(
                        speed_adjust_segment,
                        i, video_segments[i],
                        os.path.join(dirs["audio"], f"audio_{i}.mp3"),
                        dirs["adjusted"]
                    ): i for i in range(num_paragraphs)
                }
                for future in concurrent.futures.as_completed(futures):
                    idx = futures[future]
                    try:
                        adjusted_segments[idx] = future.result()
                    except Exception as e:
                        st.error(f"❌ Speed adjust failed for segment {idx+1}: {e}")
                    done = sum(1 for x in adjusted_segments if x is not None)
                    progress_bar.progress(0.33 + 0.33 * done / num_paragraphs)
                    progress_detail.markdown(f"⚡ Segment {done}/{num_paragraphs} speed adjusted")

            gc.collect()
            step3_elapsed = time.time() - step_start
            progress_detail.markdown(f"✅ All {num_paragraphs} segments speed-adjusted ({step3_elapsed:.1f}s)")

            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # FINAL STEP: Merge all speed-adjusted segments
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            step_status_placeholder.markdown("**Step 3/3:** Merging final video...")
            progress_detail.markdown("🔗 Merging segments...")
            step_start = time.time()
            output_video = os.path.join(dirs["temp"], "final_output.mp4")
            merge_speed_adjusted_segments(adjusted_segments, output_video)
            progress_bar.progress(1.0)
            final_merge_elapsed = time.time() - step_start
            progress_detail.markdown(f"✅ Final video merged ({final_merge_elapsed:.1f}s)")
            gc.collect()
            
            st.session_state.processing_active = False
            status.update(label="✅ Complete!", state="complete")
            st.write("✅ Processing complete. Download your video below.")

        except Exception as e:
            st.error(f"❌ Processing failed: {e}")
            st.session_state.processing_active = False
            return

        total_elapsed = time.time() - total_start
        timer_placeholder.markdown(f"⏱️ **Total: {format_time(total_elapsed)}**")
        step_status_placeholder.markdown("**✅ All steps complete!**")
        st.success(f"🎉 Completed in **{format_time(total_elapsed)}**")

        if os.path.exists(output_video):
            st.download_button(
                "📥 Download Final Video",
                data=open(output_video, "rb"),
                file_name="final_output.mp4",
                mime="video/mp4"
            )

        if st.button("🧹 Cleanup All Files"):
            shutil.rmtree(dirs["temp"], ignore_errors=True)
            if os.path.exists(output_video):
                os.remove(output_video)
            st.session_state.processing_active = False
            st.rerun()
if __name__ == "__main__":
    main()

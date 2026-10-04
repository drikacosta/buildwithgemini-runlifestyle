import os
import math
import numpy as np
import scipy.io.wavfile as wav
import subprocess
from google.cloud import storage

BUCKET_NAME = "runlifestyle-images-qwiklabs-gcp-02-61a3e08edf96"
FFMPEG = "/config/.cache/ms-playwright/ffmpeg-1011/ffmpeg-linux"

def generate_lofi_track(duration_sec=38.0, sample_rate=44100):
    bpm = 85.0
    beat_duration = 60.0 / bpm
    total_samples = int(sample_rate * duration_sec)
    audio = np.zeros(total_samples, dtype=np.float32)

    # Chord progression frequencies (Cmaj7, Am7, Dm7, G7 in warm octave)
    chords = [
        [261.63, 329.63, 392.00, 493.88], # Cmaj7 (C4, E4, G4, B4)
        [220.00, 261.63, 329.63, 392.00], # Am7 (A3, C4, E4, G4)
        [293.66, 349.23, 440.00, 523.25], # Dm7 (D4, F4, A4, C5)
        [196.00, 246.94, 293.66, 349.23], # G7 (G3, B3, D4, F4)
    ]

    t = np.arange(total_samples) / float(sample_rate)

    # 1. Electric Piano Chords (Smooth Sine + Warm harmonics with lo-fi decay)
    bar_duration = beat_duration * 4.0
    num_bars = int(duration_sec / bar_duration) + 1

    for bar in range(num_bars):
        chord_freqs = chords[bar % len(chords)]
        bar_start_sample = int(bar * bar_duration * sample_rate)
        bar_len = int(bar_duration * sample_rate)
        
        if bar_start_sample >= total_samples:
            break

        # Strum chord at bar start and beat 2.5
        strum_offsets = [0.0, beat_duration * 2.5]
        for offset in strum_offsets:
            s_start = bar_start_sample + int(offset * sample_rate)
            if s_start >= total_samples:
                continue
            
            s_len = min(int(beat_duration * 2.2 * sample_rate), total_samples - s_start)
            t_strum = np.arange(s_len) / float(sample_rate)
            env = np.exp(-1.8 * t_strum) * (1.0 - np.exp(-20.0 * t_strum)) # smooth piano envelope
            
            chord_signal = np.zeros(s_len, dtype=np.float32)
            for f in chord_freqs:
                # Sine + soft 2nd/3rd harmonics
                note = (np.sin(2 * np.pi * f * t_strum) + 
                        0.3 * np.sin(2 * np.pi * 2 * f * t_strum) + 
                        0.1 * np.sin(2 * np.pi * 3 * f * t_strum))
                chord_signal += note
            
            chord_signal = (chord_signal / len(chord_freqs)) * env * 0.35
            audio[s_start:s_start + s_len] += chord_signal

    # 2. Kick Drum (Sub bass drop + fast punch)
    num_beats = int(duration_sec / beat_duration) + 1
    for beat in range(num_beats):
        # Kick on beat 1 and beat 3.5 (lo-fi groove)
        kick_offsets = [0.0, beat_duration * 2.5] if (beat % 2 == 0) else [0.0, beat_duration * 1.5]
        beat_start = beat * beat_duration
        for ko in kick_offsets:
            k_time = beat_start + ko
            k_start = int(k_time * sample_rate)
            if k_start >= total_samples:
                continue
            k_len = min(int(0.25 * sample_rate), total_samples - k_start)
            tk = np.arange(k_len) / float(sample_rate)
            # pitch drop from 120Hz to 45Hz
            freq_env = 45.0 + 75.0 * np.exp(-30.0 * tk)
            phase = 2 * np.pi * np.cumsum(freq_env) / sample_rate
            kick = np.sin(phase) * np.exp(-12.0 * tk) * 0.45
            audio[k_start:k_start + k_len] += kick

    # 3. Soft Snare / Rimshot on beat 2 and beat 4
    for beat in range(num_beats):
        if beat % 2 == 1:
            s_start = int(beat * beat_duration * sample_rate)
            if s_start < total_samples:
                s_len = min(int(0.18 * sample_rate), total_samples - s_start)
                ts = np.arange(s_len) / float(sample_rate)
                noise = (np.random.rand(s_len) * 2.0 - 1.0) * np.exp(-25.0 * ts) * 0.18
                body = np.sin(2 * np.pi * 180 * ts) * np.exp(-35.0 * ts) * 0.2
                audio[s_start:s_start + s_len] += (noise + body)

    # 4. Hi-Hat pattern (8th notes)
    hat_step = beat_duration / 2.0
    num_hats = int(duration_sec / hat_step) + 1
    for h in range(num_hats):
        h_start = int(h * hat_step * sample_rate)
        if h_start < total_samples:
            h_len = min(int(0.05 * sample_rate), total_samples - h_start)
            th = np.arange(h_len) / float(sample_rate)
            hat = (np.random.rand(h_len) * 2.0 - 1.0) * np.exp(-80.0 * th) * 0.08
            audio[h_start:h_start + h_len] += hat

    # 5. Vinyl Crackle & Ambient Warmth
    crackle = (np.random.rand(total_samples) * 2.0 - 1.0)
    crackle = np.where(np.abs(crackle) > 0.985, crackle * 0.06, 0.0)
    audio += crackle

    # Master Normalize & Peak Limiter
    max_val = np.max(np.abs(audio))
    if max_val > 0:
        audio = audio / max_val * 0.85

    audio_int16 = (audio * 32767).astype(np.int16)
    wav.write("lofi_music.wav", sample_rate, audio_int16)
    print("Generated lofi_music.wav successfully!")

def merge_video_and_audio():
    video_in = "runlifestyle_demo.webm"
    audio_in = "lofi_music.wav"
    output_webm = "runlifestyle_demo_lofi.webm"

    print(f"Merging {video_in} with {audio_in}...")
    cmd = [
        FFMPEG, "-y",
        "-i", video_in,
        "-i", audio_in,
        "-c:v", "copy",
        "-c:a", "libvpx_vp8",
        "-shortest",
        output_webm
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    print("FFmpeg output:", res.stdout, res.stderr)

    if os.path.exists(output_webm):
        print(f"Merged video created: {output_webm}")
        # Upload to GCS
        try:
            client = storage.Client(project="qwiklabs-gcp-02-61a3e08edf96")
            bucket = client.bucket(BUCKET_NAME)
            blob = bucket.blob(output_webm)
            blob.upload_from_filename(output_webm, content_type="video/webm")
            public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{output_webm}"
            print(f"Uploaded demo with lo-fi music to GCS: {public_url}")
        except Exception as e:
            print(f"Error uploading to GCS: {e}")

if __name__ == "__main__":
    generate_lofi_track(duration_sec=38.0)
    merge_video_and_audio()

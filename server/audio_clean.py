"""Cleans a recording from a loud room (an emergency department) before speech recognition.

Three steps, all on the server with numpy, no extra models:
1. Speech band: removes rumble and hum below 100 Hz and hiss above 7 kHz.
2. Steady noise: estimates the room's constant noise (ventilation, monitors, distant murmur) from the quietest
   moments and subtracts it, frequency by frequency.
3. Closest voice: the person speaking into the phone is the loudest voice in the recording. Stretches that are
   much quieter than that voice (other people further away) are turned down, and background-only time before
   the speaker starts and after they finish is trimmed off.
"""
import numpy as np

SR = 16000
N_FFT, HOP = 512, 128                 # 32 ms windows, 8 ms steps
BAND = (100.0, 7000.0)                # speech band kept, in Hz
NOISE_PERCENTILE = 15                 # the room's steady noise = the quiet 15% of each frequency over time
OVERSUBTRACT, GAIN_FLOOR = 1.6, 0.12  # how hard steady noise is removed, and how far it can be turned down
FOCUS_DB = 20.0                       # stretches this far below the closest voice are background
FOCUS_KEEP_DB = 12.0                  # stretches within this of the closest voice are always kept in full
TRIM_DB, TRIM_PAD_S = 14.0, 0.3       # trimming: foreground = within 14 dB of the closest voice, plus 0.3 s


def _frames(x):
    pad = N_FFT // 2
    xp = np.pad(x, (pad, pad + N_FFT))
    n = 1 + (len(xp) - N_FFT) // HOP
    idx = np.arange(N_FFT)[None, :] + HOP * np.arange(n)[:, None]
    return xp[idx]


def _smooth(a, n, axis):
    if n <= 1:
        return a
    k = np.ones(n) / n
    return np.apply_along_axis(lambda v: np.convolve(v, k, mode="same"), axis, a)


def clean_speech(audio, sr=SR):
    """Returns (cleaned audio, info). Short or silent recordings are returned unchanged."""
    x = np.asarray(audio, dtype=np.float32)
    if sr != SR or len(x) < SR * 0.4 or float(np.abs(x).max()) < 1e-4:
        return x, {"cleaned": False}
    win = (0.5 - 0.5 * np.cos(2 * np.pi * np.arange(N_FFT) / N_FFT)).astype(np.float32)   # periodic Hann
    spec = np.fft.rfft(_frames(x) * win, axis=1)
    mag = np.abs(spec) + 1e-9
    freqs = np.fft.rfftfreq(N_FFT, 1 / SR)

    # 2. Steady noise, removed per frequency, smoothed so it doesn't leave a "watery" sound behind
    noise = np.percentile(mag, NOISE_PERCENTILE, axis=0)
    gain = np.clip(1.0 - OVERSUBTRACT * noise[None, :] / mag, GAIN_FLOOR, 1.0)
    gain = _smooth(_smooth(gain, 3, 0), 3, 1)
    # 1. Speech band
    gain[:, (freqs < BAND[0]) | (freqs > BAND[1])] = GAIN_FLOOR * 0.5
    spec = spec * gain

    # 3. Closest voice: loudness of each moment in the core speech band, as an envelope over +-100 ms
    core = (freqs >= 300) & (freqs <= 3500)
    level = 10 * np.log10(np.sum(np.abs(spec[:, core]) ** 2, axis=1) + 1e-10)
    span = 12
    padded = np.pad(level, span, mode="edge")
    env = np.max(np.lib.stride_tricks.sliding_window_view(padded, 2 * span + 1), axis=1)
    voice = float(np.percentile(level, 95))            # the closest (loudest) voice
    below = voice - env
    focus = np.clip((FOCUS_DB - below) / (FOCUS_DB - FOCUS_KEEP_DB), 0.0, 1.0)
    focus = _smooth(0.1 + 0.9 * focus, 9, 0)          # far voices turned down by up to 20 dB, smoothly
    spec = spec * focus[:, None]

    # Back to audio (overlap-add)
    out_frames = np.fft.irfft(spec, n=N_FFT, axis=1) * win
    y = np.zeros(len(out_frames) * HOP + N_FFT, dtype=np.float32)
    norm = np.zeros_like(y)
    for i, f in enumerate(out_frames):                 # ~2,000 frames for 18 s: fast enough
        s = i * HOP
        y[s:s + N_FFT] += f
        norm[s:s + N_FFT] += win ** 2
    y = (y / np.maximum(norm, 1e-6))[N_FFT // 2: N_FFT // 2 + len(x)]

    # Trim background-only time before and after the closest voice
    fg = np.where(level >= voice - TRIM_DB)[0]
    start = end = None
    if len(fg):
        pad = int(TRIM_PAD_S * SR)
        start = max(0, fg[0] * HOP - N_FFT // 2 - pad)
        end = min(len(y), fg[-1] * HOP + N_FFT // 2 + pad)
        if end - start >= SR * 0.4:
            y = y[start:end]
    peak = float(np.abs(y).max())
    if peak > 1e-6:
        y = y * (0.9 / peak)
    return y.astype(np.float32), {"cleaned": True, "noiseDb": round(float(20 * np.log10(np.median(noise) + 1e-9)), 1),
                                  "trimmed": [round(float(start or 0) / SR, 2), round(float(end or len(x)) / SR, 2)]}

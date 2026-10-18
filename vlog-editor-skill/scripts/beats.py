"""Music analysis: tempo, first downbeat, per-second energy -- so cuts can land on the beat and you can
see where a track builds, drops, or runs out.

usage: python3 beats.py [--out DIR] track.mp3 [track2.mp3 ...]
Writes DIR/<file>.json = {dur, tempo, first_beat, energy:[per-second RMS]} and prints an energy bar.
(numpy only -- no librosa needed.)
"""
import argparse
import json
import os
import subprocess

import numpy as np


def load(p, sr=22050):
    raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", p, "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
                         capture_output=True).stdout
    return np.frombuffer(raw, np.float32), sr


def analyse(p):
    y, sr = load(p)
    hop, n = 512, 2048
    frames = np.lib.stride_tricks.sliding_window_view(y, n)[::hop] * np.hanning(n)
    logm = np.log1p(10 * np.abs(np.fft.rfft(frames)))
    flux = np.maximum(0, np.diff(logm, axis=0)).sum(1)
    flux = (flux - flux.mean()) / (flux.std() + 1e-9)
    fps = sr / hop
    ac = np.correlate(flux, flux, "full")[len(flux) - 1:]
    lags = np.arange(len(ac))
    bpm = 60 * fps / np.maximum(lags, 1)
    m = (bpm > 70) & (bpm < 180)
    lag = lags[m][np.argmax(ac[m])]
    off = max(range(lag), key=lambda o: flux[o::lag].sum())
    rms = np.sqrt((frames ** 2).mean(1))
    sec = int(len(y) / sr)
    energy = [float(rms[int(i * fps):int((i + 1) * fps)].mean()) for i in range(sec)]
    return dict(dur=len(y) / sr, tempo=round(60 * fps / lag, 1), first_beat=round(off / fps, 3), energy=energy)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("tracks", nargs="+")
    ap.add_argument("--out", default=".")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    for p in a.tracks:
        r = analyse(p)
        e = np.array(r["energy"]); e = e / (e.max() + 1e-9)
        bars = " ".join("▁▂▃▄▅▆▇█"[min(7, int(e[i:i + 8].mean() * 8))] for i in range(0, len(e), 8))
        print(f"{os.path.basename(p)}: {r['dur']:.0f}s  {r['tempo']} bpm  first beat {r['first_beat']}s\n  energy/8s: {bars}")
        json.dump(r, open(os.path.join(a.out, os.path.basename(p) + ".json"), "w"))

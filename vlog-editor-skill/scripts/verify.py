"""Verification -- prove a cut or a render is right instead of assuming.

usage:
  python3 verify.py cut CLIP START END        loudness every 50 ms around a cut (find real word edges/silence)
  python3 verify.py output VIDEO [LISTFILE]   frame gaps, A/V length, per-shot drift (if the render's
                                              list_*.txt is given), integrated loudness and true peak
  python3 verify.py levels VIDEO [SECONDS]    loudness per 0.5 s (music too loud/quiet? pumping?)
  python3 verify.py frames VIDEO OUT.png t1 t2 ...   stills of the *rendered* video for a visual check

Pair `cut` with `transcribe.py --snippet CLIP START END`: the waveform shows where sound starts/stops,
the snippet transcription tells you which words are actually inside the cut (e.g. a stray "and...").
"""
import json
import subprocess
import sys

import numpy as np


def env(src, a, b, win=0.05):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(a), "-t", str(b - a), "-i", src, "-vn", "-ac", "1",
                          "-ar", "16000", "-af", "highpass=f=150,lowpass=f=3800", "-f", "f32le", "-"], capture_output=True).stdout
    y = np.frombuffer(raw, np.float32)
    n = int(16000 * win)
    k = len(y) // n
    r = 20 * np.log10(np.sqrt((y[:k * n].reshape(k, n) ** 2).mean(1)) + 1e-6)
    return [(a + i * win, v) for i, v in enumerate(r)]


def probe(f):
    j = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,duration",
                                   "-of", "json", f], capture_output=True, text=True).stdout)
    return {s["codec_type"]: float(s.get("duration", 0)) for s in j["streams"]}


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "cut":
        src, a, b = sys.argv[2], float(sys.argv[3]), float(sys.argv[4])
        e = env(src, a, b)
        floor = float(np.percentile([v for _, v in e], 15))
        print(" ".join(f"{t:.2f}:{int(v)}{'*' if v > floor + 8 else ''}" for t, v in e))
        print(f"(voice-band dB per 50 ms; noise floor here ~{floor:.0f} dB; * = likely speech (> floor+8). "
              "On loud street audio rely on transcribe.py --snippet --lang en as the tie-breaker.)")
    elif cmd == "output":
        f = sys.argv[2]
        d = probe(f)
        pts = sorted(float(x) for x in subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                                      "packet=pts_time", "-of", "csv=p=0", f], capture_output=True,
                                                     text=True).stdout.split())
        gaps = [(round(x, 2), round(y - x, 2)) for x, y in zip(pts, pts[1:]) if y - x > 0.05]
        o = subprocess.run(["ffmpeg", "-nostdin", "-i", f, "-vn", "-af", "ebur128=peak=true", "-f", "null", "-"],
                           capture_output=True, text=True).stderr
        lo = [l.strip() for l in o.splitlines() if l.strip().startswith(("I:", "Peak:"))][-2:]
        print(f"video {d.get('video', 0):.3f}s  audio {d.get('audio', 0):.3f}s  frames {len(pts)}  gaps {gaps[:5]}  {lo}")
        if len(sys.argv) > 3:
            shots = [l.strip()[6:-1] for l in open(sys.argv[3])]
            off = [probe(s).get("video", 0) - probe(s).get("audio", 0) for s in shots]
            print(f"{len(shots)} shots | worst shot A/V mismatch {max(map(abs, off)) * 1000:.1f} ms | "
                  f"total drift {sum(off) * 1000:.1f} ms (should be a few ms)")
    elif cmd == "levels":
        f = sys.argv[2]
        t = float(sys.argv[3]) if len(sys.argv) > 3 else 1e9
        o = subprocess.run(["ffmpeg", "-nostdin", "-t", str(t), "-i", f, "-vn", "-af",
                            "asetnsamples=n=24000:p=0,astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.RMS_level",
                            "-f", "null", "-"], capture_output=True, text=True).stderr
        v = [l.split("=")[1][:5] for l in o.splitlines() if "RMS_level=" in l]
        print("dB per 0.5 s:", " ".join(v))
    elif cmd == "frames":
        from PIL import Image
        f, out, ts = sys.argv[2], sys.argv[3], [float(x) for x in sys.argv[4:]]
        ims = []
        for t in ts:
            raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{t:.2f}", "-i", f, "-frames:v", "1",
                                  "-vf", "scale=480:270", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
            ims.append(Image.frombytes("RGB", (480, 270), raw) if len(raw) == 480 * 270 * 3 else Image.new("RGB", (480, 270)))
        cols = min(4, len(ims))
        g = Image.new("RGB", (480 * cols, 270 * ((len(ims) + cols - 1) // cols)))
        for k, im in enumerate(ims):
            g.paste(im, ((k % cols) * 480, (k // cols) * 270))
        g.save(out)
        print(out)

"""Local speech-to-text with word timestamps (Apple Silicon, mlx-whisper large-v3-turbo). Nothing leaves the Mac.

usage: python3 transcribe.py --cache DIR clip1.MOV clip2.MOV ...      (skips clips already done)
       python3 transcribe.py --snippet clip.MOV START END              (what is *actually* said in a cut)

Writes DIR/tx/<clip stem>.json = {text, language, segments:[{start,end,text,nsp,words:[{word,start,end}]}]}

Run ONE transcription job at a time on 8 GB machines (two models in memory thrash swap).
Whisper word times drift (early after pauses, stretched on drawn-out words) and it can hallucinate repeats
("It's the best pizza" x6) -- treat timings as approximate and verify important cuts with --snippet.
Setup (once): python3 -m venv ~/.vlog-editor-venv && ~/.vlog-editor-venv/bin/pip install mlx-whisper
"""
import argparse
import json
import os
import subprocess
import tempfile

MODEL = "mlx-community/whisper-large-v3-turbo"
if os.path.isdir(os.path.expanduser("~/.cache/huggingface/hub/models--mlx-community--whisper-large-v3-turbo")):
    os.environ.setdefault("HF_HUB_OFFLINE", "1")  # model already downloaded: never touch the network


def wav(src, a=None, b=None):
    out = tempfile.mktemp(suffix=".wav")
    cmd = ["ffmpeg", "-nostdin", "-y", "-v", "error"]
    if a is not None:
        cmd += ["-ss", str(a), "-t", str(b - a)]
    subprocess.run(cmd + ["-i", src, "-vn", "-ac", "1", "-ar", "16000", out], check=True)
    return out


def main():
    import mlx_whisper
    ap = argparse.ArgumentParser()
    ap.add_argument("clips", nargs="*")
    ap.add_argument("--cache")
    ap.add_argument("--snippet", nargs=3, metavar=("CLIP", "START", "END"))
    ap.add_argument("--lang", default=None, help="e.g. en -- strongly recommended for --snippet (short noisy "
                    "windows otherwise get detected as another language and hallucinate)")
    a = ap.parse_args()
    if a.snippet:
        c, s, e = a.snippet
        r = mlx_whisper.transcribe(wav(c, float(s), float(e)), path_or_hf_repo=MODEL, condition_on_previous_text=False,
                                   language=a.lang or "en")
        print(repr(r["text"].strip()))
        return
    os.makedirs(os.path.join(a.cache, "tx"), exist_ok=True)
    for c in a.clips:
        out = os.path.join(a.cache, "tx", os.path.splitext(os.path.basename(c))[0] + ".json")
        if os.path.exists(out):
            continue
        w = wav(c)
        r = mlx_whisper.transcribe(w, path_or_hf_repo=MODEL, word_timestamps=True, condition_on_previous_text=False,
                                   **({"language": a.lang} if a.lang else {}))
        json.dump({"text": r["text"], "language": r.get("language"),
                   "segments": [{"start": s["start"], "end": s["end"], "text": s["text"], "nsp": s.get("no_speech_prob"),
                                 "words": s.get("words", [])} for s in r["segments"]]}, open(out, "w"))
        os.remove(w)
        print(os.path.basename(c), "|", r["text"][:90].strip(), flush=True)


if __name__ == "__main__":
    main()

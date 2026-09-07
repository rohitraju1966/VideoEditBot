#!/usr/bin/env python3
"""Transcribe and analyse a folder of clips into index/<id>.json.

One pass per clip produces the complete record the selection stage reads:
word-level transcript plus on-device visual signal. The visual half is not
a nicety — roughly 40% of this corpus has no speech at all, and without it
those clips reach `select` as empty records.

Expensive and idempotent: a clip with an existing index/<id>.json is skipped
unless --force is given.

    python transcribe.py raw/
    python transcribe.py raw/ --model small --limit 10
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
import time

import numpy as np

VIDEO_SUFFIXES = {".mov", ".mp4", ".m4v", ".avi", ".mkv"}

# Frames are sampled at these fractions of each clip's duration. One frame is
# a lottery ticket on a handheld shot; three is enough to catch a whip pan.
SAMPLE_POINTS = (0.25, 0.5, 0.75)

# Downscale for the blur metric. Laplacian variance is scale-dependent, so
# this must stay fixed or scores stop being comparable between runs.
BLUR_W, BLUR_H = 480, 270

LABEL_MIN_CONFIDENCE = 0.5


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Run a command, raising with the real stderr if it fails."""
    proc = subprocess.run(cmd, capture_output=True, **kwargs)
    if proc.returncode != 0:
        stderr = proc.stderr
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", "replace")
        raise RuntimeError(f"{cmd[0]} failed on {cmd[-1]}:\n{stderr.strip()}")
    return proc


def probe(path: pathlib.Path) -> dict:
    """Duration, resolution, fps and codecs. Raises if the file is unreadable."""
    out = run([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration,size",
        "-show_entries", "stream=codec_type,codec_name,width,height,r_frame_rate",
        "-of", "json", str(path),
    ], text=True).stdout
    data = json.loads(out)

    duration = float(data["format"]["duration"])
    if duration <= 0:
        raise RuntimeError(f"{path.name}: non-positive duration {duration}")

    video = next((s for s in data["streams"] if s.get("codec_type") == "video"), None)
    audio = next((s for s in data["streams"] if s.get("codec_type") == "audio"), None)
    if video is None:
        raise RuntimeError(f"{path.name}: no video stream")

    num, den = (int(x) for x in video["r_frame_rate"].split("/"))
    return {
        "duration": round(duration, 3),
        "size_bytes": int(data["format"].get("size", 0)),
        "width": video.get("width"),
        "height": video.get("height"),
        "fps": round(num / den, 3) if den else None,
        "video_codec": video.get("codec_name"),
        "audio_codec": audio.get("codec_name") if audio else None,
        "has_audio": audio is not None,
    }


# --- transcript ------------------------------------------------------------


def transcribe(model, path: pathlib.Path, duration: float) -> dict:
    """Word-level transcript with VAD.

    vad_filter is not optional. Whisper narrates confident text over ambient
    audio ("Thanks for watching!"), which would make a silent clip look like
    a talkative one and quietly corrupt every downstream decision.
    """
    segments, _ = model.transcribe(
        str(path), word_timestamps=True, vad_filter=True, language="en"
    )
    segments = list(segments)

    words = [
        {"word": w.word.strip(), "start": round(w.start, 3), "end": round(w.end, 3)}
        for s in segments
        for w in (s.words or [])
    ]
    speech = sum(s.end - s.start for s in segments)
    return {
        "text": " ".join(s.text.strip() for s in segments).strip(),
        "words": words,
        "word_count": len(words),
        "speech_seconds": round(speech, 2),
        "speech_ratio": round(speech / duration, 3),
    }


# --- visual ----------------------------------------------------------------


def grab_gray(path: pathlib.Path, at: float) -> np.ndarray:
    raw = run([
        "ffmpeg", "-nostdin", "-v", "error", "-ss", f"{at:.3f}", "-i", str(path),
        "-frames:v", "1", "-vf", f"scale={BLUR_W}:{BLUR_H}",
        "-pix_fmt", "gray", "-f", "rawvideo", "-",
    ]).stdout
    if len(raw) < BLUR_W * BLUR_H:
        raise RuntimeError(f"{path.name}: short frame read at {at:.2f}s")
    return np.frombuffer(raw[: BLUR_W * BLUR_H], dtype=np.uint8).reshape(
        BLUR_H, BLUR_W
    ).astype(np.float32)


def grab_jpeg(path: pathlib.Path, at: float, out: pathlib.Path) -> pathlib.Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    run([
        "ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{at:.3f}", "-i", str(path),
        "-frames:v", "1", "-vf", "scale=640:-2", str(out),
    ])
    return out


def blur_score(gray: np.ndarray) -> float:
    """Variance of the Laplacian. Low means soft, dark, or motion-blurred."""
    lap = (
        -4 * gray
        + np.roll(gray, 1, 0) + np.roll(gray, -1, 0)
        + np.roll(gray, 1, 1) + np.roll(gray, -1, 1)
    )[1:-1, 1:-1]
    return round(float(lap.var()), 1)


def load_vision():
    """Apple's on-device Vision framework. macOS only, no network, no model download."""
    try:
        import Quartz
        import Vision
    except ImportError as exc:
        raise RuntimeError(
            "Vision unavailable — install with: pip install pyobjc-framework-Vision "
            "pyobjc-framework-Quartz  (or pass --no-vision to skip visual analysis)"
        ) from exc
    return Quartz, Vision


def analyse_frame(quartz, vision_mod, img: pathlib.Path) -> dict:
    url = quartz.CFURLCreateWithFileSystemPath(
        None, str(img), quartz.kCFURLPOSIXPathStyle, False
    )
    handler = vision_mod.VNImageRequestHandler.alloc().initWithURL_options_(url, {})

    aesthetics = vision_mod.VNCalculateImageAestheticsScoresRequest.alloc().init()
    classify = vision_mod.VNClassifyImageRequest.alloc().init()
    faces = vision_mod.VNDetectFaceRectanglesRequest.alloc().init()
    handler.performRequests_error_([aesthetics, classify, faces], None)

    result = aesthetics.results()[0]
    return {
        "aesthetic": round(float(result.overallScore()), 3),
        "is_utility": bool(result.isUtility()),
        "labels": {
            o.identifier(): round(float(o.confidence()), 2)
            for o in classify.results()
            if o.confidence() > LABEL_MIN_CONFIDENCE
        },
        "faces": len(faces.results() or []),
    }


def analyse_visual(path: pathlib.Path, duration: float, frame_dir: pathlib.Path,
                   quartz, vision_mod) -> dict:
    """Sample several frames and summarise. Per-frame values are kept so the
    summary can be recomputed later without re-running this expensive pass."""
    frames = []
    for i, fraction in enumerate(SAMPLE_POINTS):
        at = duration * fraction
        jpeg = grab_jpeg(path, at, frame_dir / f"{path.stem}_{i}.jpg")
        frame = analyse_frame(quartz, vision_mod, jpeg)
        frame["at"] = round(at, 2)
        frame["blur"] = blur_score(grab_gray(path, at))
        frame["frame"] = str(jpeg)
        frames.append(frame)

    # Union of labels across frames, keeping the highest confidence seen.
    labels: dict[str, float] = {}
    for f in frames:
        for name, conf in f["labels"].items():
            labels[name] = max(labels.get(name, 0.0), conf)

    aesthetics = sorted(f["aesthetic"] for f in frames)
    blurs = sorted(f["blur"] for f in frames)
    return {
        "aesthetic": aesthetics[len(aesthetics) // 2],
        "aesthetic_min": aesthetics[0],
        "blur": blurs[len(blurs) // 2],
        "blur_min": blurs[0],
        "faces_max": max(f["faces"] for f in frames),
        "labels": dict(sorted(labels.items(), key=lambda kv: -kv[1])),
        "frames": frames,
    }


# --- driver ----------------------------------------------------------------


def find_clips(source: pathlib.Path) -> list[pathlib.Path]:
    if source.is_file():
        return [source]
    clips = sorted(
        p for p in source.iterdir()
        if p.is_file() and p.suffix.lower() in VIDEO_SUFFIXES
    )
    if not clips:
        raise SystemExit(f"no video files in {source}")
    return clips


SF_DATALESS = 0x40000000  # macOS: file is an iCloud placeholder, contents not local


def check_materialised(clips: list[pathlib.Path]) -> None:
    """iCloud-offloaded files read as placeholders and block on download.

    They do not fail — they hang, which is worse. Catch it before a long run.
    """
    offloaded = [p.name for p in clips if p.stat().st_flags & SF_DATALESS]
    if offloaded:
        raise SystemExit(
            f"{len(offloaded)} of {len(clips)} file(s) are iCloud placeholders, "
            f"not downloaded locally: {', '.join(offloaded[:5])}"
            f"{' ...' if len(offloaded) > 5 else ''}\n"
            "Download them in Finder first, or reads will stall mid-run."
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", type=pathlib.Path, help="folder of clips, or one clip")
    parser.add_argument("--index", type=pathlib.Path, default=pathlib.Path("index"))
    parser.add_argument("--frames", type=pathlib.Path, default=pathlib.Path("work/frames"))
    parser.add_argument("--model", default="large-v3", help="whisper model (default: large-v3)")
    parser.add_argument("--limit", type=int, help="only process the first N clips")
    parser.add_argument("--force", action="store_true", help="re-process clips already indexed")
    parser.add_argument("--no-vision", action="store_true", help="skip visual analysis")
    args = parser.parse_args()

    if not args.source.exists():
        raise SystemExit(f"{args.source} does not exist")

    clips = find_clips(args.source)
    check_materialised(clips)
    if args.limit:
        clips = clips[: args.limit]

    args.index.mkdir(parents=True, exist_ok=True)
    pending = [p for p in clips if args.force or not (args.index / f"{p.stem}.json").exists()]
    skipped = len(clips) - len(pending)

    print(f"{len(clips)} clip(s); {skipped} already indexed, {len(pending)} to process")
    if not pending:
        return

    quartz = vision_mod = None
    if not args.no_vision:
        quartz, vision_mod = load_vision()

    print(f"loading whisper model '{args.model}' ...")
    from faster_whisper import WhisperModel

    model = WhisperModel(args.model, device="cpu", compute_type="int8")

    started = time.time()
    for i, path in enumerate(pending, 1):
        t0 = time.time()
        info = probe(path)
        if not info["has_audio"]:
            print(f"[{i}/{len(pending)}] {path.name}: no audio stream", file=sys.stderr)

        record = {
            "id": path.stem,
            "source": str(path),
            "indexed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "model": args.model,
            **info,
        }
        record["transcript"] = (
            transcribe(model, path, info["duration"])
            if info["has_audio"]
            else {"text": "", "words": [], "word_count": 0,
                  "speech_seconds": 0.0, "speech_ratio": 0.0}
        )
        if vision_mod is not None:
            record["visual"] = analyse_visual(
                path, info["duration"], args.frames, quartz, vision_mod
            )

        (args.index / f"{path.stem}.json").write_text(json.dumps(record, indent=2))

        t = record["transcript"]
        v = record.get("visual", {})
        print(
            f"[{i}/{len(pending)}] {path.name}  {info['duration']:6.1f}s  "
            f"{t['word_count']:4} words ({t['speech_ratio']:.0%})  "
            f"aesth={v.get('aesthetic', float('nan')):+.2f}  "
            f"blur={v.get('blur', float('nan')):7.1f}  "
            f"({time.time() - t0:.1f}s)"
        )

    elapsed = time.time() - started
    print(f"\n{len(pending)} clip(s) in {elapsed / 60:.1f} min -> {args.index}/")


if __name__ == "__main__":
    main()

# CLAUDE.md

Corpus-scale vlog editor. Takes a folder of ~130 raw vlog files and produces an
ordered EDL that renders into one coherent video.

The hard part is **cross-file narrative selection**: deciding which takes to keep,
in what order, and where to cut. Existing tools solve per-file editing. They do not
solve this. That gap is the whole point of this repo.

## Pipeline

```
raw/*.mp4
  -> transcribe   (faster-whisper, word-level timestamps)  -> index/<id>.json
  -> cards        (one compact summary per video)          -> index/cards.json
  -> select       (Claude reasons across cards)            -> edl.json
  -> render       (ffmpeg / mcp-video)                     -> out/final.mp4
```

Each stage reads files and writes files. No stage holds state in memory across runs.

## Non-negotiables

- **IMPORTANT: never write to `raw/`.** Originals are irreplaceable. All output
  goes to `index/`, `work/`, or `out/`.
- **Word-level timestamps or nothing.** Segment-level cuts sound chopped. WhisperX
  or faster-whisper with alignment enabled.
- **`edl.json` is the deliverable of the selection stage**, not a rendered video.
  It must be human-readable and hand-editable. Render is a separate command.
- **Every EDL entry carries a `reason` field.** If a cut can't be justified in a
  short phrase, it's a guess and should be flagged rather than silently included.
- Cuts land inside silence, never mid-word. Audio crossfade ~30ms at every splice.

## EDL format

```json
[
  {"source": "raw/vlog_042.mp4", "start": 12.40, "end": 48.15,
   "reason": "clean intro, best of 3 takes"}
]
```

Timestamps are seconds, float, relative to the source file. Order in the array is
order in the output.

## Card format

Cards are what Claude reads to make selection decisions. All ~130 must fit in one
context window together, so keep them small. Full transcripts are fetched on demand
only for shortlisted files.

Per card: source path, duration, one-line topic, 2-3 line summary, quality flags,
timestamps of obvious fumbles or restarts.

## Conventions

- Python 3.11+. Standard library plus faster-whisper and ffmpeg-python. Resist
  adding dependencies.
- **Use the simplest approach that works.** No class hierarchies, no plugin systems,
  no abstraction layers for a single implementation. This is a personal tool.
- Each stage is a standalone script runnable on its own. No orchestration framework.
- Transcription is expensive and idempotent — always check for an existing
  `index/<id>.json` and skip rather than recompute.
- Fail loudly on a bad file. Do not silently skip and produce a short video.

## Commands

```bash
python transcribe.py raw/          # populate index/, skips existing
python cards.py                    # index/*.json -> index/cards.json
python render.py edl.json out/final.mp4
```

## What Claude does not do

I cannot see the footage. All reasoning is from transcripts. A take that reads well
but is visually bad (off-camera gaze, bad framing) will pass through. Assume every
EDL needs human review before render.

## Context

- `mcp-video` is now **`kinocut`** (KyaniteLabs, Apache-2.0) — same repo, renamed.
  Wraps ffmpeg with typed MCP tools and has a usable EDL/approval layer. ~141 stars,
  actively maintained. Optional — plain ffmpeg is the real dependency and the fallback.
- Its semantic index stores and queries a supplied index; it does not build one, and
  it binds one index per source file. There is no cross-corpus layer. That's ours.
- Evaluated and rejected: Clipto (subscription), Video Jungle (hosted API),
  Descript (paid tiers gate the AI features — now also an official Claude connector,
  but the pricing objection stands).
- Surveyed 2026-09-07 and rejected for this use: Adobe's official "Adobe for
  creativity" connector (hosted, asset-upload, usage-limited — wrong shape for 130
  local files), DaVinci Resolve MCP (drives a GUI NLE; we want headless files),
  Premiere Pro MCPs (community, largely scaffolded).
- **OpenTimelineIO** (Pixar → ASWF, Apache-2.0, `pip install OpenTimelineIO`) is the
  real industry format for timeline interchange, and it round-trips to FCPXML and
  Resolve. Worth adding later as an *export target* so an EDL can open in a real NLE.
  Not a replacement for `edl.json` — OTIO JSON is too verbose to hand-edit, and
  hand-editability is the point.
- No tool found solves cross-file narrative selection over a corpus. Corpus-scale
  tooling that exists is for logging and prep, not for choosing takes. The gap is real.

## Working state

Moving state — current phase, open questions, what broke last run — lives in
`NOTES.md`, not here. Read it at the start of a session. Keep this file for rules
that stay true across sessions.

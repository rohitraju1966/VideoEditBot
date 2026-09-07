# VideoEditBot

A corpus-scale vlog editor. It takes a folder of ~130 raw vlog files and produces
an ordered edit decision list that renders into one coherent video.

The hard part is **cross-file narrative selection**: deciding which takes to keep,
in what order, and where to cut. Existing tools solve per-file editing well. None
of them solve selection across a whole corpus. That gap is the reason this repo
exists.

> **Status: scaffolding.** The pipeline described below is the design, not yet the
> implementation. No stage is built. See [NOTES.md](NOTES.md) for where things
> actually stand.

## How it works

```
raw/*.mp4
  │
  ├─ transcribe  faster-whisper, word-level timestamps  →  index/<id>.json
  ├─ cards       one compact summary per video          →  index/cards.json
  ├─ select      Claude reasons across all cards        →  edl.json
  └─ render      ffmpeg                                 →  out/final.mp4
```

Each stage reads files and writes files. No stage holds state in memory across
runs, and each is runnable on its own — there is no orchestration framework.

Why the split matters: **selection is the deliverable, not the render.** The
`select` stage emits an `edl.json` that you read and edit by hand before anything
gets encoded. Rendering is a separate command you run once you trust the cuts.

### Why cards

All ~130 summaries have to fit in one context window together, because choosing
take 3 of the coffee-shop bit over take 1 requires seeing both at once. Cards are
the compression that makes that possible. Full transcripts are fetched on demand,
only for the files that make the shortlist.

## Requirements

- Python 3.11+
- ffmpeg (`brew install ffmpeg`)
- faster-whisper
- Dependencies beyond the standard library are resisted on purpose. Standard
  library, plus faster-whisper and ffmpeg-python.

## Usage

```bash
python transcribe.py raw/          # populate index/, skips existing
python cards.py                    # index/*.json -> index/cards.json
python render.py edl.json out/final.mp4
```

Transcription is expensive and idempotent — it checks for an existing
`index/<id>.json` and skips rather than recomputing.

## Formats

Both output formats are plain JSON, on purpose: you are expected to open them.

### `edl.json`

```json
[
  {
    "source": "raw/vlog_042.mp4",
    "start": 12.40,
    "end": 48.15,
    "reason": "clean intro, best of 3 takes"
  }
]
```

Timestamps are floats in seconds, relative to the source file. Order in the array
is order in the output.

Every entry carries a `reason`. If a cut cannot be justified in a short phrase,
it is a guess, and it gets flagged rather than quietly included.

### Cards

One per video: source path, duration, a one-line topic, a 2–3 line summary,
quality flags, and timestamps of obvious fumbles or restarts. Kept small so all
of them fit in context together.

## Rules

- **Never write to `raw/`.** Originals are irreplaceable. Everything this tool
  produces goes to `index/`, `work/`, or `out/`.
- **Word-level timestamps or nothing.** Segment-level cuts sound chopped.
- **Cuts land inside silence, never mid-word.** ~30 ms audio crossfade at every
  splice.
- **Fail loudly on a bad file.** Do not silently skip it and hand back a short
  video.

## Known limitation

Claude cannot see the footage. Every decision is made from transcripts, so a take
that reads well but looks bad — off-camera gaze, bad framing, someone walking
through the shot — will pass straight through the filter.

**Assume every EDL needs human review before render.** That is not a temporary
gap; it is the shape of the tool.

## Repo layout

```
CLAUDE.md          rules that stay true across sessions
NOTES.md           moving state: current phase, open questions, what broke
.claude/skills/    vendored coding standards (see PROVENANCE.md)
raw/               source footage — gitignored, never written to
index/             transcripts and cards — gitignored
work/              intermediate artifacts — gitignored
out/               rendered video — gitignored
```

Footage and everything derived from it are gitignored. Nothing large should ever
reach a commit.

## License

Not yet chosen.

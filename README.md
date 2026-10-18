# Video Editor — an AI vlog-editing skill for Claude

Hand Claude a folder of phone clips and get back a finished, YouTube-ready vlog: story structure,
tight jump cuts, synced captions, beat-matched montages, a proper music mix, subtle color, titles,
your channel intro/outro, a 4K export, thumbnails and a social trailer — with short previews to review
along the way.

It runs **entirely on your Mac**: ffmpeg + VideoToolbox for video, `mlx-whisper` for speech-to-text,
Pillow for graphics, Apple Vision for thumbnail cut-outs. No footage leaves your machine.

Built while editing a real 10-minute New York travel vlog for the
Frost Tube channel — every rule in the skill comes from a real review round,
and every bug it guards against actually happened (see
[`vlog-editor-skill/references/lessons.md`](vlog-editor-skill/references/lessons.md)).

## What it does

| Stage | How |
|---|---|
| Understand footage | inventory (length, fps, rotation, HDR, audio, time, GPS) + contact sheets; parse an existing DaVinci timeline |
| Find the story | local transcription with word timestamps; reads transcripts like a script |
| Edit | a Python *plan* (talk / B-roll / sections / music) → `plan.json` |
| Render | per-shot GPU HDR→SDR tone-mapping, rotation fixes, grade, captions & titles, transitions, slow-mo/ramps, cached and length-verified |
| Music | beat analysis, cuts on the beat, songs carried across sections, dips under speech, two-pass loudness (-14 LUFS) |
| Check | clipped words, mid-sentence endings, caption proof-read, vertical clips in montages, songs running out, A/V drift, frame gaps |
| Package | 4K HEVC export, house-style thumbnails with subject cut-out, research-backed titles, horizontal trailer |
| Clean up | after posting, frees the GBs of caches — keeps finals, thumbnails and re-editable plans |

## Requirements

- macOS on Apple Silicon (VideoToolbox HDR tone-mapping, mlx-whisper, Apple Vision)
- [Claude Code](https://claude.com/claude-code) (CLI or desktop app)
- `ffmpeg` (Homebrew: `brew install ffmpeg`), Python 3.10+, Xcode command-line tools (`swiftc`)

## Install

```bash
git clone https://github.com/rohitraju1966/VideoEditBot.git "$HOME/Desktop/Video Editor"   # or anywhere you like
cd "$HOME/Desktop/Video Editor"
./setup.sh
```

`setup.sh` creates a Python venv (`~/.vlog-editor-venv`) with `mlx-whisper`, `numpy`, `Pillow`; builds the
Apple Vision cut-out tool; and links the skill into `~/.claude/skills/vlog-editor` so Claude Code picks it up.
The Whisper model (~1.6 GB) downloads on first transcription.

## Use

In Claude Code, just ask:

> "Edit my New York trip into a vlog — clips are in ~/Downloads/NYC clips, music in the Video Editor music folder."

Claude will inventory the footage, propose a structure, then send ~1.5-minute preview parts as they render.
Give notes with timestamps; only the changed shots re-render. When you're happy it renders 4K, makes
thumbnails, and (optionally) a trailer. After you post: "the video is posted — clean up".

### Make it yours: a channel profile

Copy `vlog-editor-skill/profiles/example.md` to `profiles/<your-channel>.md` and fill in your name
spelling, intro/outro asset, tone (e.g. family-friendly), thumbnail house style and preferences. Profiles are
gitignored — your channel stays private.

## Folder layout

```
Video Editor/
├── vlog-editor-skill/        the skill (committed)
│   ├── SKILL.md              workflow + editing rules Claude follows
│   ├── scripts/              render engine and tools
│   ├── references/           lessons learned, plan format, titles & thumbnails
│   ├── profiles/example.md   template (your own profile is gitignored)
│   └── examples/             a complete example plan
├── assets/                   your intro/outro, logos         (gitignored)
├── music/                    your reusable music library     (gitignored)
└── projects/<Video Name>/    plans, finals, thumbnails       (gitignored)

~/Movies/Video Editor Cache/  transcripts + render caches — local only, never synced
```

> Desktop/Documents are often iCloud-synced on macOS. Render caches live in `~/Movies/...` so multi-GB
> intermediates never upload. Move footage into a synced archive only after the final render.

## Scripts

| script | purpose |
|---|---|
| `render.py` | plan.json → video (`--res 1080/2160`, `--only` sections for previews) |
| `planlib.py` | helpers to write plans: `talk`, `broll`, `sec`, `T`, `clean_montage`, `add_asides`, `pick`, `write_plan` |
| `clips.py` | footage inventory, contact sheets, frame grids |
| `transcribe.py` | mlx-whisper transcripts; `--snippet` to hear what's inside a cut |
| `beats.py` | tempo / first beat / energy per track |
| `check_plan.py` | pre-render checklist (+ `--captions` proof-read) |
| `verify.py` | cut waveforms, output A/V sync & loudness, level plots, still frames |
| `thumbnail.py`, `cutout.swift` | stills, subject cut-out, house-style thumbnails |
| `cleanup.py` | free space after posting |

## Contributing

Issues and PRs welcome — especially new lessons (what broke, why, the fix) for `references/lessons.md`.
Please don't commit footage, music or personal profiles.

## License

MIT — see [LICENSE](LICENSE). Music, footage and channel assets you use with it remain yours and are not covered.

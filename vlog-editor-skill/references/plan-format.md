# plan.json format

`render.py` reads a plan; `planlib.py` writes it. You normally only touch shots via `talk()`, `broll()`,
`T()` and `sec()`, but these are the keys the renderer understands.

## Top level
| key | meaning |
|---|---|
| `project` | name; default cache = `~/Movies/Video Editor Cache/<project>/` |
| `clipinfo` | path to probed clip info (`w,h,fps,rot,dur,sdr,audio` per clip) |
| `tx_for` | clip path → transcript JSON |
| `music_dir`, `tracks` | `{key: {file, bpm, first_beat, dur}}` |
| `sections` | ordered list (below) |
| `fixes` | caption corrections `{"misheard phrase": "right phrase"}` (whole words, applied across chunks) |
| `duck` | side-chain settings (default gentle; trailers use even gentler) |
| `out`, `work_dir` | default output file and cache dir |

## Section
| key | meaning |
|---|---|
| `name`, `segments` | id + shots |
| `music` | track key or null (silence) |
| `music_beat` / `music_offset` / `music_continue` | where the song starts: beat n / absolute seconds / carry on from the previous section using this song |
| `music_level` | bed level under speech (0.06-0.15 typical) |
| `music_broll` | bed level between lines (0.85); omit for montage sections |
| `music_fade_in`, `music_fade_out` | seconds |
| `no_duck` | speech here does not duck the music (cold opens, trailers) |
| `repeat_ok` | this section deliberately reuses a stretch of a song already heard |
| `snap_after_talk` | next beat-cut after a dialogue line lands back on the beat grid |

## Shot (segment)
| key | meaning |
|---|---|
| `src`, `start`, `end` | source file and seconds |
| `voice` | speech shot (captioned, music dips) vs B-roll |
| `beats` | length in music beats (cuts on the beat); start/end then mark the window it's taken from |
| `speed` | 0.5 = slow-mo (audio muted); `ramp: [fast, slow, frac]` speed ramp |
| `cine` | 2.39 bars + film grade (set by `sec()` on B-roll) |
| `grade` | `"bold"` for the opening montage look |
| `raw` | channel graphics / memes: no grade, no bars |
| `punch`, `focus: [fx, fy]` | static zoom-in (1.12 jump-cut punch; 1.6-2.6 comedic) framed on the face |
| `zoom` | slow push-in factor; `tilt: "up"` bottom-to-top reveal |
| `pulse`, `shake`, `flash` | accents -- sparingly |
| `tr_in`, `tr_out` | `whip`, `zoom`, `leak`, `glitch` |
| `vol` | clip audio level (B-roll default 0.05 in montages; 0 to mute) |
| `rot` | override a wrong rotation flag |
| `captions: false` | no auto captions (use `text` instead) |
| `mute_after` | source second after which the voice fades out (picture continues); captions stop too |
| `fade_in`, `fade_out` | picture fades |
| `verified` | cut points confirmed by ear -- check_plan.py stops re-flagging them (set by `start_at`/`end_at`) |
| `text` | overlays `[a, b, text, kind]` -- seconds into the shot |

## Overlay kinds
`caption` (auto subtitles style) · `pop` (yellow callout, top) · `title` (big letter-spaced) · `sub`
(subtitle under a title) · `loc` (`"Place|detail"` lower-left location tag) · `aside` (`*italic yellow*`,
emoji supported) · `endcard` (`"TOP LINE|BIG|signature"`). Titles/loc/aside/endcard fade in and out.

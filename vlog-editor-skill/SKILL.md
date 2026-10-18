---
name: vlog-editor
description: Edit raw phone/camera footage into a finished, YouTube-ready vlog or travel video on macOS -- cuts, captions, beat-synced montages, music mixing, color, titles, channel intro/outro, 4K export, thumbnails and a social trailer. Use this whenever someone wants a video or vlog edited, cut, re-edited, captioned, color graded, synced to music, turned into a trailer/reel, or wants a thumbnail/title for a video, or mentions a folder of clips/footage (iCloud Photos export, DaVinci/Premiere timeline, .MOV files) they want "made into a video" -- even if they never say "skill" or name a tool. Also use it when a video is posted and they want the leftover editing space cleaned up.
---

# Vlog Editor

Turn a pile of clips into a vlog people want to watch -- and keep the person in the loop with short previews
instead of one long render. Everything runs locally: ffmpeg + VideoToolbox for video, mlx-whisper for speech,
Pillow for graphics, Apple Vision for thumbnail cut-outs.

Run every script with the skill's Python: `~/.vlog-editor-venv/bin/python` (created by `setup.sh`; the
system `python3` usually lacks numpy/Pillow/mlx-whisper).

The engine (scripts/) took a long, painful project to get right. **Use it; don't rewrite it.** Most early
failures in that project came from hand-rolled ffmpeg commands (washed-out HDR, audio drifting ahead of the
picture, songs bleeding across cuts). Every one of those is now handled in `render.py` -- see
`references/lessons.md` for what went wrong and why the engine does what it does.

## Before anything: kickoff questions (profile + brief)

A few minutes of questions up front saves hours of review rounds -- most fixes in past projects were
preferences nobody had asked about yet. Use the ask-the-user tool if available (multiple choice + "other"),
and keep it to what you can't infer.

**First project with a channel -- build the channel profile** (`profiles/<channel>.md`, from
`profiles/example.md`; personal, gitignored): creator name *spelling*, channel name, audience/tone
(family-friendly?), intro/outro asset and where each goes, pacing taste, caption style, grade, music
sources, thumbnail house style (ask for a screenshot of their channel page), where footage should be
archived, and anything they already know they dislike.

**Every project -- a short brief** (`projects/<Name>/brief.md`), confirming rather than re-asking what the
profile covers:
- What is it and why should viewers care (the trip's purpose, the story)? Target length and platform.
- Where are the clips (and any extra clips from friends)? An existing timeline (optional -- see step 1)?
- Must-include moments, people to feature, things to leave out (work/office, private, off-tone lines).
- Music they want (or let you suggest), memes/GIFs they plan to add.
- Deliverables: 4K final? thumbnail + title research? social trailer (format)?

Read the profile before every session and update it whenever the creator states a lasting preference --
they should never have to repeat feedback. Profile and brief override the defaults below.

## Workspace layout

```
<Video Editor>/                     # the creator's editing workspace (this skill lives inside it)
  assets/        channel intro/outro, logos            (gitignored)
  music/         reusable music library + music_log.md  (gitignored)
  projects/<Name>/  plan.py, plan.json, final videos, thumbnails/, previews/   (gitignored)
~/Movies/Video Editor Cache/<Name>/  transcripts, clip info, rendered-shot cache  (LOCAL ONLY)
<footage>      wherever the clips are; after the final render, move into the creator's archive folder
```

Desktop and Documents are often iCloud-synced on Macs: never put render caches there (GBs of intermediates
would upload). Only move footage into a synced archive **after** the final render -- iCloud may evict local
copies, and re-downloading 20 GB mid-edit stalls everything.

## Workflow

### 1. Understand the footage (don't edit blind)
- `scripts/clips.py inventory <dirs>` -- length, fps, rotation, HDR, audio, time, GPS for every clip.
  Group by GPS/time into places and days; that is your story skeleton.
- `scripts/clips.py sheets <out> <dirs>` and look at the sheets. Note hero shots, faces, food, landmarks,
  friends, and which clips are vertical, shaky, or "random buildings".
- An existing timeline is **optional**. Without one, select from transcripts + contact sheets + GPS/time
  groups. If they do have one (DaVinci `.drt` is a zip of XML; FCPXML/EDL also work), parse it: it shows
  which clips *they* already liked -- a head start, not a constraint (better shots often hide in the rest).
- `scripts/transcribe.py --cache <cache> <clips with speech>` (one job at a time on 8 GB Macs). Read the
  transcripts like a script -- the best vlog moments are in the words.
- Check free disk space and memory early (`df -h ~`); a 10-minute 4K job needs ~6 GB free.

### 2. Propose the story, then build the plan
Write `projects/<Name>/plan.py` with `scripts/planlib.py` (see `references/plan-format.md` and
`examples/plan_example.py`). A structure that worked:
1. **Cold open** -- the single best reaction line (a few seconds), punch-in on the payoff word.
2. **Title montage** -- 15-20 s, the *best of the trip* (places + food + friends' faces + reactions), clean
   hard cuts on the beat of an upbeat track, big title + subtitle on the first shot. Music starts softly
   from the very first second (under the cold open, `no_duck=True`) and lands on the beat as the title hits.
3. **Channel intro sting** (from the profile), music fading out across it.
4. **Context** -- why/where/how long ("going for a demo, two days"). Without it viewers don't know why to care.
5. **The trip, in order**, as mini-stories (arrival, each place, food, night...), each opened with B-roll and
   a location tag, talking parts tightened with jump cuts, short B-roll montages between places.
6. **Outro** -- the last great reaction, an end title over a wide shot, then the channel end screen (>= 5 s).

Scale this to the job: a 1-minute single-place draft is just a short teaser, the place as a mini-story,
and the channel outro -- skip the title montage and trip context. Channel assets from the profile
(sting, end screen) still apply unless the brief says otherwise.

Tell the creator the structure in plain words before rendering big changes -- especially when they ask
"what are you planning?" Rendering first and explaining later wastes their time.

### 3. Render in short parts and send them as they finish
- `scripts/render.py plan.json --res 1080 --only <sections> --out previews/partN.mp4` for ~1.5-2 min parts.
  Send each part as soon as it is verified; the creator reviews part by part. Shots are cached, so a
  change re-renders only what changed (minutes, not the whole video).
- Before sending anything: `scripts/check_plan.py plan.json --only ... --captions` (clipped words,
  mid-sentence endings, vertical B-roll, whips on talking, songs running out/repeating) and
  `scripts/verify.py output <file>` (frame gaps, A/V sync, loudness). Look at a few frames too.
- When a fix is ambiguous ("there's an issue at 0:50"), map the timestamp to the shot and *listen/look*
  (`verify.py cut`, `transcribe.py --snippet`) before changing anything; say what you found.

### 4. Final
- `render.py plan.json --res 2160 --out "<Name> FINAL 4K.mp4"` (HEVC, -14 LUFS), then `verify.py output` with
  the render's `list_*.txt` to confirm per-shot A/V drift is a few ms.
- **Title + thumbnail (research first, never guess)** -- follow `references/thumbnails-and-titles.md`:
  pull view counts for similar videos, pick a title pattern that fits what the video actually delivers,
  build 2 house-style thumbnail variants (subject cut-out over a context background, text that adds to the
  title), recommend one and suggest A/B testing the other in YouTube Studio.
- Optional social trailer: reuse the opening montage + 3-4 dialogue beats; music loud and continuous;
  end on the title alone.
- Move footage to the archive folder, music to `music/` (+ log which tracks this video used).

### 5. After it's posted
`scripts/cleanup.py "<Name>"` shows what it would free (shot caches, previews, review copies) and asks first.
Finals, thumbnails, plan files, transcripts, footage and the music library are kept.

## Editing rules (defaults -- the profile can override)

These came from real review rounds; the reasons matter more than the rules.

**Speech**
- Never clip a word or end a line mid-sentence. Whisper's word times drift (early after pauses, stretched on
  drawn-out words), so confirm important cut points with `verify.py cut` (loudness every 50 ms) and
  `transcribe.py --snippet` (which words are really inside the cut). Use `end_at=`/`start_at=` to pin them.
- Cut dead air (nose-wipes, "uh" pauses) but keep natural rhythm (gaps < ~0.6 s).
- If speech runs on into something you don't want ("...parlor and sh*t, but"), let the picture breathe and
  fade the voice (`mute_after=`) instead of chopping mid-flow.
- Keep the lines that give context; drop lines that are factually wrong, rude, or "attitude" for a
  family-friendly channel -- cutting beats on-screen corrections, which tend to feel smug.

**Captions**
- Must match what's said *and* appear when it's said (the engine snaps each caption to the real voice
  onset). If whisper's word times are badly wrong for one shot (a restart smeared across words), set
  `captions=False` on that shot and place the words by hand with `T(a, b, "...", "caption")`.
  Keep `fixes` to word corrections -- adding punctuation there splits caption chunks. Proof-read every caption (`check_plan.py --captions`): names, places, numbers ("4:30 a.m.",
  "$5.00"), and whisper mishearings go in `fixes`. Spell the creator's name the way the profile says.

**Pacing & montages**
- Energetic, but not frantic: 0.35-0.7 s cuts everywhere felt "too fast". Build montages: longer opening
  shots, then shorter, a peak, then something that breathes (a slow-mo moment, a crowd wide shot).
- Short B-roll "blips" between lines make the music pump up and down. Either make the montage a real
  3+ s moment or drop it.
- Show what's being talked about (the building, the dish) and let key moments finish (a full tilt to the
  top, a performer's whole run-up and jump in slow-mo).

**Shots**
- Montages are 16:9: no vertical clips there. No shots where a friend is just a torso -- show faces. No
  "random buildings"; prefer landmarks, food, people, reactions. Verify a landmark is the landmark (GPS).
- Live Photo clips are short, SDR and silent -- usable, but the engine needs to know (it detects them).

**Look**
- Subtle, natural grade for most of the video; the bold teal/orange look only in the opening montage.
  iPhone HDR already looks vivid once tone-mapped; extra saturation reads amateur.
- 2.39 letterbox bars on cinematic B-roll; talking shots full frame.
- Transitions sparingly: mostly clean cuts on the beat; at most one light-leak; occasional whip/zoom between
  two B-roll shots only. Repeated shakes, glitches and zoom-thumps "look forced".

**Music**
- Low under speech, fuller between lines -- but only for B-roll stretches of 3+ s (shorter gaps cause pumping).
- One song carries through related sections (`music_continue`); never restart or jump back; an outgoing
  song fades *before* the cut (nothing bleeds into the next section); a song must not run out mid-section.
- Tracks with vocals clash with talking; the creator may still choose one -- then keep it very low under speech.
- Suggest where to find music (e.g. YouTube Audio Library: mood, genre, BPM, no vocals) rather than guessing;
  copyrighted chart music gets videos claimed.

**Comedy & memes**
- Short meme clips the creator supplies (1.5-2.5 s) at a comedic beat, music dropped out around the beat,
  then slam back in. Big zoom-ins on a punchline line work well.
- Custom animated "explain the joke" cards and narrator asides mostly felt cringe; one tiny wink
  ("*pun intended* 🍦") was liked. Default to fewer.

**Facts**
- Check every place name, title and claim on screen (and the creator's spoken claims) before the final;
  flag anything a commenter would correct. Ask, don't silently change their words.

## Communicating
- Short, concrete status; honest time estimates (measure render pace instead of guessing).
- When you find a bug in your own work, say so plainly, fix it, and add a check so it can't recur.
- Don't make the creator repeat feedback: keep a running checklist from their notes and run it before
  every preview. Save durable preferences into their channel profile.

## Reference files
- `references/lessons.md` -- every failure from real projects, its cause, and the fix (read when something
  looks/sounds wrong, or before changing render.py)
- `references/plan-format.md` -- shot/section/overlay keys the renderer understands
- `references/thumbnails-and-titles.md` -- research-backed title & thumbnail process, house style
- `examples/plan_example.py` -- a complete small plan to copy from

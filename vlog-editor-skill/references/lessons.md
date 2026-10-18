# Lessons from real projects

Each entry: what happened → why → what the engine/workflow now does. Read the relevant section when
something looks or sounds wrong, and before changing `render.py`.

## Contents
1. Picture
2. Sound & sync
3. Music
4. Captions & transcription
5. Cutting speech
6. Shot choice & story
7. Process & tooling

---

## 1. Picture

**iPhone footage looked washed-out/grey.** iPhone records HLG HDR (`color_transfer=arib-std-b67`).
Treating it as SDR flattens it. → Decode with VideoToolbox and tone-map with
`scale_vt=...:color_transfer=bt709` (GPU, fast, best-looking of the options tried; the CPU `colorspace`
filter looked washed out). Export SDR bt709 so it looks right on every screen.

**Some clips rendered black / a montage cut short at 15 s.** A 1-second Live Photo clip was 8-bit SDR
(the HDR path's `format=p010le` download fails) and had **no audio stream** (`[0:a]` matched nothing).
→ Probe every clip: `sdr` clips take a plain decode path; clips without audio get `anullsrc` silence.

**Clips upside-down / sideways.** Rotation lives in side data (`-180`, `-90`). → Decode with
`-noautorotate` and apply `hflip,vflip` / `transpose` explicitly. Some clips carry a *wrong* flag (a
landscape video tagged -90 rendered vertical and "inverted") → per-shot `rot=0` override; check frames.

**Grade "too strong / not professional".** Extra saturation on top of tone-mapped HDR. → Subtle default
grade (contrast 1.03, no saturation boost, faint warm highlights); bold teal/orange only for the opening
montage (`grade="bold"`).

**"Shaking transitions look forced."** Zoom-thumps on every beat, shakes, glitches, whips everywhere.
→ Clean cuts on the beat; one light-leak in the opening; occasional whip/zoom between B-roll only
(`TRANSITION_EVERY=6`). Never a transition on a talking shot -- a blur over speech reads as a glitch.

**Text effects felt cringe.** An animated "FROST = ICE CREAM ...get it?" frost card explained a pun the
audience would get anyway; narrator asides ("*sad trombone*", "*it's Koreatown*") felt smug. → Default to
none; one tiny aside at most if the creator likes it.

## 2. Sound & sync

**Voice ahead of the picture, getting worse through the video (~0.85 s by the end).** Each shot was
encoded with `-frames:v n`; ffmpeg stops the moment the last video frame is written and drops the last
few audio packets. Over 160 shots the shortfall accumulated. → `fix_av_length()` pads every shot's audio
to its exact video length before concatenation; `verify.py output VIDEO list.txt` reports per-shot and total
drift (expect a few ms).

**Stray voices under B-roll** ("Yeah... this is..." before a line; wind on a skyline). → B-roll ambience
defaults to `vol=0.05` in montages; mute shots that carry speech/wind (`vol=0`).

**Cold open music inaudible.** The voice side-chain squashed the fading-in music under "what the hell
dude... WOW". → `no_duck=True` sections are excluded from the ducking key.

## 3. Music

**Music too loud under speech.** → Two-level bed: `music_level` under speech, `music_broll` between lines,
with 0.6 s fades. Plus a gentle side-chain and a two-pass linear loudnorm (-14 LUFS) so nothing pumps.

**Music pumping up and down.** 1-2 s B-roll gaps between lines each lifted the music. → Talk runs separated
by < 3 s are merged into one dip; better still, make real montages or drop the blips.

**Old song audible for a moment after a cut / "music hasn't started well".** Each section's track spilled a
1 s fade into the next section. → Outgoing songs fade *inside* their section (0.6 s) and stop at the cut.

**The same passage twice / music restarting.** Each section restarted its song at a fixed beat.
→ `music_continue=True` carries the song on; positions are computed on the full plan, so `--only` previews
sound exactly like the final. `check_plan.py` flags repeats.

**Silence for the last minute of a section.** The chosen start point + section length exceeded the song.
→ `check_plan.py` flags SONG RUNS OUT. Pick an earlier `music_beat` or another track.

**Cuts drifting off the beat after a continuing song or a dialogue line.** → The beat grid is computed from
the song's actual position (`lead`); `snap_after_talk=True` puts the next montage cut back on the grid.

## 4. Captions & transcription

**"explode Times Square" (was "explore"), "Joe's Bazaar", "Adnoyal" (Magnolia), "Babakitchi" (bb.q Chicken),
"Rohith" (Rohit).** Whisper mishears names and places. → Proof-read every caption; `fixes` are applied on
the word stream (so a phrase split across caption chunks still gets fixed).

**"5 p" / ".m." split; "Square by we I"; captions before the words.** Whisper tokenises "p .m.", "o 'clock";
its word starts are early after pauses. → Tokens are glued back; chunks are <= 3 words / 1.6 s, never split
numbers/times or proper-noun pairs; each chunk snaps to the measured voice onset; fillers (uh/um) hidden;
capitalise only after a real sentence end.

**"It's the best pizza" x6.** Whisper hallucinated repeats (zero-length words). → Keep only the clean take.

## 5. Cutting speech

**Endings clipped ("awesome" cut early, "And-" bleeding in).** Padding reached into the next word; or
whisper said the next word started earlier than it did. → Padding stops just before the next word; touching
words cut exactly at the boundary; important cuts verified on the waveform (`verify.py cut`) and with
`transcribe.py --snippet`, then pinned with `end_at=`/`start_at=`. `check_plan.py` flags clipped words and
mid-sentence endings.

**Abrupt cut at "...ice cream parlor"** (because "and sh*t, but" follows immediately). → Let the picture run
~0.5 s longer and fade the voice from the end of the wanted word (`mute_after=`).

## 6. Shot choice & story

- Viewers didn't know *why* the trip happened → keep context lines in the intro.
- "Random buildings" in the title montage → replace with food, landmarks, friends' faces, reactions.
- A friend shown as a torso, or a vertical clip in a 16:9 montage → never.
- A building talked about but not shown → show it first (tagged), then the line.
- A camera tilt cut before reaching the top / a performer cut before the jump → let the move finish;
  slow-mo the key moment (60 fps sources at 0.35-0.5x).
- Montage of 0.35-0.7 s cuts "too fast" → build it: long, medium, quick peak, breathe.
- Things the creator said that were wrong (food trucks "not in Austin" -- Austin is famous for them) or
  off-tone ("don't give an F") → cut them; fact-check every on-screen name/claim before the final.

## 7. Process & tooling

- **Render in parts, send as they finish.** One 35-minute render per feedback round was too slow.
- **"Tell me the plan first"** for ambiguous or large changes -- then render.
- **Half-written cache files** after stopping a render made the next run crash ("cached" shot unreadable).
  → shots render to `*.part.mov` and are renamed only when complete.
- **Parallel renders clobbered shared temp files.** → temp names include the output name.
- **8 GB RAM:** two whisper jobs at once filled swap and crawled; thumbnail extraction of 4K HEVC on 8
  threads starved everything. One heavy job at a time; use VideoToolbox decode for frames.
- **Disk:** check before 4K (needs ~6 GB). Swap grows when memory is short and eats free space.
- **Editing the plan with string replacement** once matched a substring inside another line and deleted a
  block. Use unique anchors, assert one match, and re-run the plan + `check_plan.py` after every edit.
- **`python3` may not be the one with numpy/Pillow** (system vs Anaconda vs venv). Use the venv from the
  README.
- **iCloud "dataless" files** (shown in `ls -lO`) hang ffprobe until downloaded; ask the creator to
  "Download Now" in Finder or copy the file locally.

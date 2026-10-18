"""planlib -- describe an edit in Python, write plan.json for render.py.

A project's plan.py imports this, lists sections of shots, and calls write_plan(). Typical use:

    from planlib import *
    P = Project("NYC Vlog", footage=["~/Downloads/iCloud Photos (unzipped)", "~/Downloads/Friend clips"],
                music_dir="~/Desktop/Video Editor/music")
    sections = [
        sec("teaser", [talk("IMG_4653", 1.3, 5.7)], music="mukbang", music_offset=1.45, no_duck=True),
        sec("title",  [broll("IMG_4393", 2, 9, beats=8, keep=True, text=[T(0.2, 2.7, "NEW YORK", "title")]),
                       broll("IMG_4440", 0, 8, beats=2, keep=True)], music="mukbang", music_continue=True),
    ]
    write_plan(P, sections, tracks={"mukbang": "Mukbang - The Soundlings.mp3"})

Shots are plain dicts (src/start/end/voice/...). The helpers below just make the common ones safely:
  talk()  -- speech from a clip, auto jump-cutting pauses, padded so sentence endings are never clipped
  broll() -- a montage shot, optionally `beats` long so cuts land on the music
  sec()   -- a section: one music decision + montage defaults (bars, sparing transitions, quiet ambience)
"""
import copy
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# pacing defaults (see references/lessons.md for why these values)
GAP = 0.6                     # cut pauses longer than this; shorter ones are natural speech rhythm
PAD_IN, PAD_OUT = 0.15, 0.4   # breathing room around speech -- never into a neighbouring word
PUNCH = 1.12                  # every other jump cut punches in slightly so talking doesn't feel static
TRANSITIONS = ["whip", "zoom"]  # subtle only; light-leak/glitch are one-off accents, never rotated in
TRANSITION_EVERY = 6          # at most one effect transition per this many montage cuts


class Project:
    """Where things live for one video.

    footage   -- folders searched (in order) when a shot names a clip, e.g. "IMG_4378"
    cache     -- local, NOT iCloud-synced dir for transcripts/clip info/render caches
    music_dir -- folder holding the tracks named in write_plan(tracks=...)
    assets    -- shared channel assets (intro/outro etc.), e.g. ~/Desktop/Video Editor/assets
    """

    def __init__(self, name, footage, music_dir, assets=None, cache=None, out_dir=None):
        self.name = name
        self.footage = [os.path.expanduser(f) for f in footage]
        self.music_dir = os.path.expanduser(music_dir)
        self.assets = os.path.expanduser(assets) if assets else None
        self.cache = os.path.expanduser(cache or f"~/Movies/Video Editor Cache/{name}")
        self.out_dir = os.path.expanduser(out_dir) if out_dir else os.getcwd()
        os.makedirs(os.path.join(self.cache, "tx"), exist_ok=True)
        self.info_path = os.path.join(self.cache, "clipinfo.json")
        self.info = json.load(open(self.info_path)) if os.path.exists(self.info_path) else {}
        global _P
        _P = self


_P = None


def probe(path):
    """Duration, size, fps, rotation flag, HDR-or-not, has-audio -- everything the renderer branches on."""
    j = json.loads(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=codec_type,width,height,r_frame_rate,color_transfer:stream_side_data=rotation:format=duration",
         "-of", "json", path], capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout)
    vs = [s for s in j["streams"] if s["codec_type"] == "video"][0]
    n, d = vs["r_frame_rate"].split("/")
    trc = vs.get("color_transfer", "")
    return dict(w=vs["width"], h=vs["height"], fps=round(int(n) / int(d), 2),
                rot=next((x["rotation"] for x in vs.get("side_data_list", []) if "rotation" in x), 0),
                dur=float(j["format"]["duration"]),
                sdr=trc not in ("arib-std-b67", "smpte2084"),        # Live Photos / graphics / memes
                audio=any(s["codec_type"] == "audio" for s in j["streams"]))


def clip(name):
    """Resolve a clip name ("IMG_4378", "IMG_4378.MOV" or a full path) to a path, probing it once."""
    path = os.path.expanduser(name)
    if not os.path.isabs(path):
        cands = [os.path.join(d, f) for d in _P.footage for f in os.listdir(d)
                 if os.path.splitext(f)[0] == os.path.splitext(name)[0] or f == name]
        if not cands:
            raise SystemExit(f"clip not found in footage folders: {name}")
        path = cands[0]
    if path not in _P.info:
        _P.info[path] = probe(path)
    return path


def asset(name):
    return clip(os.path.join(_P.assets, name))


def txpath(path):
    return os.path.join(_P.cache, "tx", os.path.splitext(os.path.basename(path))[0] + ".json")


def words(path):
    try:
        t = json.load(open(txpath(path)))
    except FileNotFoundError:
        return []
    return [w for s in t["segments"] if (s.get("nsp") or 0) < 0.6 for w in s.get("words", [])]


def talk(name, a, b, gap=GAP, text=None, end_at=None, start_at=None, **kw):
    """Speech in [a, b] (source seconds) as padded 'islands'; pauses longer than `gap` are jump-cut.

    end_at/start_at: hand-verified cut points (waveform / snippet transcription) that override
    whisper's word boundaries, which drift -- especially after pauses and on drawn-out words.
    text: overlays for the first island. Other kw (rot=, mute_after=, punch=...) go on every island.
    """
    path = clip(name)
    ws = [w for w in words(path) if w["start"] >= a - 0.1 and w["end"] <= b + 0.15 and w["word"].strip()]
    if not ws:
        out = [dict(src=path, start=a, end=b, voice=True, **kw)]
    else:
        isl = [[ws[0]["start"], ws[0]["end"]]]
        for w in ws[1:]:
            if w["start"] - isl[-1][1] > gap:
                isl.append([w["start"], w["end"]])
            else:
                isl[-1][1] = w["end"]
        dur = _P.info[path]["dur"]
        allw = [w for w in words(path) if w["word"].strip()]
        out = []
        for s, e in isl:
            # pad, but never into the previous/next spoken word; touching words cut exactly at the boundary
            nxt = min((w["start"] for w in allw if w["start"] >= e - 0.01), default=dur)
            prv = max((w["end"] for w in allw if w["end"] <= s + 0.01), default=0)
            s, e = max(0, min(s, prv + 0.03), s - PAD_IN), min(dur - 0.05, max(e, nxt - 0.06), e + PAD_OUT)
            if out and s <= out[-1]["end"]:
                out[-1]["end"] = e
            else:
                out.append(dict(src=path, start=round(s, 3), end=round(e, 3), voice=True, **kw))
        for k, o in enumerate(out):
            if k % 2 and "punch" not in o and _P.info[path]["rot"] not in (90, -90):
                o["punch"] = PUNCH
    if start_at is not None:
        out[0]["start"] = start_at
        out[0]["verified"] = True
    if end_at is not None:
        out[-1]["end"] = end_at
        out[-1]["verified"] = True
    if text:
        out[0]["text"] = text
    return out


def broll(name, a, b=None, beats=None, keep=True, **kw):
    """A montage/B-roll shot taken from around [a, b]. beats=n makes it exactly n music beats long
    (cuts land on the beat). keep=False halves the beat count for a faster feel.
    Useful kw: speed=0.5 (slow-mo, 60 fps sources), ramp=[fast, slow, frac], tilt="up", zoom=1.08,
    pulse/shake/flash (accents -- use sparingly), vol=0 (mute ambience), text=[T(...)], rot=0."""
    d = dict(src=clip(name), start=a, end=b if b is not None else a + 3, voice=False, **kw)
    if beats:
        d["beats"] = beats if keep else max(1, beats // 2)
    return [d]


def T(a, b, text, kind="pop"):
    """Overlay from a to b seconds into the shot. kinds: caption, pop, title, sub, loc ("Name|detail"),
    aside (*italic yellow*), endcard ("TOP|BIG|signature")."""
    return [a, b, text, kind]


_tr = [0]


def next_tr():
    t = TRANSITIONS[_tr[0] % len(TRANSITIONS)]
    _tr[0] += 1
    return t


def sec(name, shots, cine=True, flash_first=False, **kw):
    """A section = shots + one music decision.

    cine=True: B-roll shots get 2.39 bars + film look + quiet ambience (vol 0.05) and an effect transition
    only every TRANSITION_EVERY montage cuts. flash_first=True adds a white flash on the first B-roll shot.
    Music kw: music=<track key>, music_beat=n | music_offset=s | music_continue=True,
              music_level (under speech), music_broll (between lines), music_fade_in, music_fade_out,
              no_duck=True (music rides freely under speech, e.g. a cold open), snap_after_talk=True."""
    segments = [s for g in shots for s in g]
    if cine:
        brolls = [s for s in segments if not s["voice"] and not s.get("raw")]
        for s in brolls:
            s["cine"] = True
            s.setdefault("vol", 0.05)
        if brolls and flash_first:  # e.g. the title montage slamming in; not every section
            brolls[0].setdefault("flash", True)
        for k in range(1, len(segments)):
            x, y = segments[k - 1], segments[k]
            if x.get("cine") and y.get("cine") and k % TRANSITION_EVERY == 0:
                x["tr_out"] = y["tr_in"] = next_tr()
    return dict(name=name, segments=segments, **kw)


def clean_montage(section, keep_flash_first=True, leak_before=None):
    """Strip accents from a montage: hard cuts on the beat read as 'pro'; stacked effects read as forced.
    leak_before=<clip name>: one warm light-leak into that shot (a single accent is plenty)."""
    segs = section["segments"]
    for k, g in enumerate(segs):
        for fx in ("pulse", "shake", "tr_in", "tr_out", "whip_in", "whip_out"):
            g.pop(fx, None)
        if k > 0 or not keep_flash_first:
            g.pop("flash", None)
    if leak_before:
        i = next(i for i, g in enumerate(segs) if os.path.splitext(os.path.basename(g["src"]))[0] == leak_before)
        segs[i - 1]["tr_out"] = segs[i]["tr_in"] = "leak"


def add_asides(sections, asides, dur=1.8):
    """asides = [(clip name, source time the line ends, text)]. Pops in 0.15 s after the line,
    carries onto the next shot if the line ends near a cut, never stacks two at once."""
    flat = [g for s in sections for g in s["segments"]]
    for name, t_src, txt in asides:
        path = clip(name)
        k = next(i for i, g in enumerate(flat) if g["src"] == path and g["start"] - 0.05 <= t_src <= g["end"] + 0.05)
        g = flat[k]
        sp = g.get("speed", 1)
        a = (t_src - g["start"]) / sp + 0.15
        g.setdefault("text", []).append(T(a, a + dur, txt, "aside"))
        left = dur - ((g["end"] - g["start"]) / sp - a)
        if left > 0.3 and k + 1 < len(flat):
            flat[k + 1].setdefault("text", []).append(T(0.0, left, txt, "aside"))
    for g in flat:
        al = sorted([t for t in g.get("text", []) if t[3] == "aside"], key=lambda t: t[0])
        for p_, n_ in zip(al, al[1:]):
            p_[1] = min(p_[1], n_[0])


def section_transitions(sections):
    """Effect transitions across section boundaries -- only between two B-roll shots, never on speech
    or channel graphics (a whip over someone talking reads as a glitch)."""
    for prev, nxt in zip(sections, sections[1:]):
        a, b = prev["segments"][-1], nxt["segments"][0]
        if (prev.get("cine", True) and not a.get("raw") and not b.get("raw")
                and not a["voice"] and not b["voice"] and a.get("cine") and b.get("cine")):
            a["tr_out"] = b["tr_in"] = next_tr()


def pick(sections, name, start=None):
    """Copy an exact shot from the main edit (reuses its cached render), e.g. for a trailer."""
    path = clip(name)
    for s in sections:
        for g in s["segments"]:
            if g["src"] == path and (start is None or abs(g["start"] - start) < 0.05):
                g2 = copy.deepcopy(g)
                for k in ("t0", "frames", "tr_in", "tr_out", "fade_in", "fade_out"):
                    g2.pop(k, None)
                return [g2]
    raise SystemExit(f"pick: no shot {name} @ {start}")


def analyze_tracks(tracks):
    """tracks = {key: filename in music_dir}. Runs beats.py once per track (tempo, first beat, energy)."""
    out = {}
    for key, f in tracks.items():
        js = os.path.join(_P.cache, "music", f + ".json")
        if not os.path.exists(js):
            subprocess.run([sys.executable, os.path.join(HERE, "beats.py"), "--out", os.path.dirname(js),
                            os.path.join(_P.music_dir, f)], check=True)
        a = json.load(open(js))
        out[key] = dict(file=f, bpm=a["tempo"], first_beat=a["first_beat"], dur=a["dur"])
    return out


def write_plan(P, sections, tracks, fixes=None, out_name=None, path="plan.json", extra=None):
    """Write plan.json (+ a length report). fixes = {"misheard phrase": "correct phrase"} for captions."""
    trk = analyze_tracks(tracks)
    for s in sections:  # probe every source, including hand-written dicts (channel assets, memes)
        for g in s["segments"]:
            if g["src"] not in P.info:
                P.info[g["src"]] = probe(g["src"])
    section_transitions(sections)
    json.dump(P.info, open(P.info_path, "w"))
    plan = dict(project=P.name, clipinfo=P.info_path, music_dir=P.music_dir, tracks=trk, sections=sections,
                tx_for={p: txpath(p) for p in P.info}, fixes=fixes or {},
                work_dir=P.cache,
                out=os.path.join(P.out_dir, out_name or f"{P.name}.mp4"))
    plan.update(extra or {})
    json.dump(plan, open(path, "w"), indent=1)
    tot = 0
    for s in sections:
        d = sum((g["end"] - g["start"]) / g.get("speed", 1) if "beats" not in g
                else g["beats"] * 60 / trk[s.get("music") or next(iter(trk))]["bpm"] for g in s["segments"])
        tot += d
        print(f"{s['name']:16s} {d:6.1f}s  ({len(s['segments'])} shots)")
    print(f"TOTAL {tot / 60:.2f} min -> {path}")
    return plan

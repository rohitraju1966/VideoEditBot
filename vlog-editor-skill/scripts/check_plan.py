"""Pre-render checklist for a plan.json -- run it before every preview you send.

usage: python3 check_plan.py plan.json [--only sec1,sec2] [--captions]

Flags:
  CLIPPED WORD     a cut lands inside a word (by whisper timing -- confirm with verify.py cut/snippet;
                   whisper is often early, so a flag at a hand-verified end_at can be a false alarm)
  MID-SENTENCE?    a line ends without . ? ! and the next word follows within 0.5 s
  VERTICAL B-ROLL  portrait clip in a montage (looks bad in 16:9)
  NO AUDIO / SDR   Live Photo or graphics clip (fine if intended -- renderer handles them)
  WHIP ON TALK     effect transition on a speaking shot (reads as a glitch)
  SONG RUNS OUT    a section asks for more music than the track has (silence)
  SONG REPEATS     the same stretch of a track plays twice (mark a deliberate reuse with repeat_ok=True)
Shots marked verified=True (cut points confirmed by ear) are not re-flagged for clipped words/mid-sentence.
--captions prints every caption exactly as it will render, to proof-read names and mishearings.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plan")
    ap.add_argument("--only")
    ap.add_argument("--captions", action="store_true")
    a = ap.parse_args()
    plan = json.load(open(a.plan))
    info = json.load(open(plan["clipinfo"]))
    only = a.only.split(",") if a.only else None
    ns = {}
    exec(open(os.path.join(HERE, "render.py")).read().split("def grade_key")[0], ns)  # caption_chunks + seg_frames
    issues = 0
    for sec in plan["sections"]:
        if only and sec["name"] not in only:
            continue
        for sg in sec["segments"]:
            src, nm = sg["src"], os.path.basename(sg["src"])
            m = info[src]
            if not sg.get("voice"):
                if m["rot"] in (90, -90) and "rot" not in sg:
                    print("VERTICAL B-ROLL", sec["name"], nm); issues += 1
                continue
            if sg.get("tr_in") or sg.get("tr_out"):
                print("WHIP ON TALK", sec["name"], nm); issues += 1
            p = plan["tx_for"].get(src)
            if not p or not os.path.exists(p) or sg.get("captions") is False:
                continue
            ws = [w for s in json.load(open(p))["segments"] for w in s["words"] if w["word"].strip()]
            cut = [w["word"].strip() for w in ws if (w["start"] < sg["end"] - 0.02 and w["end"] > sg["end"] + 0.05)
                   or (w["start"] < sg["start"] - 0.05 and w["end"] > sg["start"] + 0.02)]
            inside = [w for w in ws if w["start"] >= sg["start"] - 0.05 and w["end"] <= sg["end"] + 0.05]
            nxt = [w for w in ws if w["start"] >= sg["end"] - 0.02 and w not in inside]
            if sg.get("verified"):  # cut points checked by ear (waveform/snippet) -- whisper timing is known to be off
                cut = []
            if cut:
                print(f"CLIPPED WORD {sec['name']} {nm} {sg['start']:.2f}-{sg['end']:.2f} {cut}"); issues += 1
            if inside and inside[-1]["word"].strip()[-1:] not in ".?!" and nxt and nxt[0]["start"] - inside[-1]["end"] < 0.5 \
                    and not sg.get("mute_after") and not sg.get("verified"):
                print(f"MID-SENTENCE? {sec['name']} {nm}: '...{' '.join(w['word'].strip() for w in inside[-4:])}'"
                      f" | next: '{' '.join(w['word'].strip() for w in nxt[:3])}'"); issues += 1
            if a.captions:
                chunks = ns["caption_chunks"](ws, sg["start"], min(sg["end"], sg.get("mute_after", 1e9)),
                                              sg.get("speed", 1), plan.get("fixes", {}))
                print(f"  [{nm} {sg['start']:.1f}-{sg['end']:.1f}] " + " | ".join(c[2] for c in chunks))
    if a.captions:  # hand-written overlays (titles, tags, pops, end cards) need proof-reading too
        for sec in plan["sections"]:
            for sg in sec["segments"]:
                for t in sg.get("text", []):
                    if t[3] != "caption" or sg.get("captions") is False:
                        print(f"  [{sec['name']} {t[3]}] {t[2]}")
    # music: run-outs and repeats (positions as the full video plays them)
    ns["seg_frames"](plan)
    used = {}
    for sec in plan["sections"]:
        mk = sec.get("music")
        if not mk:
            continue
        t = plan["tracks"][mk]
        off, ln = sec["_music_off"], (sec["t1"] - sec["t0"]) / 30
        if off + ln > t.get("dur", 1e9) - 0.5:
            print(f"SONG RUNS OUT {sec['name']}: needs {off:.0f}-{off + ln:.0f}s of {t['file']} ({t.get('dur', 0):.0f}s)"); issues += 1
        for (o2, l2, n2) in used.get(mk, []):
            if off < o2 + l2 - 1 and o2 < off + ln - 1 and not sec.get("music_continue") and not sec.get("repeat_ok"):
                print(f"SONG REPEATS {sec['name']} replays {t['file']} {max(off, o2):.0f}s (also in {n2})"); issues += 1
        used.setdefault(mk, []).append((off, ln, sec["name"]))
    print(f"checks done: {issues} flag(s)")


if __name__ == "__main__":
    main()

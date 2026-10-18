"""vlog-editor render engine: plan.json -> finished video.

Every shot is rendered on its own (iPhone HLG HDR -> SDR on the GPU, rotation, grade, captions/titles,
transitions), cached by a hash of its settings, length-checked so audio == video, then concatenated.
The music bed is built per section (beat-aligned, continuing songs across sections), dipped under
speech, side-chained, and loudness-normalised in two passes (-14 LUFS).

usage: python3 render.py plan.json --res 1080|2160 [--only sec1,sec2] [--work DIR] [--out FILE]

  --only   render just these sections (a preview part). Music positions are still taken from the
           full plan, so a preview sounds exactly like that stretch of the final video.
  --work   cache dir for rendered shots. Default: plan["work_dir"] or ~/Movies/Video Editor Cache/<plan>/
           Keep it OUT of iCloud-synced folders (Desktop/Documents) -- it holds GBs of intermediates.
"""
import argparse, json, os, re, subprocess, sys, hashlib
from PIL import Image, ImageDraw, ImageFont

FPS = 30
FADE_KINDS = ("title", "sub", "loc", "endcard", "aside")
EMOJI = "/System/Library/Fonts/Apple Color Emoji.ttc"
AVENIR = "/System/Library/Fonts/Avenir Next.ttc"   # 0 Bold, 8 Heavy
FUTURA = "/System/Library/Fonts/Supplemental/Futura.ttc"  # 2 Bold, 4 Cond ExtraBold
# iPhone HDR is already vivid after tone-mapping, so the everyday grade stays subtle
GRADE = ("eq=contrast=1.03:saturation=1.0,"
         "colorbalance=rh=0.015:bh=-0.015,"
         "vignette=angle=PI/8")
# montage look: punchier teal/orange, film grain, 2.39:1 bars
GRADE_CINE = ("eq=contrast=1.06:saturation=1.04:gamma=0.99,"
              "colorbalance=rs=-0.02:bs=0.025:rh=0.025:bh=-0.025,"
              "vignette=angle=PI/6,noise=alls=4:allf=t")
# bold teal/orange look, used only for the opening trailer
GRADE_BOLD = ("eq=contrast=1.12:saturation=1.2:gamma=0.96,"
              "colorbalance=rs=-0.05:bs=0.06:rm=0.02:bm=-0.02:rh=0.06:bh=-0.06,"
              "vignette=angle=PI/5,noise=alls=7:allf=t")


def run(cmd):
    r = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"FAILED: {' '.join(cmd)}\n{r.stderr[-3000:]}")
    return r


def text_png(path, text, W, H, kind):
    """Transparent full-frame PNG with styled text. kind: caption | title | sub | pop."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    s = H / 1080
    if kind == "loc":  # location card, lower-left: thin rule + letter-spaced place name (+ optional "· detail")
        name, _, detail = text.partition("|")
        f = ImageFont.truetype(FUTURA, int(46 * s), index=2)
        f2 = ImageFont.truetype(AVENIR, int(26 * s), index=5)
        x, y = int(0.06 * W), int(0.70 * H)
        d.rectangle([x, y, x + int(60 * s), y + int(4 * s)], fill=(255, 214, 10, 255))
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        sd = ImageDraw.Draw(sh)
        spaced = " ".join(name.upper())
        sd.text((x + 2 * s, y + 18 * s), spaced, font=f, fill=(0, 0, 0, 150))
        if detail:
            sd.text((x + 2 * s, y + 78 * s), detail, font=f2, fill=(0, 0, 0, 150))
        im = Image.alpha_composite(im, sh)
        d = ImageDraw.Draw(im)
        d.text((x, y + 16 * s), spaced, font=f, fill=(255, 255, 255, 255))
        if detail:
            d.text((x, y + 76 * s), detail, font=f2, fill=(235, 235, 235, 255))
        im.save(path)
        return
    if kind == "endcard":  # "SEE YOU NEXT TIME / NEW YORK / — Frost Tube —" closing title
        import numpy as np
        top, big, sig = (text.split("|") + ["", ""])[:3]
        band = np.zeros((H, W, 4), np.uint8)  # soft dark band behind the text for legibility
        yy = np.arange(H)[:, None] / H
        band[..., 3] = (np.clip(1 - np.abs(yy - 0.52) / 0.22, 0, 1) ** 1.5 * 150).astype(np.uint8)
        im = Image.alpha_composite(im, Image.fromarray(band))
        d = ImageDraw.Draw(im)
        gold = (232, 196, 120, 255)
        f1 = ImageFont.truetype(FUTURA, int(40 * s), index=2)
        f2 = ImageFont.truetype(FUTURA, int(190 * s), index=4)
        f3 = ImageFont.truetype(AVENIR, int(30 * s), index=5)
        def centred(txt, f, y, fill, spacing):
            txt = (" " * spacing).join(txt)
            bx = d.textbbox((0, 0), txt, font=f)
            x = (W - (bx[2] - bx[0])) / 2
            d.text((x + 3 * s, y + 4 * s), txt, font=f, fill=(0, 0, 0, 150))
            d.text((x, y), txt, font=f, fill=fill)
            return x, bx[2] - bx[0]
        x1, w1 = centred(top.upper(), f1, 0.36 * H, (255, 255, 255, 255), 1)
        ly = 0.36 * H + 24 * s  # thin gold rules either side of the top line
        d.rectangle([x1 - 140 * s, ly, x1 - 30 * s, ly + 2 * s], fill=gold)
        d.rectangle([x1 + w1 + 30 * s, ly, x1 + w1 + 140 * s, ly + 2 * s], fill=gold)
        centred(big.upper(), f2, 0.41 * H, (255, 255, 255, 255), 1)
        if sig:
            centred(sig, f3, 0.64 * H, gold, 0)
        im.save(path)
        return
    if kind == "aside":  # *narrator-style aside*: italic, brand yellow, black outline, above the subtitles
        txt = text.strip()
        emo = "".join(ch for ch in txt if ord(ch) > 0x2000 and ch not in "’…")
        words = "".join(ch for ch in txt if not (ord(ch) > 0x2000 and ch not in "’…")).strip()
        f = ImageFont.truetype(AVENIR, int(46 * s), index=1)  # Avenir Next Bold Italic
        sw = int(5 * s)
        bx = d.textbbox((0, 0), f"*{words}*", font=f, stroke_width=sw)
        em = None
        if emo:
            ef = ImageFont.truetype(EMOJI, 160)
            em = Image.new("RGBA", (200 * len(emo), 200), (0, 0, 0, 0))
            ImageDraw.Draw(em).text((0, 0), emo, font=ef, embedded_color=True)
            em = em.crop(em.getbbox())
            eh = int((bx[3] - bx[1]) * 0.95)
            em = em.resize((max(1, int(em.width * eh / em.height)), eh), Image.LANCZOS)
        tw = bx[2] - bx[0] + (em.width + int(12 * s) if em else 0)
        x, y = (W - tw) / 2, 0.735 * H - (bx[3] - bx[1]) / 2
        d.text((x, y), f"*{words}*", font=f, fill=(255, 214, 10, 255), stroke_width=sw, stroke_fill=(0, 0, 0, 255))
        if em:
            im.alpha_composite(em, (int(x + bx[2] - bx[0] + 12 * s), int(y + (bx[3] - bx[1] - em.height) / 2 + 4 * s)))
        im.save(path)
        return
    if kind == "caption":
        f = ImageFont.truetype(AVENIR, int(52 * s), index=0)
        y, sw = 0.83 * H, int(5 * s)
    elif kind == "pop":
        f = ImageFont.truetype(AVENIR, int(64 * s), index=8)
        y, sw = 0.18 * H, int(6 * s)
    elif kind == "title":
        f = ImageFont.truetype(FUTURA, int(150 * s), index=4)
        y, sw = 0.5 * H, 0
    else:  # sub (small title line)
        f = ImageFont.truetype(FUTURA, int(48 * s), index=2)
        y, sw = 0.62 * H, 0
    if kind == "title":
        text = " ".join(text.upper())  # letter-spaced look
    box = d.textbbox((0, 0), text, font=f, stroke_width=sw)
    x = (W - (box[2] - box[0])) / 2
    yy = y - (box[3] - box[1]) / 2
    if kind in ("title", "sub"):  # soft shadow instead of outline
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(sh).text((x + 3 * s, yy + 4 * s), text, font=f, fill=(0, 0, 0, 140))
        im = Image.alpha_composite(im, sh)
        d = ImageDraw.Draw(im)
        d.text((x, yy), text, font=f, fill=(255, 255, 255, 255))
    else:
        fill = (255, 214, 10, 255) if kind == "pop" else (255, 255, 255, 255)
        d.text((x, yy), text, font=f, fill=fill, stroke_width=sw, stroke_fill=(0, 0, 0, 255))
    im.save(path)


_ENV = {}


def voice_onset(src):
    """Returns f(t): the first moment at/after ~t where the clip's audio actually rises into speech.
    Whisper's word starts drift early after pauses; captions snap to this instead."""
    if src not in _ENV:
        import numpy as np
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", src, "-vn", "-ac", "1", "-ar", "16000",
                              "-af", "highpass=f=120,lowpass=f=4000", "-f", "f32le", "-"],
                             capture_output=True, stdin=subprocess.DEVNULL).stdout
        y = np.frombuffer(raw, np.float32)
        hop = 160  # 10 ms
        n = len(y) // hop
        rms = np.sqrt((y[:n * hop].reshape(n, hop) ** 2).mean(1)) if n else np.zeros(1)
        floor, loud = np.percentile(rms, 20), np.percentile(rms, 95)
        thr = max(floor * 3, floor + 0.2 * (loud - floor))
        _ENV[src] = (rms > thr)
    on = _ENV[src]

    def f(t):
        i0, i1 = max(0, int((t - 0.15) * 100)), min(len(on), int((t + 0.5) * 100))
        for i in range(i0, i1):
            if on[i] and (i + 3 >= len(on) or on[i + 1:i + 4].any()):
                return i / 100
        return t
    return f


def leak_png(path, W, H):
    """Warm orange/magenta film light-leak, transparent elsewhere."""
    import numpy as np
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    def blob(cx, cy, r):
        return np.clip(1 - np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / r, 0, 1) ** 1.6
    a = np.clip(blob(0.1 * W, 0.2 * H, 0.75 * W) + 0.7 * blob(0.95 * W, 0.85 * H, 0.6 * W), 0, 1)
    warm = blob(0.1 * W, 0.2 * H, 0.75 * W)
    rgb = np.stack([np.full_like(a, 255), 120 + 60 * warm, 40 + 80 * (1 - warm)], -1)
    img = np.concatenate([rgb, (a * 215)[..., None]], -1).astype(np.uint8)
    Image.fromarray(img).save(path)


def caption_chunks(words, start, end, speed, fixes, onset=None):
    """Group whisper words inside [start,end] into short on-screen chunks (segment-relative times)."""
    ws = []
    for w in words:  # glue whisper's split tokens back on: "p" ".m." -> "p.m.", "o" "'clock" -> "o'clock"
        if not (w["start"] >= start - 0.05 and w["end"] <= end + 0.05):
            continue
        t = w["word"].strip()
        if ws and t[:1] in (".", "'", "-") and len(t) > 1:
            ws[-1]["word"] = ws[-1]["word"].rstrip() + t
            ws[-1]["end"] = w["end"]
        else:
            ws.append(dict(w))
    # apply multi-word fixes on the word stream first, so a phrase split across two caption chunks still gets fixed
    norm = lambda t: re.sub(r"[^\w']", "", t).lower()
    for bad, good in fixes.items():
        bw, gw = bad.split(), good.split()
        for i in range(len(ws) - len(bw) + 1):
            if [norm(w["word"]) for w in ws[i:i + len(bw)]] == [norm(x) for x in bw]:
                tail = re.sub(r"^.*?([^\w']*)$", r"\1", ws[i + len(bw) - 1]["word"].strip())  # keep trailing punctuation
                if len(gw) == len(bw):
                    for k in range(len(bw)):
                        ws[i + k]["word"] = " " + gw[k]
                else:
                    ws[i]["word"] = " " + good
                    for k in range(1, len(bw)):
                        ws[i + k]["word"] = ""
                ws[i + len(bw) - 1]["word"] = ws[i + len(bw) - 1]["word"].rstrip() + tail if ws[i + len(bw) - 1]["word"] else ""
                if not ws[i + len(bw) - 1]["word"]:
                    ws[i]["word"] = ws[i]["word"].rstrip() + tail
    chunks, cur = [], []
    for w in ws:
        t = w["word"].strip()
        if not t:
            continue
        prev = cur[-1]["word"].strip() if cur else ""
        keep_together = cur and (  # never split "4:30 | a.m.", "3 | 30" or "Times | Square"
            (re.match(r"^\$?\d", prev) and re.match(r"^(\d|[ap]\.m\.|o'clock)", t))
            or (prev[:1].isupper() and t[:1].isupper() and prev.lower() not in ("i", "i'm") and len(cur) < 4))
        ends_sentence = prev[-1:] in ".?!," and not re.search(r"\b[ap]\.m\.$|\bU\.S\.$", prev)
        if cur and not keep_together and (len(cur) >= 3 or w["start"] - cur[-1]["end"] > 0.35
                                          or w["end"] - cur[0]["start"] > 1.6 or ends_sentence):
            chunks.append(cur); cur = []
        cur.append(w)
    if cur:
        chunks.append(cur)
    out = []
    for c in chunks:
        txt = " ".join(w["word"].strip() for w in c).strip(" ,")
        # tidy whisper's tokenised punctuation: "4 30 a .m." -> "4:30 a.m.", "$5 .00" -> "$5.00", "o 'clock" -> "o'clock"
        txt = re.sub(r"\b(\d{1,2}) (\d{2}) (a|p) ?\.m\.", r"\1:\2 \3.m.", txt)
        txt = re.sub(r"\b(\d{1,2}) (\d{2})\b", r"\1:\2", txt)
        txt = re.sub(r"(\w) \.(\w)", r"\1.\2", txt)
        txt = re.sub(r"(\w) '(\w)", r"\1'\2", txt)
        txt = re.sub(r"(\w) -(\w)", r"\1-\2", txt)
        txt = re.sub(r"(?<![$\d])(\d{1,2})\.(\d{2})\b", r"\1:\2", txt)  # clock times 8.30 -> 8:30, not $5.00
        txt = re.sub(r"\bi\b", "I", txt)
        txt = re.sub(r"\s*\b(uh|um|uhm|umm)\b,?", "", txt, flags=re.I).strip(" ,")  # hide fillers in captions
        if out and (out[-1][2].rstrip()[-1:] in ".?!"  # capitalise only after a sentence ends (else keep whisper's case)
                       and not re.search(r"\b[ap]\.m\.$", out[-1][2].rstrip())):
            txt = txt[:1].upper() + txt[1:]
        if not txt or txt in (".", "..."):
            continue
        t0 = onset(c[0]["start"]) if onset else c[0]["start"]  # appear when the voice actually starts
        a = max(0, (t0 - start) / speed)
        b = min((end - start) / speed, max((c[-1]["end"] - start) / speed + 0.15, a + 0.4),
                a + 0.35 * len(c) + 0.6)  # whisper sometimes stretches a word's end; don't let it linger
        out.append([a, b, txt])
    for i in range(len(out) - 1):  # no overlap
        out[i][1] = min(out[i][1], out[i + 1][0])
    return out


def seg_frames(plan):
    """Assign exact frame counts. Montage segs given in beats snap cuts to the section's beat grid."""
    t = 0  # frames
    pos = {}  # where each song has got to (for music_continue)
    for sec in plan["sections"]:
        sec["t0"] = t
        m = sec.get("music")
        trk = plan["tracks"].get(m)
        beat = 60 / trk["bpm"] if trk else None
        lead = 0.0
        if trk:
            if "_music_off" not in sec:  # first pass (full plan); trimmed preview passes reuse it
                if sec.get("music_continue") and m in pos:
                    sec["_music_off"] = pos[m]
                elif "music_offset" in sec:
                    sec["_music_off"] = sec["music_offset"]
                else:
                    sec["_music_off"] = trk["first_beat"] + sec.get("music_beat", 0) * beat
            # time from section start to the song's next downbeat, so montage cuts land on the beat
            lead = (trk["first_beat"] - sec["_music_off"]) % beat
            if lead > beat - 0.01:
                lead = 0.0
        acc_beats = 0
        for sg in sec["segments"]:
            if "beats" in sg:
                acc_beats += sg["beats"]
                end = sec["t0"] + round((lead + acc_beats * beat) * FPS)
                sg["frames"] = end - t
            else:
                sg["frames"] = round((sg["end"] - sg["start"]) / sg.get("speed", 1) * FPS)
                acc_beats = ((t + sg["frames"] - sec["t0"]) / FPS - lead) / beat if beat else 0
                if beat and sec.get("snap_after_talk"):  # next montage cut lands back on the beat grid
                    import math
                    acc_beats = math.ceil(acc_beats - 1e-6)
            sg["t0"] = t
            t += sg["frames"]
        sec["t1"] = t
        if trk:
            pos[m] = sec["_music_off"] + (t - sec["t0"]) / FPS
    return t


def grade_key(sg):
    return ("raw" if sg.get("raw") else GRADE_BOLD if sg.get("grade") == "bold" else GRADE_CINE if sg.get("cine") else GRADE)


def fix_av_length(path):
    """Make a shot's audio exactly as long as its video. Stopping the encoder on a frame count can drop
    the last few audio packets; across ~160 shots that added up to ~0.85 s of voice-leads-picture drift."""
    j = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,duration",
                                   "-of", "json", path], capture_output=True, text=True,
                                  stdin=subprocess.DEVNULL).stdout)
    d = {st["codec_type"]: float(st["duration"]) for st in j["streams"]}
    if abs(d["video"] - d["audio"]) < 0.0015:
        return
    tmp = path + ".fix.mov"
    run(["ffmpeg", "-y", "-v", "error", "-i", path, "-map", "0:v", "-map", "0:a", "-c:v", "copy",
         "-af", f"apad,atrim=0:{d['video']:.6f}", "-c:a", "pcm_s16le", tmp])
    os.replace(tmp, path)


def render_segment(i, sg, plan, info, tx, W, H, work, vcodec):
    src = sg["src"]
    meta = info[src]
    speed = sg.get("speed", 1)
    n = sg["frames"]
    dur_out = n / FPS
    src_len = dur_out * speed
    ramp = sg.get("ramp")  # [fast_speed, slow_speed, fraction of output played fast]
    if ramp:
        s1, s2, f = ramp
        tau1 = f * dur_out * s1
        src_len = tau1 + (1 - f) * dur_out * s2
    start = sg["start"]
    if "beats" in sg:  # montage: take src_len centred on requested start..end window
        end = sg.get("end", start + src_len)
        start = max(0, min(meta["dur"] - src_len - 0.05, (start + end) / 2 - src_len / 2))
    overlays = []
    if sg.get("voice") and sg.get("captions", True):
        words = [w for s in tx.get(src, {}).get("segments", []) for w in s.get("words", [])]
        overlays += [(a, b, t, "caption") for a, b, t in
                     caption_chunks(words, start, min(start + src_len, sg.get("mute_after", 1e9)), speed, plan.get("fixes", {}),
                                    onset=voice_onset(src))]
    for o in sg.get("text", []):  # [a, b, text, kind]
        overlays.append((o[0], min(o[1], dur_out), o[2], o[3]))
    key = hashlib.md5(json.dumps([{k: v for k, v in sg.items() if k != "t0"}, start, n, W, overlays, grade_key(sg), "ov2"], sort_keys=True).encode()).hexdigest()[:10]
    out = f"{work}/seg{i:03d}_{key}.mov"
    if os.path.exists(out):
        return out
    rot = sg.get("rot", meta["rot"])  # some clips carry a wrong rotation flag
    portrait = rot in (90, -90)
    # portrait: scale the coded landscape frame so that after rotation its height == H
    sw, sh = (H, round(H * H / W / 2) * 2) if portrait else (W, H)
    if meta.get("sdr"):  # ordinary 8-bit SDR file (channel graphics): plain decode + scale
        chain = [f"scale={sw}:{sh}", "format=yuv420p"]
    else:  # iPhone HLG HDR -> SDR on the GPU
        chain = [f"scale_vt=w={sw}:h={sh}:color_matrix=bt709:color_primaries=bt709:color_transfer=bt709",
                 "hwdownload", "format=p010le", "format=yuv420p"]
    if rot in (180, -180):
        chain += ["hflip", "vflip"]
    elif rot == -90:
        chain += ["transpose=clock"]
    elif rot == 90:
        chain += ["transpose=cclock"]
    if ramp:
        chain += ["setpts=PTS-STARTPTS",
                  f"setpts='if(lt(T,{tau1:.4f}),T/{s1},{tau1/s1:.4f}+(T-{tau1:.4f})/{s2})/TB'", f"fps={FPS}"]
    else:
        chain += [f"setpts=(PTS-STARTPTS)/{speed}", f"fps={FPS}"]
    fc = f"[0:v]{','.join(chain)}[v0];"
    if portrait:  # blurred fill background
        fc += (f"[v0]split[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
               f"boxblur=20:2,eq=brightness=-0.08[bg];[bg][b]overlay=(W-w)/2:0[v0];")
    zoom = sg.get("zoom")  # slow push-in for static shots: e.g. 1.08
    if zoom:
        fc += (f"[v0]scale={int(W*zoom)}:{int(H*zoom)},crop={W}:{H}:"
               f"'(iw-{W})/2*(1-t/{dur_out})':'(ih-{H})/2*(1-t/{dur_out})'[v0];")
    if sg.get("tilt") == "up":  # reveal: glide the frame from the base of the shot up to the top
        z = 1.35
        fc += (f"[v0]scale={round(W*z/2)*2}:{round(H*z/2)*2},"
               f"crop={W}:{H}:(iw-{W})/2:'(ih-{H})*(1-min(1,t/{dur_out:.3f}))'[v0];")
    punch = sg.get("punch")  # static punch-in on alternate jump cuts, framed slightly high (faces)
    if punch:
        fx, fy = sg.get("focus", [0.5, 0.42])  # where the face is, as a fraction of the frame
        fc += (f"[v0]scale={round(W*punch/2)*2}:{round(H*punch/2)*2},"
               f"crop={W}:{H}:'min(max(iw*{fx}-{W}/2,0),iw-{W})':'min(max(ih*{fy}-{H}/2,0),ih-{H})'[v0];")
    if sg.get("pulse"):  # zoom "thump" on the beat: 1.12x easing back to 1x over 0.3s
        fc += (f"[v0]scale=w='{W}*(1+0.12*max(0,1-t/0.3))':h='{H}*(1+0.12*max(0,1-t/0.3))':eval=frame,"
               f"crop={W}:{H}:(iw-{W})/2:(ih-{H})/2[v0];")
    if sg.get("shake"):  # handheld hit for the first 0.5s
        fc += (f"[v0]scale={round(W*1.06/2)*2}:{round(H*1.06/2)*2},"
               f"crop={W}:{H}:'(iw-{W})/2+if(lt(t,0.5),{W*0.012:.0f}*sin(t*70)*(1-t/0.5),0)'"
               f":'(ih-{H})/2+if(lt(t,0.5),{H*0.012:.0f}*cos(t*55)*(1-t/0.5),0)'[v0];")
    cine = sg.get("cine")
    grade = ("null" if sg.get("raw") else GRADE_BOLD if sg.get("grade") == "bold"  # raw: channel graphics, untouched
             else GRADE_CINE if cine else GRADE)
    fc += f"[v0]{grade}"
    # transitions into / out of this shot: whip | zoom | glitch | leak (leak is an overlay, added below)
    tin = sg.get("tr_in") or ("whip" if sg.get("whip_in") else None)
    tout = sg.get("tr_out") or ("whip" if sg.get("whip_out") else None)
    wd, zd, gd = 0.13, 0.22, 0.12
    if tin == "whip":
        fc += f",dblur=angle=0:radius=60:enable='lt(t,{wd})'"
    if tout == "whip":
        fc += f",dblur=angle=0:radius=60:enable='gte(t,{dur_out - wd:.3f})'"
    if tin == "zoom" or tout == "zoom":  # punch through the cut: zoom into the outgoing shot, out of the incoming one
        zin = f"0.3*clip(1-t/{zd},0,1)" if tin == "zoom" else "0"
        zout = f"0.3*clip((t-{dur_out - zd:.3f})/{zd},0,1)" if tout == "zoom" else "0"
        fc += (f",scale=w='{W}*(1+{zin}+{zout})':h='{H}*(1+{zin}+{zout})':eval=frame,"
               f"crop={W}:{H}:(iw-{W})/2:(ih-{H})/2,dblur=angle=90:radius=18:enable='lt(t,{zd if tin == 'zoom' else 0})+gte(t,{dur_out - (zd if tout == 'zoom' else -1):.3f})'")
    if tin == "glitch":
        fc += f",rgbashift=rh=-{W//80}:bh={W//80}:gv={H//120}:enable='lt(t,{gd})'"
    if tout == "glitch":
        fc += f",rgbashift=rh={W//80}:bh=-{W//80}:gv=-{H//120}:enable='gte(t,{dur_out - gd:.3f})'"
    if sg.get("flash"):
        fc += ",fade=t=in:st=0:d=0.12:color=white"
    if cine:
        bar = round((H - W / 2.39) / 2)
        fc += (f",drawbox=x=0:y=0:w=iw:h={bar}:color=black:t=fill"
               f",drawbox=x=0:y=ih-{bar}:w=iw:h={bar}:color=black:t=fill")
    if sg.get("fade_in"):
        fc += f",fade=t=in:st=0:d={sg['fade_in']}"
    if sg.get("fade_out"):
        fc += f",fade=t=out:st={dur_out - sg['fade_out']:.3f}:d={sg['fade_out']}"
    fc += "[v1];"
    hw = [] if meta.get("sdr") else ["-hwaccel", "videotoolbox", "-hwaccel_output_format", "videotoolbox_vld"]
    inputs = [*hw, "-noautorotate", "-ss", f"{start:.3f}", "-t", f"{src_len + 0.2:.3f}", "-i", src]
    last = "v1"
    for k, (a, b, t, kind) in enumerate(overlays):
        p = f"{work}/txt_{key}_{k}.png"
        text_png(p, t, W, H, kind)
        if kind in FADE_KINDS:  # fade in/out rather than pop
            fi, fo = (0.6, 0.5) if kind == "endcard" else (0.12, 0.2) if kind == "aside" else (0.25, 0.25)
            inputs += ["-loop", "1", "-t", f"{dur_out:.3f}", "-i", p]
            fc += (f"[{k+1}:v]format=rgba,fade=t=in:st={a:.3f}:d={fi}:alpha=1,"
                   f"fade=t=out:st={max(a + fi, b - fo):.3f}:d={fo}:alpha=1[f{k}];"
                   f"[{last}][f{k}]overlay=enable='between(t,{a:.3f},{b:.3f})'[o{k}];")
        else:
            inputs += ["-i", p]
            fc += f"[{last}][{k+1}:v]overlay=enable='between(t,{a:.3f},{b:.3f})'[o{k}];"
        last = f"o{k}"
    if tin == "leak" or tout == "leak":  # warm film light-leak washing over the cut
        lp = f"{work}/leak_{W}.png"
        if not os.path.exists(lp):
            leak_png(lp, W, H)
        inputs += ["-loop", "1", "-t", f"{dur_out:.3f}", "-i", lp]
        li = len(overlays) + 1
        fades = []
        if tout == "leak":
            fades.append(f"fade=t=in:st={max(0, dur_out - 0.35):.3f}:d=0.3:alpha=1")
        if tin == "leak":
            fades.append("fade=t=out:st=0.05:d=0.35:alpha=1")
        fc += f"[{li}:v]format=rgba,{','.join(fades)}[lk];[{last}][lk]overlay[lko];"
        last = "lko"
    vol = sg.get("vol", 1.0 if sg.get("voice") else 0.25)
    if speed != 1 or ramp:
        vol = 0  # slow-mo shots: no warped audio
    has_audio = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries",
                                "stream=index", "-of", "csv=p=0", src], capture_output=True, text=True,
                               stdin=subprocess.DEVNULL).stdout.strip() != ""
    ain = "0:a"
    if not has_audio:  # e.g. Live Photo videos: feed silence instead
        inputs += ["-f", "lavfi", "-t", f"{dur_out + 0.5:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
        ain = f"{len(overlays) + 1 + (1 if tin == 'leak' or tout == 'leak' else 0)}:a"
    fc += (f"[{ain}]asetpts=PTS-STARTPTS,volume={vol},aresample=48000,aformat=channel_layouts=stereo,"
           f"afade=t=in:d=0.04,apad,atrim=0:{dur_out:.4f},"
           + (f"afade=t=out:st={max(0, (sg['mute_after'] - start) / speed):.4f}:d=0.15[a]" if sg.get("mute_after")
              else f"afade=t=out:st={max(0, dur_out-0.05):.4f}:d=0.05[a]"))
    cmd = ["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", fc,
           "-map", f"[{last}]", "-map", "[a]", "-frames:v", str(n), *vcodec,
           "-pix_fmt", "yuv420p", "-color_primaries", "bt709", "-color_trc", "bt709",
           "-colorspace", "bt709", "-r", str(FPS), "-c:a", "pcm_s16le", out + ".part.mov"]
    run(cmd)
    os.replace(out + ".part.mov", out)  # only a fully written shot gets its cache name
    return out


def build_music(plan, total_frames, work, music_dir, tag):
    """One music bed: each section plays its track from a beat-aligned offset, crossfaded."""
    inputs, parts = [], []
    k = 0
    secs = plan["sections"]
    pos = {}  # where each track left off, for music_continue
    for i, sec in enumerate(secs):
        m = sec.get("music")
        if not m:
            continue
        trk = plan["tracks"][m]
        a, b = sec["t0"] / FPS, sec["t1"] / FPS
        length = b - a
        cont = sec.get("music_continue") and (m in pos or "_music_off" in sec)
        if "_music_off" in sec:
            off = sec["_music_off"]
        elif cont:
            off = pos[m]
        elif "music_offset" in sec:
            off = sec["music_offset"]
        else:
            off = trk["first_beat"] + sec.get("music_beat", 0) * 60 / trk["bpm"]
        pos[m] = off + length
        fi = sec.get("music_fade_in", 0.03 if cont else 0.8)
        nxt = secs[i + 1] if i + 1 < len(secs) else None
        seamless = nxt and nxt.get("music") == m and nxt.get("music_continue") and nxt["t0"] == sec["t1"]
        handoff = nxt and nxt.get("music") and not seamless and nxt["t0"] == sec["t1"]  # another song takes over
        lvl = sec.get("music_broll", sec.get("music_level", 0.5))  # bed level between lines
        spill = 0  # never let a song bleed into the next section
        inputs += ["-ss", f"{off:.3f}", "-t", f"{length + spill:.3f}", "-i", os.path.join(music_dir, trk["file"])]
        fo = sec.get("music_fade_out")  # fade down inside the section instead of spilling past its end
        if not seamless and not fo:
            fo = 0.6  # fade down just before the cut
        fade_out = ("anull" if seamless else f"afade=t=out:st={length - fo:.3f}:d={fo}" if fo
                    else f"afade=t=out:st={length:.3f}:d=1.0")
        parts.append(f"[{k}:a]aresample=48000,aformat=channel_layouts=stereo,volume={lvl},"
                     f"afade=t=in:d={fi},{fade_out},adelay={int(a*1000)}|{int(a*1000)}[m{k}]")
        k += 1
    fc = ";".join(parts) + ";" + "".join(f"[m{j}]" for j in range(k)) + \
        f"amix=inputs={k}:normalize=0:duration=longest,atrim=0:{total_frames/FPS:.3f}[out]"
    out = f"{work}/music_{tag}.wav"
    run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", fc, "-map", "[out]", out])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plan")
    ap.add_argument("--res", type=int, default=1080)
    ap.add_argument("--work", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--only", default=None, help="render only these section names (preview)")
    a = ap.parse_args()
    plan = json.load(open(a.plan))
    H = a.res; W = H * 16 // 9
    default_work = plan.get("work_dir") or os.path.join(
        os.path.expanduser("~/Movies/Video Editor Cache"), plan.get("project", "project"))
    work = a.work or os.path.join(default_work, f"work{H}")
    os.makedirs(work, exist_ok=True)
    info = json.load(open(plan["clipinfo"]))
    tx = {}
    for src in info:
        p = plan["tx_for"].get(src)
        if p and os.path.exists(p):
            tx[src] = json.load(open(p))
    seg_frames(plan)  # full plan first: fixes each section's song position, so previews match the final
    if a.only:
        keep = a.only.split(",")
        plan["sections"] = [s for s in plan["sections"] if s["name"] in keep]
    total = seg_frames(plan)
    vcodec = (["-c:v", "h264_videotoolbox", "-b:v", "9M", "-profile:v", "high"] if H <= 1080 else
              ["-c:v", "hevc_videotoolbox", "-b:v", "28M", "-tag:v", "hvc1"])
    segs = [sg for sec in plan["sections"] for sg in sec["segments"]]
    files = []
    for i, sg in enumerate(segs):
        f = render_segment(i, sg, plan, info, tx, W, H, work, vcodec)
        fix_av_length(f)
        files.append(f)
        print(f"  seg {i+1}/{len(segs)}", flush=True)
    out = a.out or plan["out"]
    tag = os.path.splitext(os.path.basename(out))[0]  # per-output temp names: parallel renders can't clash
    lst = f"{work}/list_{tag}.txt"
    open(lst, "w").write("".join(f"file '{f}'\n" for f in files))
    body = f"{work}/body_{tag}.mov"
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", body])
    music = build_music(plan, total, work, plan["music_dir"], tag)
    # Ducking key = talking segments only, so street noise / crowds in B-roll never pull the music down.
    talk_ranges = []
    no_duck = {id(g) for sec in plan["sections"] if sec.get("no_duck") for g in sec["segments"]}
    for sg in segs:
        if sg.get("voice") and id(sg) not in no_duck:  # no_duck sections: music rides freely under the voice
            a0, a1 = sg["t0"] / FPS, (sg["t0"] + sg["frames"]) / FPS
            if talk_ranges and abs(talk_ranges[-1][1] - a0) < 0.01:
                talk_ranges[-1][1] = a1
            else:
                talk_ranges.append([a0, a1])
    gate = "+".join(f"between(t,{x:.3f},{y:.3f})" for x, y in talk_ranges) or "0"
    # music automation: in sections with music_broll, dip the bed to music_level while you talk (0.2s ramps)
    dips = []
    for sec in plan["sections"]:
        if not sec.get("music_broll"):
            continue
        depth = 1 - sec["music_level"] / sec["music_broll"]
        runs = []  # merge back-to-back talking shots into one dip
        for sg in sec["segments"]:
            if not sg.get("voice"):
                continue
            a0, a1 = sg["t0"] / FPS, (sg["t0"] + sg["frames"]) / FPS
            if runs and abs(runs[-1][1] - a0) < 0.01:
                runs[-1][1] = a1
            else:
                runs.append([a0, a1])
        merged = []
        for span in runs:
            if merged and span[0] - merged[-1][1] < 3.0:  # short B-roll gap: keep the music down, no pumping
                merged[-1][1] = span[1]
            else:
                merged.append(list(span))
        dips += [(span, depth) for span in merged]
    rp = 0.6  # music fades down/up over 0.6 s around talking
    env = "+".join(f"{d:.3f}*clip((t-{x - rp:.3f})/{rp},0,1)*clip(({y + rp:.3f}-t)/{rp},0,1)"
                   for (x, y), d in dips) or "0"
    auto = f"volume='1-min(0.95,{env})':eval=frame"
    duck = plan.get("duck", "threshold=0.01:ratio=4:attack=15:release=400:makeup=1")  # gentle; automation does the heavy lifting
    mix = f"{work}/mix_{tag}.wav"
    # voice clarity: cut rumble, even out levels, lift presence a touch
    voice = ("highpass=f=90,acompressor=threshold=0.06:ratio=3:attack=8:release=150:makeup=2,"
             "equalizer=f=3000:t=q:w=1.2:g=3")
    fc = (f"[0:a]{voice},asplit[v][sc];[sc]volume=0:enable='not({gate})'[key];"
          f"[1:a]{auto}[bed];[bed][key]sidechaincompress={duck}[m];[v][m]amix=inputs=2:normalize=0[a]")
    open(f"{work}/mixgraph_{tag}.txt", "w").write(fc)  # kept for debugging the mix
    run(["ffmpeg", "-y", "-v", "error", "-i", body, "-i", music, "-filter_complex", fc,
         "-map", "[a]", "-c:a", "pcm_s24le", mix])
    # Two-pass loudness: measure the whole mix, then apply one fixed (linear) gain -> no pumping.
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", mix, "-af",
                        "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
                       stdin=subprocess.DEVNULL, capture_output=True, text=True).stderr
    m = json.loads(r[r.rindex("{"):r.rindex("}") + 1])
    ln = (f"loudnorm=I=-14:TP=-1.5:LRA=11:linear=true:measured_I={m['input_i']}:"
          f"measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}:"
          f"measured_thresh={m['input_thresh']}:offset={m['target_offset']}")
    for f in os.listdir(work):  # free disk before the final write
        if f.startswith("txt_"):
            os.remove(os.path.join(work, f))
    run(["ffmpeg", "-y", "-v", "error", "-i", body, "-i", mix, "-filter_complex", f"[1:a]{ln},aresample=48000[a]",
         "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k",
         "-movflags", "+faststart", out])
    os.remove(mix)
    os.remove(body)
    print(f"done: {out}  {total/FPS/60:.2f} min")


if __name__ == "__main__":
    main()

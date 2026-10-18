"""Footage inventory: what's in a dump of phone clips, where and when it was shot, and what it looks like.

usage: python3 clips.py inventory  DIR|CLIP [...]  > inventory.tsv   (name, secs, WxH, fps, rot, HDR, audio, time, GPS)
       python3 clips.py sheets     OUTDIR DIR|CLIP [...]              (contact sheets: 3 frames per clip, 12 clips/sheet)
       python3 clips.py frames     CLIP OUTPNG t1 t2 ...             (frame grid at chosen times, SDR-correct)

Why: you can't judge footage from filenames. GPS + creation time group clips into places/days (and verify
landmarks -- e.g. "is this really the Empire State Building?"), contact sheets show which shots are usable,
rot/HDR/audio flags predict render problems (sideways clips, washed-out HDR, silent Live Photos).
Frames are decoded with VideoToolbox; HDR is tone-mapped so stills look like the final video.
"""
import json
import os
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

VIDEO = (".mov", ".mp4", ".m4v")


def meta(p):
    j = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                                   "stream=codec_type,width,height,r_frame_rate,color_transfer:stream_side_data=rotation:"
                                   "format=duration:format_tags=creation_time,com.apple.quicktime.location.ISO6709",
                                   "-of", "json", p], capture_output=True, text=True, stdin=subprocess.DEVNULL).stdout)
    v = [s for s in j.get("streams", []) if s["codec_type"] == "video"]
    if not v:
        return None
    v = v[0]
    n, d = v["r_frame_rate"].split("/")
    tags = j["format"].get("tags", {})
    return dict(dur=float(j["format"].get("duration", 0)), w=v["width"], h=v["height"], fps=round(int(n) / int(d), 2),
                rot=next((x["rotation"] for x in v.get("side_data_list", []) if "rotation" in x), 0),
                hdr=v.get("color_transfer") in ("arib-std-b67", "smpte2084"),
                audio=any(s["codec_type"] == "audio" for s in j["streams"]),
                time=tags.get("creation_time", "")[:19], gps=tags.get("com.apple.quicktime.location.ISO6709", ""))


def frame(p, t, w=320, h=180, m=None):
    """One display-correct frame (rotation + HDR tone-map) as a PIL image letterboxed into w x h."""
    m = m or meta(p)
    flip = {180: "hflip,vflip,", -180: "hflip,vflip,", -90: "transpose=clock,", 90: "transpose=cclock,"}.get(m["rot"], "")
    if m["hdr"]:
        pre = ["-hwaccel", "videotoolbox", "-hwaccel_output_format", "videotoolbox_vld"]
        vf = (f"scale_vt=w={m['w'] // 4}:h={m['h'] // 4}:color_matrix=bt709:color_primaries=bt709:color_transfer=bt709,"
              f"hwdownload,format=p010le,format=yuv420p,{flip}")
    else:
        pre, vf = [], flip
    vf += f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2"
    raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", *pre, "-noautorotate", "-ss", f"{t:.2f}", "-i", p,
                          "-frames:v", "1", "-vf", vf, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    if len(raw) != w * h * 3:
        return Image.new("RGB", (w, h))
    return Image.frombytes("RGB", (w, h), raw)


def clips_in(paths):
    """Folders and/or individual clip files."""
    out = []
    for p in map(os.path.expanduser, paths):
        if os.path.isdir(p):
            out += [os.path.join(p, f) for f in os.listdir(p) if f.lower().endswith(VIDEO)]
        elif p.lower().endswith(VIDEO):
            out.append(p)
    return sorted(out)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "inventory":
        print("clip\tsecs\tsize\tfps\trot\thdr\taudio\ttime\tgps")
        for p in clips_in([os.path.expanduser(d) for d in sys.argv[2:]]):
            m = meta(p)
            if m:
                print(f"{os.path.basename(p)}\t{m['dur']:.1f}\t{m['w']}x{m['h']}\t{m['fps']}\t{m['rot']}\t{m['hdr']}\t"
                      f"{m['audio']}\t{m['time']}\t{m['gps']}")
    elif cmd == "sheets":
        out = os.path.expanduser(sys.argv[2]); os.makedirs(out, exist_ok=True)
        font = ImageFont.load_default(16)
        strips = []
        for p in clips_in([os.path.expanduser(d) for d in sys.argv[3:]]):
            m = meta(p)
            if not m:
                continue
            st = Image.new("RGB", (960, 200))
            for k, q in enumerate((0.15, 0.5, 0.85)):
                st.paste(frame(p, m["dur"] * q, m=m), (k * 320, 20))
            ImageDraw.Draw(st).text((4, 2), f"{os.path.basename(p)} {m['dur']:.1f}s {m['fps']}fps rot{m['rot']} "
                                             f"{'HDR' if m['hdr'] else 'SDR'}{'' if m['audio'] else ' NO-AUDIO'} {m['time'][5:16]}",
                                    fill="yellow", font=font)
            strips.append(st)
        for i in range(0, len(strips), 12):
            sh = Image.new("RGB", (960 * 3, 200 * 4))
            for k, s in enumerate(strips[i:i + 12]):
                sh.paste(s, ((k % 3) * 960, (k // 3) * 200))
            sh.save(os.path.join(out, f"sheet{i // 12:02d}.jpg"), quality=78)
        print(f"{len(strips)} clips -> {out}")
    elif cmd == "frames":
        p, outp, ts = sys.argv[2], sys.argv[3], [float(x) for x in sys.argv[4:]]
        m = meta(p)
        ims = [frame(p, t, m=m) for t in ts]
        for im, t in zip(ims, ts):
            ImageDraw.Draw(im).text((4, 4), f"{t}", fill="yellow")
        cols = min(6, len(ims))
        g = Image.new("RGB", (320 * cols, 180 * ((len(ims) + cols - 1) // cols)))
        for k, im in enumerate(ims):
            g.paste(im, ((k % cols) * 320, (k // cols) * 180))
        g.save(outp)

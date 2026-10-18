"""YouTube thumbnails (1280x720) from your own footage.

usage:
  python3 thumbnail.py still CLIP SECONDS OUT.png        SDR-correct full-res frame (HDR tone-mapped like the video)
  python3 thumbnail.py compose --bg BG.png --subject CUT.png --lines "New York's" "Most Famous Slice!!" OUT.jpg
        [--bg-crop x0,y0,width]   crop of the background frame (16:9), in source pixels
        [--subject-box x,y,height] where the cut-out goes on the 1280x720 canvas (default right side)
        [--style house|bold]       house = white box + heavy black text + yellow offset block (channel style)

Rules of thumb that tested well (see references/thumbnails.md): one big face/subject ~1/4-1/3 of the frame,
<= 3-4 words, high contrast, nothing in the bottom-right (YouTube's timestamp), text adds to the title
instead of repeating it. Make 2 variants and run YouTube Studio "Test & Compare".
"""
import argparse
import os
import subprocess

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

W, H = 1280, 720
AVENIR = "/System/Library/Fonts/Avenir Next.ttc"      # index 8 = Heavy
FUTURA = "/System/Library/Fonts/Supplemental/Futura.ttc"  # index 4 = Condensed ExtraBold


def pop(im, c=1.15, s=1.2):
    return ImageEnhance.Color(ImageEnhance.Contrast(im).enhance(c)).enhance(s)


def still(clip, t, out):
    vt = ("scale_vt=w=3840:h=2160:color_matrix=bt709:color_primaries=bt709:color_transfer=bt709,"
          "hwdownload,format=p010le,format=yuv420p")
    trc = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=color_transfer",
                          "-of", "csv=p=0", clip], capture_output=True, text=True).stdout
    hw = ["-hwaccel", "videotoolbox", "-hwaccel_output_format", "videotoolbox_vld"] if "b67" in trc or "2084" in trc else []
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-v", "error", *hw, "-ss", str(t), "-i", clip, "-frames:v", "1",
                    *(["-vf", vt] if hw else []), out], check=True)


def house_label(d, xy, txt, size, pad=(22, 10), off=10):
    """Channel house style: white box, heavy black text, yellow block offset down-right."""
    f = ImageFont.truetype(AVENIR, size, index=8)
    bx = d.textbbox((0, 0), txt, font=f)
    w, h = bx[2] - bx[0] + 2 * pad[0], bx[3] - bx[1] + 2 * pad[1]
    x, y = xy
    d.rectangle([x + off, y + off, x + w + off, y + h + off], fill=(255, 214, 0))
    d.rectangle([x, y, x + w, y + h], fill=(255, 255, 255), outline=(0, 0, 0), width=4)
    d.text((x + pad[0] - bx[0], y + pad[1] - bx[1]), txt, font=f, fill=(0, 0, 0))
    return h


def compose(bg, subject, lines, out, bg_crop=None, subject_box=None, style="house"):
    im = pop(Image.open(bg).convert("RGB"))
    if bg_crop:
        x0, y0, bw = bg_crop
        im = im.crop((x0, y0, x0 + bw, y0 + int(bw * H / W)))
    canvas = im.resize((W, H), Image.LANCZOS).convert("RGBA")
    if subject:
        cut = Image.open(subject).convert("RGBA")
        cut = cut.crop(cut.getbbox())
        alpha = cut.split()[3]
        cut = pop(cut.convert("RGB"), 1.1, 1.15).convert("RGBA"); cut.putalpha(alpha)
        px, py, sh = subject_box or (W - int(590 * cut.width / cut.height) + 40, H - 560, 590)
        cut = cut.resize((int(cut.width * sh / cut.height), sh), Image.LANCZOS)
        a = cut.split()[3]
        outline = a.filter(ImageFilter.MaxFilter(13))                       # white sticker outline
        shadow = outline.filter(ImageFilter.GaussianBlur(16)).point(lambda v: int(v * 0.6))
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        s_ = Image.new("RGBA", cut.size, (0, 0, 0, 255)); s_.putalpha(shadow)
        layer.alpha_composite(s_, (px + 12, py + 16))
        o_ = Image.new("RGBA", cut.size, (255, 255, 255, 255)); o_.putalpha(outline)
        layer.alpha_composite(o_, (px, py)); layer.alpha_composite(cut, (px, py))
        canvas = Image.alpha_composite(canvas, layer)
    img = canvas.convert("RGB")
    d = ImageDraw.Draw(img)
    if style == "house":
        y = 22
        for i, txt in enumerate(lines):
            y += house_label(d, (28, y), txt, 54 if i == 0 and len(lines) > 1 else 70) + 18
    else:  # bold: big yellow words with heavy black stroke
        f = ImageFont.truetype(FUTURA, 140, index=4)
        for i, txt in enumerate(lines):
            d.text((34, 30 + i * 140), txt.upper(), font=f, fill=(255, 221, 0), stroke_width=10, stroke_fill=(0, 0, 0))
    img.save(out, quality=93)
    print(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    s1 = sp.add_parser("still"); s1.add_argument("clip"); s1.add_argument("t", type=float); s1.add_argument("out")
    s2 = sp.add_parser("compose")
    s2.add_argument("--bg", required=True); s2.add_argument("--subject"); s2.add_argument("--lines", nargs="+", required=True)
    s2.add_argument("--bg-crop"); s2.add_argument("--subject-box"); s2.add_argument("--style", default="house")
    s2.add_argument("out")
    a = ap.parse_args()
    if a.cmd == "still":
        still(a.clip, a.t, a.out)
    else:
        ints = lambda s: tuple(int(v) for v in s.split(",")) if s else None
        compose(a.bg, a.subject, a.lines, a.out, ints(a.bg_crop), ints(a.subject_box), a.style)

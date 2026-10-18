"""Example plan for a short city vlog. Copy to projects/<Name>/plan.py and edit.

    ~/.vlog-editor-venv/bin/python plan.py                    # writes plan.json + a length report
    ~/.vlog-editor-venv/bin/python <skill>/scripts/check_plan.py plan.json --captions
    ~/.vlog-editor-venv/bin/python <skill>/scripts/render.py plan.json --res 1080 --only teaser,title --out previews/part1.mp4
"""
import os
import sys

sys.path.insert(0, os.path.expanduser("~/Desktop/Video Editor/vlog-editor-skill/scripts"))
from planlib import Project, T, add_asides, asset, broll, clean_montage, sec, talk, write_plan  # noqa: E402

P = Project("City Vlog",
            footage=["~/Downloads/City clips"],                  # where the clips are right now
            music_dir="~/Desktop/Video Editor/music",
            assets="~/Desktop/Video Editor/assets")

sections = [
    # cold open: the best reaction, music already rising underneath
    sec("teaser", [talk("IMG_0101", 1.3, 5.6)],
        music="upbeat", music_offset=1.45, music_level=0.75, music_fade_in=2.0, no_duck=True),
    # title montage: best of the trip on the beat; bold look only here
    sec("title", [
        broll("IMG_0001", 2, 9, beats=8, grade="bold",
              text=[T(0.15, 2.75, "CITY NAME", "title"), T(0.6, 2.75, "A short subtitle", "sub")]),
        broll("IMG_0002", 0, 6, beats=2, grade="bold"),
        broll("IMG_0003", 0, 6, beats=2, grade="bold"),
        broll("IMG_0004", 1, 9, beats=4, grade="bold", ramp=[2.0, 0.4, 0.3]),   # slow-mo moment
    ], music="upbeat", music_continue=True, music_level=0.9, flash_first=True),
    # channel sting: music carries through and fades out
    sec("logo", [[dict(src=asset("Intro_outro.mp4"), start=0.0, end=2.23, voice=False, raw=True, vol=0)]],
        music="upbeat", music_continue=True, music_level=0.9, music_fade_out=2.0),
    # intro + context, calm track under the talking
    sec("intro", [
        talk("IMG_0010", 0.5, 5.0),
        talk("IMG_0010", 7.1, 10.1),                 # "going for two days"
        talk("IMG_0010", 13.8, 21.2, end_at=21.2),   # end pinned after checking the waveform
    ], music="calm", music_beat=0, music_level=0.12, music_broll=0.85, music_fade_in=3.0),
    sec("first_stop", [
        broll("IMG_0020", 0, 8, beats=6, text=[T(0.3, 3.3, "Place Name|Neighbourhood", "loc")]),
        talk("IMG_0021", 0.0, 14.0),
        broll("IMG_0022", 0, 10, beats=4),
    ], music="calm", music_continue=True, music_level=0.12, music_broll=0.85),
]
clean_montage(sections[1], leak_before="IMG_0003")
add_asides(sections, [])  # e.g. [("IMG_0021", 12.1, "pun intended 🍦")]

write_plan(P, sections,
           tracks={"upbeat": "Upbeat Track.mp3", "calm": "Calm Track.mp3"},
           fixes={"misheard name": "Right Name"},
           out_name="City Vlog.mp4")

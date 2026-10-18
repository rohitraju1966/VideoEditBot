"""Free disk space once a video is posted -- caches and intermediates only, never the finished work.

usage: python3 cleanup.py "Project Name" [--project-dir DIR] [--yes]

Deletes (after showing sizes and asking):
  ~/Movies/Video Editor Cache/<project>/work*        rendered shot cache, music/mix wavs (often 10+ GB)
  <project-dir>/previews/                            preview parts sent for review
  <project-dir>/*_1080p*.mp4 review copies, *.log     (only when a 4K/final file exists)
Keeps:
  final videos (*FINAL*, *4K*), thumbnails/, plan.py / plan.json (re-editable later),
  transcripts + clip info (small; makes a re-edit start instantly), footage, music library, channel assets.
"""
import argparse
import glob
import os
import shutil


def size(p):
    if os.path.isfile(p):
        return os.path.getsize(p)
    return sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(p) for f in fs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--project-dir")
    ap.add_argument("--yes", action="store_true")
    a = ap.parse_args()
    cache = os.path.expanduser(f"~/Movies/Video Editor Cache/{a.project}")
    pdir = os.path.expanduser(a.project_dir or f"~/Desktop/Video Editor/projects/{a.project}")
    targets = glob.glob(os.path.join(cache, "work*")) + glob.glob(os.path.join(pdir, "previews"))
    finals = glob.glob(os.path.join(pdir, "*FINAL*")) + glob.glob(os.path.join(pdir, "*4K*"))
    if finals:
        targets += [f for f in glob.glob(os.path.join(pdir, "*1080p*.mp4")) if f not in finals]
        targets += glob.glob(os.path.join(pdir, "*.log"))
    targets = [t for t in targets if os.path.exists(t)]
    if not targets:
        print("nothing to clean")
        return
    total = 0
    for t in targets:
        s = size(t); total += s
        print(f"  {s / 1e9:6.2f} GB  {t}")
    print(f"total {total / 1e9:.2f} GB.  Kept: {', '.join(os.path.basename(f) for f in finals) or '(no final video found!)'}")
    if not finals:
        print("No final video found in the project folder -- refusing to delete review copies.")
    if not a.yes and input("Delete these? [y/N] ").strip().lower() != "y":
        return
    for t in targets:
        shutil.rmtree(t) if os.path.isdir(t) else os.remove(t)
    print(f"freed {total / 1e9:.2f} GB")


if __name__ == "__main__":
    main()

# NOTES

Moving state. Rules that stay true live in CLAUDE.md.

## Phase

Scaffolding. Nothing built yet — repo initialized, no pipeline stages written.

## Standards

Six ECC skills vendored as markdown into `.claude/skills/` (coding-standards,
git-workflow, github-ops, security-review, python-patterns, python-testing).
Pinned to a commit; see `.claude/skills/PROVENANCE.md`. The ECC *plugin* was
deliberately not installed — its hooks run node on every tool call.

Commits follow Conventional Commits (`feat(scope): ...`), per git-workflow.

**Skills load at session start — restart the session before they are active.**

## Footage

Footage is copied into `raw/` in this project folder (gitignored). Settled
2026-09-07: the laptop files are already copies — the originals live on Rohit's
phone — so `raw/` is the working set, not the last surviving copy. A real copy
rather than a symlink, so "never write to `raw/`" holds without depending on
link-following behaviour.

`~/Desktop/Youtube/2025_recap` was investigated and ruled out. Kept only as a
warning: every file there was iCloud-dataless, so reads blocked on a full
download. Check `stat -f '%Sf' <file>` for `dataless` on whatever lands in
`raw/` before planning a run.

## Open questions

- **Transfer in progress** — waiting on footage landing in `raw/`. File count
  and naming scheme unknown until then.
- **Watch for iCloud-dataless files.** In `2025_recap` every file reported
  `compressed,dataless` with 0 local blocks; reads block on a full download
  (`ffprobe` on one 131 MB file took minutes to return a 14 s duration). If the
  real corpus is offloaded too, transcription is bound by network, not compute —
  and it will hang rather than fail loudly. Materialize locally first.
- faster-whisper not installed. ffmpeg 8.1.2 and Python 3.11.5 are present.

## Last run

None.

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

Candidate corpus: `~/Desktop/Youtube/2025_recap` — 132 videos (122 .MOV, 7 .MP4,
3 .mov), ~15 GB apparent. Also 3 HEIC + 2 PNG stills to exclude, and
`2025Recap.mov` (672 MB) which looks like a previous render, not raw.

## Open questions

- **Blocker: every file is iCloud-dataless.** `stat -f %Sf` reports
  `compressed,dataless` with 0 local blocks on all of them. Reads block on
  network download. `ffprobe` on one 131 MB file eventually succeeded but took
  minutes — it pulls the whole file first. At that rate 15 GB of transcription
  is dominated by download time, not compute. Materialize the corpus locally
  before running anything.
- `raw/` does not exist yet. Decide: copy footage in, or symlink to
  `2025_recap`. Symlink is cheaper but makes the "never write to raw/" rule
  depend on not following the link.
- faster-whisper not installed. ffmpeg 8.1.2 and Python 3.11.5 are present.

## Last run

None.

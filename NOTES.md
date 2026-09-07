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

**Corpus not yet chosen.** `~/Desktop/Youtube/2025_recap` was investigated and
ruled out by Rohit — not the folder to use. Its findings are kept only as a
warning: 132 files, ~15 GB, and every one iCloud-dataless.

Whatever folder is chosen, check `stat -f '%Sf' <file>` for `dataless` before
planning a run.

## Open questions

- **Which folder is the corpus?** Blocking everything downstream.
- **Watch for iCloud-dataless files.** In `2025_recap` every file reported
  `compressed,dataless` with 0 local blocks; reads block on a full download
  (`ffprobe` on one 131 MB file took minutes to return a 14 s duration). If the
  real corpus is offloaded too, transcription is bound by network, not compute —
  and it will hang rather than fail loudly. Materialize locally first.
- `raw/` does not exist yet. Decide: copy footage in, or symlink. Symlink is
  cheaper but makes the "never write to raw/" rule depend on not following the
  link. Leaning copy.
- faster-whisper not installed. ffmpeg 8.1.2 and Python 3.11.5 are present.

## Last run

None.

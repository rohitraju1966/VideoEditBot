# Changelog

## 0.1.1 — 2026-10-18
Fixes from the first fresh-agent smoke test (Magnolia Bakery draft: passed, 0 flags, 0.1 ms A/V drift).
- write_plan probes every shot source (hand-written asset dicts no longer crash render/check); example uses `asset()`.
- Caption fixes applied once (no doubled punctuation).
- `transcribe.py --lang` (snippets default to English -- no more hallucinated other languages); offline when the model is cached.
- `verify.py cut`: voice-band filter and noise-floor-relative speech marks (street footage).
- `check_plan.py`: no MID-SENTENCE false positive at clip end; `--captions` also proof-reads titles/tags/end cards.
- `clips.py` accepts individual clip files; `sec()` no longer flashes every section (`flash_first=True` to opt in).
- Pillow 13 compatibility; docs: venv Python, short-draft guidance, per-shot caption workaround.

## 0.1.0 — 2026-10-18
First release, extracted from editing a 9.5-minute New York travel vlog (Frost Tube).
- Render engine: GPU HDR→SDR, rotation fixes, Live Photo handling, per-shot cache with atomic writes,
  per-shot A/V length fix (no sync drift), beat-aligned cuts, continuing songs, speech-aware music bed,
  two-pass loudness, captions snapped to voice onset, titles/location tags/asides/end cards, transitions.
- Tools: footage inventory & contact sheets, local transcription (+ snippet check), beat analysis,
  pre-render checks, output verification, house-style thumbnails with Apple Vision cut-out, cleanup.
- SKILL.md workflow + editing rules; lessons learned; channel profile template.

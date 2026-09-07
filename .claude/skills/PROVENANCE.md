# Vendored skills — provenance

These skills are copied verbatim from the third-party repo
[affaan-m/ECC](https://github.com/affaan-m/ECC) ("Everything Claude Code", MIT).

- Pinned commit: `cf065358fb67b710d8ac90597b57719b75c632c4`
- Fetched: 2026-09-07
- Vendored: `coding-standards`, `git-workflow`, `github-ops`, `security-review`,
  `python-patterns`, `python-testing` (6 of the repo's 286 skills)

## What was deliberately NOT taken

The ECC plugin was **not** installed. Installing it registers `PreToolUse` hooks
that run `node` on every `Bash`, `Write`, and `Edit`, plus one matching `.*`
(every tool call). Only these markdown files were vendored — nothing executable,
no hooks, no agents, no command shims.

To re-verify or update, re-fetch at a new pinned SHA and re-read the diff. Do not
switch to the plugin install without deciding about the hooks again.

## Precedence

`CLAUDE.md` at the repo root wins over anything here. Where they disagree — ECC
assumes a team codebase, this is a solo personal tool — CLAUDE.md's "simplest
approach that works" and "resist adding dependencies" rules take priority.

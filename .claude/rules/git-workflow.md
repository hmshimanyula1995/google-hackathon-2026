---
description: Commits, deploys, hackathon scope discipline.
---

# Git, deploys, scope

## Commits
- No Claude attribution.
- Concise messages focused on the WHY.
- **Commit only when requested** — Hudson drives the commit cadence on this repo.

## GitHub account
This repo is `hmshimanyula1995/google-hackathon-2026`. Before pushing:
```bash
gh auth switch --user hmshimanyula1995
```

## Hackathon scope (HARD)
- Deadline: **2026-03-16 @ 5:00 PM PT**. Don't expand scope.
- New features need to demonstrably matter for the demo or judging.
- Refactors are fine if they keep the demo working — verify with a local run.
- **Don't break the live audio path.** Test stage 1 (REST), stage 2 (WebSocket concierge), stage 3 (WebSocket keynote) end-to-end before any merge.

## Deploy discipline
- `./deploy.sh` only. Don't sidestep with raw `gcloud run deploy`.
- After a deploy, verify the live URL still works before walking away.

## Mandatory agent behavior
1. Before writing code, describe your approach. Ask clarifying questions if ambiguous.
2. After writing code: confirm what was tested locally; if it touched WebSockets or A2A, confirm interruption still works.
3. For bugs: write a minimal reproducer first; then fix.
4. Continuous Learning Loop on conflicts (see `~/.claude/CLAUDE.md`).

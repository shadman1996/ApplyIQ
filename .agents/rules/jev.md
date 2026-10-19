---
trigger: always_on
description: "TypeSafe AI Jev System 1 Decision Router Policy"
---

# Jev System 1 Decision Router Policy

Before substantial browser research, repeating a failed approach, loading several tools or skills, spawning agents, choosing between materially different execution routes, or proposing a consequential action, consider whether a small bounded Jev decision would change the next step. If yes, build a compact state without secrets, call the installed router (`core/jev_router.py`), interpret its action, and continue the original task. Skip Jev for simple answers, deterministic calculations, routine file edits, and situations where the call adds no useful decision. Respect 'bypass jev'. Keep irreversible actions behind human confirmation.

## Operational Standards
- **Shadow Mode First**: Router starts in `shadow` mode logging to `logs/jev_decisions.jsonl`.
- **Zero Token Gatekeeping**: Always check `core/second_brain.py` and Jev triage before invoking heavy Gemini LLM calls.
- **Circuit Breaker**: When an automation or tool action fails twice consecutively, call `decide_failure_recovery` instead of blindly repeating.

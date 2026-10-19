---
trigger: always_on
description: "ECC Agent Harness Performance and Token Optimization Guidelines"
---

# ECC Performance & Token Optimization

Adapted from the ECC Agent Harness Operating System (affaan-m/ECC).
**Core Principle: Optimize the context window. Persist everything else.**

## 1. Model Tiering & Token Economics
- **System 1 (Jev / Heuristics)**: Non-autoregressive sub-15ms typed decisions (`Choice`, `Score`, `Noul`) for routing, triage, and circuit breakers. Cost: ~$0.042 / 1M tokens.
- **Fast Tier (Gemini 3.8 Flash)**: Fast form filling, structured extractions, and single-turn task reasoning.
- **Deep Reasoning Tier (Pro models)**: Multi-step architecture reviews, complex debugging, and security policy authoring only when requested.
- **Second Brain Memory Vault (`core/second_brain.py`)**: Instant 0-token persistent cache for repeated questions (candidate profile, visa, education, EEO disclosures).

## 2. Context Window Management
- Do not dump thousands of raw DOM lines or unparsed network logs into agent context.
- Summarize tool outputs and pass objective context instead of raw unstructured blobs.
- Avoid the last 20% of the context window for complex multi-file edits or multi-step browser automation to prevent context rot.

## 3. Fast Tools vs Context Eaters
- Use focused ripgrep / ast-grep instead of loading giant files.
- Keep automation logic modular; prefer small single-purpose methods over monolithic classes.

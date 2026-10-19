---
trigger: always_on
description: "ECC Autonomous Execution Loop and Verification Pattern"
---

# ECC Autonomous Execution Loop Pattern

Adapted from ECC (affaan-m/ECC):
```text
plan -> test -> implement -> review -> verify -> remember -> improve
```

## Protocol for Automation Workflows:
1. **Plan**: Formulate the target steps and verify prerequisites before launching browser instances.
2. **Test / Triage**: Use Jev System 1 router (`core/jev_router.py`) to triage portal type, question actions, and recovery paths.
3. **Implement**: Execute actions with DOM resilience (`click_filter` overlay bypass, combobox resolvers, keyboard typing).
4. **Review & Verify**: Inspect DOM after submit or step advance (e.g. check for error banners, invalid inputs, or confirmation headers).
5. **Remember**: Record newly resolved answers and portal behavior into `core/second_brain.py` and `logs/`.
6. **Improve**: Adapt retry strategies dynamically if a step encounters obstacles.

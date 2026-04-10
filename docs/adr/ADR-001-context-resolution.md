# ADR-001: Context Resolution Layer

## Problem
Pronouns ('this', 'those', 'them', 'compare those') don't resolve to specific part numbers.
Validation questions ('does this work for medical?') don't check specs against requirements.
Each bug was being fixed individually in router.py — band-aid approach.

## Decision
Build `ContextResolver` class that runs BEFORE intent classification.
Resolves all context in one pass, not per-query fixes.

## Implementation
- `context_resolver.py` — resolve_message(), validate_application_fit()
- `conversation_memory_cosmos.py` — resolve_coreference(), recommended_parts storage
- `router.py` — ContextResolver wired in at top of handle_message()

## How It Works
1. User says "compare those"
2. ContextResolver detects pronoun
3. Queries Cosmos for last turn's recommended_parts
4. Injects resolved parts into message: "compare those [Context: referring to HC9600EOS13H, HC9600FAN13Z]"
5. Router classifies intent with full context
6. GPT sees the actual part numbers, not just "those"

## Rejection
NOT fixing individual queries in router.py.
NOT adding per-part-number if/else blocks.
Build the layer once, fix all validation queries.

## Status
- [x] context_resolver.py created
- [x] Wired into router.py
- [x] Cosmos recommended_parts storage
- [ ] End-to-end test with 5 scenarios
- [ ] Application validation with spec checking

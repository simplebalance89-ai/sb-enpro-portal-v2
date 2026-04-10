# Enpro Mastermind v3.0 Gap Analysis
Updated: 2026-04-10

## Critical (Launch Blockers)
- [x] Azure OpenAI Connection: `max_tokens` → `max_completion_tokens` for newer models
- [x] Azure OpenAI Connection: `temperature=0` rejected by all 5 deployed models
- [x] Azure AI Search: 19,470 products indexed, `search_azure.py` built
- [x] Context Resolution: ContextResolver class built (`context_resolver.py`)
- [x] Cosmos DB: Conversation memory wired (`enpro-sessions`)
- [ ] Coreference Chain: History-based "compare those" needs recommended_parts persisted and resolved
- [ ] Application Validation: "does this work for X" needs full spec checking
- [ ] Product Cards: Picks from pregame/application show text blobs, not full product cards
- [ ] Database: No Azure Postgres for auth — running in no-auth mode

## High (Week 1)
- [ ] Voice Service: Azure Speech SDK integrated but not tested end-to-end
- [ ] v3 Mastermind SDK: AzureOpenAI SDK hangs on `.openai.azure.com` endpoint — needs debugging
- [ ] Response Formatting: Duplicate/out-of-stock items in "Other options"
- [ ] Price Accuracy: Inventory merge failed on index (Part_Number column mismatch)

## Medium (Week 2)
- [ ] Mobile Optimization: Voice-first UI working but not prioritized
- [ ] Multi-turn References: "the first one", "that other filter" (beyond simple pronouns)
- [ ] Key Vault: Created but secrets still in env vars, not fetched from KV
- [ ] Managed Identity: Container App uses API keys, not RBAC
- [ ] Auto-scale Rules: No HTTP-based triggers, just min/max replicas
- [ ] Manufacturer Mapping: Display name file missing from container

## Architecture Decisions
- See `docs/adr/` for decision records
- ContextResolver handles ALL validation questions architecturally
- Legacy router.py + azure_client.py handles chat (v3 SDK wrapper caused timeouts)
- Cosmos DB (enpro-sessions) for conversation memory, Postgres for auth when available

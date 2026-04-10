# Enpro Filtration Mastermind v3.0 - Modular AI Architecture

## Sales-First Approach

This architecture prioritizes sales enablement over chemical complexity:
1. **Customer Pregame** (strategic reasoning) → Highest priority
2. **Part Lookup** (voice + text) → Fast resolution
3. **Compare Products** (reasoning-driven) → Clear recommendations
4. **Quote State** (entity extraction) → Track context
5. **Chemical** (hardcoded) → Zero AI cost

## Model Routing Strategy

| Feature | Model | Cost | Reasoning |
|---------|-------|------|-----------|
| Intent Classification | Phi-4 or Pattern | ~$0.0001 | Simple routing |
| Pregame Strategy | o3-mini-high | ~$0.015 | Visible reasoning trace |
| Voice Part Resolution | GPT-5.4 Mini | ~$0.003 | Phonetic → Part number |
| Compare Products | o3-mini | ~$0.008 | Side-by-side reasoning |
| Quote Extraction | GPT-5.4 Mini | ~$0.003 | Entity extraction |
| Chemical Lookup | Hardcoded | $0 | A/B/C/D matrix |
| Safety Escalation | o3-pro | ~$0.05 | Critical checks |

## Directory Structure

```
├── api/                    # FastAPI route handlers
│   ├── chat.py            # Main chat endpoints
│   ├── voice.py           # Voice processing
│   └── health.py          # Health checks
├── gateway/               # Request routing layer
│   └── sales_router.py    # Sales-first intent router
├── models/                # AI model abstractions
│   ├── model_router.py    # Azure model selector
│   ├── reasoning_engine.py # Pregame/compare reasoning
│   ├── classifier.py      # Intent classification
│   ├── chemical_expert.py # Hardcoded lookups
│   └── voice_resolver.py  # Phonetic resolution
├── services/              # Business logic
│   ├── search_service.py
│   ├── quote_service.py
│   └── customer_service.py
├── utils/                 # Utilities
└── config.py             # Settings with new model deployments
```

## Key Improvements

### 1. Reasoning Trace Visibility
Reps see the model's thinking process:
```json
{
  "thinking_trace": [
    "Step 1: Customer 'Acme Brewing' - Last order March 18, $34K Filtrox sheets",
    "Step 2: Industry 'Brewery' triggers: yeast carryover risk",
    "Step 3: Recent pattern → they buy depth sheets, likely need membrane upgrade",
    "Step 4: Strategic angle: Position Pall Supor as consistency upgrade"
  ]
}
```

### 2. Hardcoded Chemical Lookups
- Only 5 chemicals with hardcoded A/B/C/D ratings
- Everything else → "Contact Enpro engineering with SDS"
- Zero AI cost for chemical queries

### 3. Voice Part Resolution
- Azure Speech-to-Text with phonetic model
- GPT-5.4 Mini resolves "aitch see ninety six oh oh" → HC9600
- 85% cost reduction vs Whisper → GPT-4.1 pipeline

### 4. Pattern-Based Intent Classification
- Common intents matched via regex (zero cost)
- Phi-4 fallback for complex cases
- 98% cost reduction vs GPT-4.1-mini

## Environment Configuration

New environment variables for v3.0:

```bash
# Model Deployments (Azure OpenAI)
AZURE_DEPLOYMENT_FAST=gpt-5.4-mini
AZURE_DEPLOYMENT_STANDARD=gpt-5.4
AZURE_DEPLOYMENT_REASONING=o3-mini
AZURE_DEPLOYMENT_STRATEGIC=o3-mini-high
AZURE_DEPLOYMENT_SAFETY=o3-pro
AZURE_DEPLOYMENT_CLASSIFIER=phi-4

# Azure Speech Services (for voice)
AZURE_SPEECH_ENDPOINT=https://...
AZURE_SPEECH_KEY=...
AZURE_SPEECH_REGION=eastus

# Feature Flags
USE_MODULAR_MODELS=true
USE_HARDCODED_CHEMICAL=true
ENABLE_REASONING_TRACE=true
```

## Migration Guide

### Phase 1: Deploy New Models (Week 1)
1. Deploy o3-mini-high for pregame
2. Add reasoning trace to UI
3. Switch voice to Azure STT + GPT-5.4 Mini

### Phase 2: Simplify Chemical (Week 2)
1. Replace chemical AI prompts with hardcoded lookups
2. Route unknown chemicals to "Contact engineering"

### Phase 3: Optimize Classification (Week 3)
1. Deploy Phi-4 for intent classification
2. Add pattern matching pre-filter

### Phase 4: Cleanup (Week 4)
1. Remove legacy router.py
2. Deprecate voice_echo.py phonetic matching
3. Delete complex chemical prompts

## Cost Comparison

| Feature | v2.16 Cost | v3.0 Cost | Savings |
|---------|-----------|-----------|---------|
| Intent Classification | $0.002 | $0.0001 | 95% |
| Pregame Strategy | $0.04 | $0.015 | 62% |
| Voice Part Lookup | $0.025 | $0.003 | 88% |
| Compare Products | $0.02 | $0.008 | 60% |
| Chemical Lookup | $0.02 | $0 | 100% |
| **Average Request** | **$0.04** | **$0.008** | **80%** |

## API Endpoints

New v2 API (modular):
- `POST /api/v2/chat` - Main chat with reasoning trace
- `POST /api/v2/pregame` - Strategic pregame briefing
- `POST /api/v2/compare` - Reasoning-driven comparison
- `GET /api/v2/chemical/{name}` - Hardcoded lookup
- `GET /api/v2/stats` - Cost and usage stats

Legacy v1 API (still available):
- `POST /api/chat` - Existing endpoint

## UI Updates

### Reasoning Trace Display
```javascript
// Show thinking trace in collapsible section
<div class="reasoning-trace">
  <button onclick="toggleTrace()">Show reasoning ({model_used})</button>
  <div class="trace-content">
    {thinking_trace.map(step => <div>{step}</div>)}
  </div>
</div>
```

### Model Indicator
```javascript
// Show which model answered
<Message 
  model={response.model_used}
  cost={response.cost_usd}
  latency={response.latency_ms}
>
  {response.headline}
</Message>
```

## Safety & Validation

- All part number recommendations validated against catalog
- Safety keywords (hydrogen, H2S, >400F) force o3-pro
- Chemical escalations for unknown substances
- Reasoning traces include citation validation

## Testing Strategy

1. **Unit Tests**: Each model handler independently
2. **Integration Tests**: Full routing pipeline
3. **Cost Tracking**: Verify per-request costs
4. **Reasoning Validation**: Check trace quality
5. **Voice Resolution**: Phonetic accuracy tests

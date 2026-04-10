# Model Strategy - Clarification

## Which Models Are Used Where?

### Current Setup (mastermind_v3.py)

| Task | Model | Cost | Why |
|------|-------|------|-----|
| **Main reasoning** | `o3-mini-high` | ~$0.015 | Complex reasoning, thinking traces |
| **Narrowing 20→3 products** | `gpt-5.4-mini` | ~$0.003 | Fast, cheap selection |

### Alternative: Phi-4 Integration

If you want to use **Phi-4** (Azure AI Foundry) for even lower costs:

```python
# In mastermind_v3.py, replace the classifier section:

# CURRENT:
# Uses o3-mini for everything (simple, but not cheapest)

# WITH PHI-4 (cheaper):
# Add this to check if we even need product search:

async def chat(self, message: str, ...):
    # Step 0: Phi-4 classifies if this needs product lookup
    needs_products = await self._phi4_classify(message)
    
    if not needs_products:
        # General conversation - use cheap model
        return await self._phi4_response(message)
    
    # Needs products - use o3-mini for reasoning
    ...
```

## Updated Model Config (Using Phi-4)

```python
# mastermind_v3.py - Add Phi-4

class MastermindV3:
    def __init__(self):
        # Existing models
        self.REASONING_MODEL = "o3-mini-high"      # Complex reasoning
        self.FAST_MODEL = "gpt-5.4-mini"           # Narrowing
        
        # Add Phi-4 via Azure AI Foundry
        self.CLASSIFIER_MODEL = "phi-4"            # Intent classification
        self.CHEAP_MODEL = "phi-4-mini"            # Simple responses
```

## Phi-4 Setup in Azure AI Foundry

1. Go to [Azure AI Foundry](https://ai.azure.com)
2. Create project
3. Deploy models:
   - `phi-4` (for classification)
   - `o3-mini` (for reasoning)
   - `gpt-5.4-mini` (for fast tasks)

4. Get connection string for Phi-4

## Cost Comparison

| Approach | Cost per request | Best for |
|----------|-----------------|----------|
| **o3-mini only** (current) | ~$0.015 | Simple setup, best reasoning |
| **Phi-4 + o3-mini** | ~$0.008 | Cost-optimized, 2-model routing |
| **Phi-4 only** | ~$0.002 | Simple Q&A, no complex reasoning |

## Which Should You Use?

### Option A: Keep Current (o3-mini + gpt-5.4-mini)
✅ Simpler code  
✅ Best reasoning quality  
❌ Slightly more expensive  

### Option B: Add Phi-4 (Recommended for cost)
✅ 50% cheaper  
✅ Phi-4 handles simple queries  
✅ o3-mini only for complex reasoning  
❌ More complex routing logic  

## Quick Fix - Add Phi-4 Classification

Want me to update `mastermind_v3.py` to use Phi-4 for classification before o3-mini?

```python
# Add this method:
async def _phi4_classify(self, message: str) -> bool:
    """Phi-4 decides if we need product lookup"""
    response = self.client.chat.completions.create(
        model="phi-4",
        messages=[{
            "role": "system",
            "content": "Classify: does this query need product catalog lookup? Reply YES or NO only."
        }, {
            "role": "user", 
            "content": message
        }],
        temperature=0.0,
        max_tokens=10
    )
    return "YES" in response.choices[0].message.content.upper()
```

**Should I add this Phi-4 classification to the code?** (saves ~50% cost on simple queries)

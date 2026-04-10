# 3-Day Azure Migration - Implementation Guide

## ⚡ The Goal
Transform your command-line database tool into a conversational AI sales assistant in 72 hours.

## 🗓️ Day 1: Kill Intent Routing (Friday)

### Morning (4 hours): Deploy Unified Handler

#### Step 1: Copy Files
```bash
# Copy the new files into your project
cp mastermind_v3.py your-project/
cp voice_v3.py your-project/
```

#### Step 2: Update Environment Variables
Add to your `.env`:
```bash
# Azure OpenAI (switch from OpenAI to Azure)
AZURE_OPENAI_ENDPOINT=https://enpro-filtration-ai.services.ai.azure.com/
AZURE_OPENAI_KEY=your-key

# Model deployments (create these in Azure AI Foundry)
AZURE_DEPLOYMENT_REASONING=o3-mini-high
AZURE_DEPLOYMENT_FAST=gpt-5.4-mini

# Feature flags
USE_UNIFIED_HANDLER=true
USE_INTENT_ROUTING=false
```

#### Step 3: Modify server.py
Replace your `/chat` endpoint:

```python
# OLD (in server.py):
from router import handle_message

@app.post("/chat")
async def chat(request: ChatRequest):
    result = await handle_message(request.message, ...)
    return result

# NEW:
from mastermind_v3 import init_mastermind, chat_endpoint

# Initialize on startup
@app.on_event("startup")
async def startup():
    init_mastermind(state.df)  # Your existing dataframe

@app.post("/chat")
async def chat(request: ChatRequest):
    return await chat_endpoint(request)
```

#### Step 4: Test Immediately
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "HC9600 price", "session_id": "test-123"}'
```

Expected: Conversational response, not "400 products found"

### Afternoon (4 hours): Fix Andrew's Example

Test this exact query:
```
"I'm meeting with a data center operator tomorrow. They're interested in filters for the HVAC system of their high-powered data center. Can you help me?"
```

**Bad Response (Old):**
> "I found 400 products. Say 'lookup' for details."

**Good Response (New):**
> "Absolutely. Data center HVAC is high-demand — high airflow, tight particulate control, filter longevity matters because downtime is expensive.
>
> A few questions:
> - Do you know what MERV rating they run, or target efficiency?
> - What filter size — standard 24x24 or custom?
> - Is the concern filter life, efficiency, or both?
>
> Meanwhile, I'd start with multi-pleat extended surface filters for high dirt-holding capacity. Available MERV 11-15. Want me to pull specifics once you have those details?"

If it doesn't sound like that, tweak `SYSTEM_PROMPT_V3` in `mastermind_v3.py`.

### Evening: Deploy to Render (Quick Test)
```bash
git add mastermind_v3.py voice_v3.py
git commit -m "Add unified conversational handler v3"
git push origin main
# Render auto-deploys
```

---

## 🗓️ Day 2: Fix Search (Saturday)

### Morning (4 hours): Cap Search Results

#### Step 1: Update Search Function
In `search.py`, add the narrowing logic:

```python
async def search_products_narrowed(df, query, context=None):
    """Returns max 3 products with reasoning."""
    
    # Your existing search
    results = search_products(df, query)  # Returns up to 400
    
    # If too many, use fast model to pick best 3
    if len(results) > 5:
        results = await narrow_with_reasoning(query, results[:20])
    
    return results[:3]
```

#### Step 2: Add Narrowing Function
```python
async def narrow_with_reasoning(query: str, products: list) -> list:
    """Use GPT-5.4-mini to pick best 3."""
    
    client = AzureOpenAI(...)
    
    response = client.chat.completions.create(
        model="gpt-5.4-mini",
        messages=[{
            "role": "system",
            "content": "Pick 3 best products. Return: {\"top_3\": [\"PN1\", \"PN2\", \"PN3\"]}"
        }, {
            "role": "user",
            "content": f"Query: {query}\nProducts: {products[:20]}"
        }],
        response_format={"type": "json_object"}
    )
    
    parsed = json.loads(response.choices[0].message.content)
    top_3 = parsed.get("top_3", [])
    
    # Filter to top 3
    return [p for p in products if p.get("Part_Number") in top_3][:3]
```

#### Step 3: Update MastermindV3
In `mastermind_v3.py`, change `_search_products` to use `search_products_narrowed`.

### Afternoon (4 hours): Test Conversations

Run the test script:
```bash
cd azure-migration/tests
python test_migration.py
```

Expected output:
```
🧪 Testing: I'm meeting with a data center operator...
   ✅ Conversational tone
   ✅ Asks clarifying question
   ✅ Max 3 products
   
🧪 Testing: HC9600 price...
   ✅ Specific product
   ✅ Includes price
   
Passed: 6/6 (100%)
```

If any fail, adjust the system prompt.

### Evening: Voice Cleanup (Optional)

Simplify voice handling:
```bash
# Comment out these files (don't delete yet)
# voice_echo.py - complex predictive prefetch
# voice_search.py - 4-tier lookup

# Keep only:
# voice_gate.py - simplified to 1 tier + reasoning
```

---

## 🗓️ Day 3: Azure Deployment (Sunday)

### Morning (4 hours): Infrastructure

#### Step 1: Azure Login
```bash
az login
az account set --subscription "your-subscription"
```

#### Step 2: Deploy Core Infrastructure
```bash
cd azure-migration

# Deploy Search + Cosmos + Container Apps
./deploy.sh
```

This creates:
- Azure AI Search (product catalog)
- Cosmos DB (session state)
- Container Apps (API hosting)

#### Step 3: Migrate Data
```bash
# Set environment variables
export AZURE_SEARCH_ENDPOINT=https://enpro-search.search.windows.net
export AZURE_SEARCH_KEY=your-key
export AZURE_OPENAI_ENDPOINT=https://enpro-openai.openai.azure.com/
export AZURE_OPENAI_KEY=your-key

# Run migration
python scripts/migrate_data.py
# Takes ~30 minutes for 19,470 products
```

### Afternoon (4 hours): Deploy Application

#### Step 1: Build & Push Container
```bash
# Build Docker image
az acr build \
  --registry enproregistry \
  --image enpro-mastermind:v3.0 \
  --file Dockerfile ..
```

#### Step 2: Update Frontend
In `static/app.js`, change:
```javascript
// OLD:
const API_BASE = window.ENPRO_API_BASE || '';

// NEW:
const API_BASE = 'https://enpro-mastermind.southcentralus.azurecontainerapps.io';
```

#### Step 3: Deploy Frontend
```bash
# Deploy to Azure Static Web Apps
az staticwebapp deploy \
  --name enpro-mastermind-web \
  --resource-group enpro-production \
  --source ../static
```

### Evening: Testing & Cutover

#### Step 1: Smoke Tests
```bash
# Test health
curl https://your-app.azurecontainerapps.io/health

# Test chat
curl -X POST https://your-app.azurecontainerapps.io/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "HC9600 price", "session_id": "test"}'
```

#### Step 2: Compare Old vs New
```bash
python azure-migration/tests/test_migration.py
```

#### Step 3: DNS Cutover (if ready)
If tests pass, update your DNS to point to Azure.

---

## 🚨 Emergency Rollback

If something breaks:

```bash
# Revert to old router
git checkout HEAD~1 -- router.py server.py

# Redeploy to Render
git push origin main
```

---

## 📋 Files Changed Summary

| File | Action | Lines |
|------|--------|-------|
| `mastermind_v3.py` | CREATE | 400 |
| `voice_v3.py` | CREATE | 100 |
| `server.py` | MODIFY | ~20 |
| `router.py` | DELETE (comment out) | -700 |
| `voice_echo.py` | DELETE (comment out) | -1500 |
| `voice_search.py` | DELETE (comment out) | -400 |

---

## 💰 Cost Comparison

| Component | Render (Current) | Azure (New) | Monthly |
|-----------|-----------------|-------------|---------|
| Compute | $25 | Container Apps | $20-50 |
| Database | PostgreSQL $15 | Cosmos DB | $25 |
| Search | In-memory (free) | AI Search | $75 |
| AI | ~$600 | Same models | ~$400 |
| **Total** | **~$640** | | **~$520** |

**Savings: ~20% + 10x better performance**

---

## ✅ Success Criteria

After 3 days, verify:

- [ ] Query "data center HVAC" returns conversational response (not "400 products")
- [ ] Query "HC9600" returns specific product with reasoning
- [ ] Voice queries work with simplified flow
- [ ] System remembers context across 3+ turns
- [ ] Response time < 3 seconds
- [ ] Deployed to Azure (or Render with new code)

---

## 🆘 Getting Help

If stuck on Day 1:
1. Check Azure OpenAI quotas (need o3-mini access)
2. Verify `AZURE_OPENAI_ENDPOINT` format
3. Test with `curl` before hitting the UI

If stuck on Day 2:
1. Simplify the narrowing (just return first 3 if model fails)
2. Increase timeout for embedding generation

If stuck on Day 3:
1. Stay on Render, just use new code
2. Azure migration can wait until next week

---

**The Goal:** Conversational AI by Sunday night.

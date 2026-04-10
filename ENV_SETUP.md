# Environment Variables Setup Guide

## Quick Start (Minimum Required)

To get the new v3.0 unified handler running, you only need these 4 variables:

```bash
# 1. Copy the example file
cp .env.example .env

# 2. Edit .env and fill in these required values:
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_KEY=your-azure-openai-key-here
AZURE_DEPLOYMENT_REASONING=o3-mini-high
AZURE_DEPLOYMENT_FAST=gpt-5.4-mini

# 3. Set feature flags
USE_UNIFIED_HANDLER=true
USE_INTENT_ROUTING=false
```

## Getting Your Azure OpenAI Credentials

### Step 1: Find Your Endpoint
1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to your Azure OpenAI resource
3. Look for "Endpoint" - copy the full URL
4. Example: `https://enpro-openai.openai.azure.com/`

### Step 2: Get Your API Key
1. In Azure Portal, go to your OpenAI resource
2. Click "Keys and Endpoint" in the left menu
3. Copy either "KEY 1" or "KEY 2"

### Step 3: Create Model Deployments
1. Go to [Azure AI Foundry](https://ai.azure.com)
2. Select your project
3. Go to "Deployments"
4. Create these deployments:
   - **Name:** `o3-mini-high` (or your preference)
   - **Model:** `o3-mini`
   - **Version:** Latest
   
   - **Name:** `gpt-5.4-mini` (or your preference)
   - **Model:** `gpt-5.4-mini`
   - **Version:** Latest

5. Use the deployment names in your `.env` file

## Deployment Modes

### Mode 1: Quick Fix on Render (Use Current Code)
**Required vars:**
```bash
AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_KEY=
AZURE_DEPLOYMENT_REASONING=
AZURE_DEPLOYMENT_FAST=
USE_UNIFIED_HANDLER=true
USE_INTENT_ROUTING=false
DATABASE_URL=  # Your existing Render PostgreSQL
```

### Mode 2: Full Azure Migration
**Required vars:**
```bash
# All of the above, PLUS:
AZURE_SEARCH_ENDPOINT=
AZURE_SEARCH_KEY=
AZURE_COSMOS_ENDPOINT=
AZURE_COSMOS_KEY=
AZURE_SPEECH_KEY=
AZURE_SPEECH_REGION=
```

## Testing Your Setup

After setting up `.env`, test with:

```bash
# 1. Load environment
source .env

# 2. Test backend
python -c "
from mastermind_v3 import MastermindV3
import pandas as pd

df = pd.read_csv('export.csv')
m = MastermindV3(df)
print('✅ Backend initialized')
"

# 3. Start server
python server.py
```

## Troubleshooting

### "Endpoint not found"
- Check `AZURE_OPENAI_ENDPOINT` format
- Should end with `/` and include `https://`

### "Deployment not found"
- Verify deployment names match exactly
- Check that deployments are in the same region

### "Authentication failed"
- Regenerate keys in Azure Portal
- Copy key exactly (no extra spaces)

### "o3-mini not available"
- Some regions don't have o3-mini yet
- Try: `eastus`, `southcentralus`, `westeurope`
- Or use `gpt-4o` as fallback

## Render Specific Setup

If deploying to Render:

1. Go to Render Dashboard
2. Select your service
3. Click "Environment"
4. Add each variable from `.env`

Or use Render CLI:
```bash
render env set AZURE_OPENAI_ENDPOINT "https://your-resource.openai.azure.com/"
render env set AZURE_OPENAI_KEY "your-key"
# ... etc
```

## Azure Deployment

For Azure Container Apps, set vars in Bicep template or Azure Portal:

```bash
# Set as Container App secrets
az containerapp secret set \
  --name enpro-mastermind \
  --resource-group enpro-production \
  --secrets \
    openai-key=your-key \
    cosmos-key=your-cosmos-key
```

## Security Notes

⚠️ **Never commit `.env` to GitHub!**
- `.env` is in `.gitignore` by default
- Use `.env.example` for documentation
- Rotate keys regularly
- Use different keys for dev/prod

## Need Help?

Check:
1. `IMPLEMENTATION_SUMMARY.md` - Full overview
2. `3DAY_IMPLEMENTATION_GUIDE.md` - Deployment steps
3. Azure Portal - Verify resource status

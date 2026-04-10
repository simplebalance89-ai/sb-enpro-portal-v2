#!/bin/bash
# Deploy Enpro FM v3.0 to Azure Container Apps
# Usage: ./scripts/deploy_azure.sh

set -e

RG="rg-enpro-ai"
ACR="enprofm20260328"
APP="enpro-fm-mastermind-gctii"
IMAGE="roundtable/mastermind"
TAG="v3.0-azure"

echo "🏗️  Building Docker image..."
az acr build --registry $ACR --image $IMAGE:$TAG . --no-logs

echo "🚀 Updating Container App..."
az containerapp update \
  --name $APP \
  --resource-group $RG \
  --image $ACR.azurecr.io/$IMAGE:$TAG \
  --cpu 1 --memory 2Gi \
  --min-replicas 0 --max-replicas 3

echo "⚙️  Setting environment variables..."
az containerapp update \
  --name $APP \
  --resource-group $RG \
  --set-env-vars \
    PORT=8000 \
    USE_UNIFIED_HANDLER=true \
    USE_PHI4_ROUTING=true \
    USE_MODULAR_MODELS=true \
    AZURE_DEPLOYMENT_CLASSIFIER=phi-4-classifier \
    AZURE_DEPLOYMENT_FAST=gpt-4.1-mini \
    AZURE_DEPLOYMENT_REASONING=o4-mini-reasoning \
    AZURE_DEPLOYMENT_STRATEGIC=gpt-4.1 \
    AZURE_DEPLOYMENT_ROUTER=gpt-5-mini \
    AZURE_OPENAI_API_VERSION=2026-01-01 \
    AZURE_SEARCH_ENDPOINT=https://enpro-ai-search.search.windows.net \
    AZURE_SEARCH_INDEX=enpro-products \
    AZURE_SPEECH_REGION=eastus \
    COSMOS_DATABASE=enpro-fm

echo ""
echo "✅ Deployed $IMAGE:$TAG to $APP"
echo "🌐 URL: https://$(az containerapp show --name $APP --resource-group $RG --query properties.configuration.ingress.fqdn -o tsv)"
echo ""
echo "⚠️  Don't forget to set secrets via Azure portal or CLI:"
echo "  AZURE_OPENAI_KEY, AZURE_SEARCH_KEY, AZURE_SPEECH_KEY,"
echo "  COSMOS_KEY, DATABASE_URL, SESSION_SECRET"

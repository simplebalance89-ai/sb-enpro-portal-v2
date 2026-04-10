#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# QUICK START - 3 Day Migration
# Run this to get started immediately
# ═══════════════════════════════════════════════════════════════════════════════

echo "🚀 Enpro Mastermind V3 - Quick Start"
echo "======================================"
echo ""

# Check prerequisites
echo "📋 Checking prerequisites..."

if ! command -v python &> /dev/null; then
    echo "❌ Python not found. Please install Python 3.11+"
    exit 1
fi

if ! command -v az &> /dev/null; then
    echo "❌ Azure CLI not found. Please install: https://aka.ms/installazurecli"
    exit 1
fi

echo "✅ Prerequisites OK"
echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 1: Backup Current Code
# ═══════════════════════════════════════════════════════════════════════════════
echo "💾 Creating backup..."
mkdir -p backup
cp router.py backup/router.py.bak
cp server.py backup/server.py.bak
cp voice_echo.py backup/voice_echo.py.bak
cp voice_search.py backup/voice_search.py.bak
echo "✅ Backup created in backup/"
echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 2: Install New Files
# ═══════════════════════════════════════════════════════════════════════════════
echo "📦 Installing new unified handler..."

# Check if files exist
if [ ! -f "mastermind_v3.py" ]; then
    echo "❌ mastermind_v3.py not found. Please copy it to this directory."
    exit 1
fi

if [ ! -f "voice_v3.py" ]; then
    echo "❌ voice_v3.py not found. Please copy it to this directory."
    exit 1
fi

echo "✅ New files present"
echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 3: Environment Setup
# ═══════════════════════════════════════════════════════════════════════════════
echo "⚙️  Setting up environment..."

if [ ! -f ".env" ]; then
    echo "Creating .env file..."
    cat > .env << 'EOF'
# Azure OpenAI (Required)
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_KEY=your-key-here

# Model Deployments (update with your deployment names)
AZURE_DEPLOYMENT_REASONING=o3-mini-high
AZURE_DEPLOYMENT_FAST=gpt-5.4-mini

# Feature Flags
USE_UNIFIED_HANDLER=true
USE_INTENT_ROUTING=false

# Optional: For Azure migration later
# AZURE_SEARCH_ENDPOINT=
# AZURE_SEARCH_KEY=
# COSMOS_ENDPOINT=
# COSMOS_KEY=
EOF
    echo "📝 Created .env file. Please edit it with your Azure credentials."
else
    echo "📝 .env file exists. Make sure it has the required variables."
fi

echo ""
echo "Required environment variables:"
echo "  - AZURE_OPENAI_ENDPOINT"
echo "  - AZURE_OPENAI_KEY"
echo "  - AZURE_DEPLOYMENT_REASONING"
echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 4: Test Configuration
# ═══════════════════════════════════════════════════════════════════════════════
echo "🧪 Testing configuration..."

python3 << 'PYTHON'
import os
from dotenv import load_dotenv

load_dotenv()

required = [
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_KEY",
    "AZURE_DEPLOYMENT_REASONING"
]

missing = [v for v in required if not os.getenv(v)]

if missing:
    print(f"❌ Missing environment variables: {', '.join(missing)}")
    exit(1)
else:
    print("✅ All required variables set")
PYTHON

if [ $? -ne 0 ]; then
    echo ""
    echo "Please edit .env and add the required variables."
    exit 1
fi

echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 5: Server.py Modification Instructions
# ═══════════════════════════════════════════════════════════════════════════════
echo "🔧 Next Steps: Modify server.py"
echo ""
echo "Add these imports near the top:"
echo ""
echo "    from mastermind_v3 import init_mastermind, chat_endpoint, router as mastermind_router"
echo "    from voice_v3 import init_voice_handler, voice_router"
echo ""
echo "Add to startup event:"
echo ""
echo "    @app.on_event('startup')"
echo "    async def startup():"
echo "        init_mastermind(state.df)"
echo "        init_voice_handler(mastermind)"
echo ""
echo "Add routers:"
echo ""
echo "    app.include_router(mastermind_router, prefix='/api/v3')"
echo "    app.include_router(voice_router, prefix='/api/v3')"
echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 6: Test Script
# ═══════════════════════════════════════════════════════════════════════════════
echo "🧪 Creating test script..."

cat > test_v3.sh << 'EOF'
#!/bin/bash
# Test the new unified handler

echo "Testing Unified Handler V3"
echo "=========================="

# Start server in background
echo "Starting server..."
python server.py &
SERVER_PID=$!
sleep 5

# Test 1: Simple query
echo ""
echo "Test 1: HC9600 price"
curl -s -X POST http://localhost:8000/api/v3/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "HC9600 price", "session_id": "test-1"}' | jq '.response'

# Test 2: Andrew's example
echo ""
echo "Test 2: Data center HVAC"
curl -s -X POST http://localhost:8000/api/v3/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "I'\''m meeting with a data center operator tomorrow. They need HVAC filters.", "session_id": "test-2"}' | jq '.response'

# Kill server
kill $SERVER_PID

echo ""
echo "Tests complete!"
EOF

chmod +x test_v3.sh

echo "✅ Created test_v3.sh"
echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# DONE
# ═══════════════════════════════════════════════════════════════════════════════
echo "🎉 Quick Start Complete!"
echo "========================"
echo ""
echo "Next steps:"
echo "1. Edit .env with your Azure OpenAI credentials"
echo "2. Modify server.py (see instructions above)"
echo "3. Run: ./test_v3.sh"
echo "4. Deploy: git push origin main"
echo ""
echo "For full migration to Azure, see:"
echo "  - 3DAY_IMPLEMENTATION_GUIDE.md"
echo "  - azure-migration/"
echo ""

#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# Switch to New UI v3.0 - Automated Script
# Backs up old files, updates references to new files
# ═══════════════════════════════════════════════════════════════════════════════

set -e  # Exit on error

echo "🚀 Switching to Enpro Mastermind UI v3.0"
echo "========================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 1: Backup Old Files
# ═══════════════════════════════════════════════════════════════════════════════
echo "📦 Step 1: Backing up old UI files..."

backup_dir="static/backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$backup_dir"

# Backup old files
cp static/app.js "$backup_dir/app.js.bak" 2>/dev/null || echo "  No app.js to backup"
cp static/index.html "$backup_dir/index.html.bak" 2>/dev/null || echo "  No index.html to backup"
cp static/styles.css "$backup_dir/styles.css.bak" 2>/dev/null || echo "  No styles.css to backup"
cp static/chat.html "$backup_dir/chat.html.bak" 2>/dev/null || echo "  No chat.html to backup"

echo -e "${GREEN}✅${NC} Old files backed up to: $backup_dir"
echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 2: Update index.html to use new files
# ═══════════════════════════════════════════════════════════════════════════════
echo "🔧 Step 2: Updating index.html to use new UI files..."

cat > static/index.html << 'EOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <meta name="theme-color" content="#0078d4">
    <title>Enpro Filtration Mastermind</title>
    <link rel="stylesheet" href="styles_v3.css">
</head>
<body>
    <div id="app-container">
        <!-- Header with Logo and Context Pills -->
        <header id="header">
            <div class="logo">Enpro Mastermind</div>
            <div id="contextBar">
                <span class="context-placeholder">New conversation</span>
            </div>
        </header>
        
        <!-- Chat History -->
        <main id="chatHistory">
            <!-- Messages will be rendered here -->
        </main>
        
        <!-- Typing Indicator -->
        <div id="typingIndicator" style="display: none;">
            <div class="typing-dots">
                <span></span>
                <span></span>
                <span></span>
            </div>
            <span>Thinking...</span>
        </div>
        
        <!-- Input Area - Voice First -->
        <footer id="inputArea">
            <!-- Big Mic Button (Primary for mobile reps) -->
            <button id="micBtn" class="mic-large" aria-label="Hold to speak">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path>
                    <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
                    <line x1="12" y1="19" x2="12" y2="23"></line>
                    <line x1="8" y1="23" x2="16" y2="23"></line>
                </svg>
                <span>Hold to speak</span>
            </button>
            
            <!-- Text Input (Secondary) -->
            <div class="text-input-row">
                <input 
                    type="text" 
                    id="textInput" 
                    placeholder="Ask me anything... part numbers, applications, meetings"
                    autocomplete="off"
                    aria-label="Type your message"
                >
                <button id="sendBtn" aria-label="Send message">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <line x1="22" y1="2" x2="11" y2="13"></line>
                        <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
                    </svg>
                </button>
            </div>
        </footer>
    </div>
    
    <!-- Load the new app.js -->
    <script src="app_v3.js"></script>
</body>
</html>
EOF

echo -e "${GREEN}✅${NC} index.html updated to use new UI files"
echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 3: Verify new files exist
# ═══════════════════════════════════════════════════════════════════════════════
echo "🔍 Step 3: Verifying new UI files..."

missing=0

if [ ! -f "static/app_v3.js" ]; then
    echo -e "${RED}❌${NC} Missing: static/app_v3.js"
    missing=1
fi

if [ ! -f "static/styles_v3.css" ]; then
    echo -e "${RED}❌${NC} Missing: static/styles_v3.css"
    missing=1
fi

if [ ! -f "static/index_v3.html" ]; then
    echo -e "${YELLOW}⚠️${NC}  Note: static/index_v3.html exists (backup)"
fi

if [ $missing -eq 1 ]; then
    echo ""
    echo -e "${RED}Error: Some new UI files are missing!${NC}"
    echo "Make sure you have:"
    echo "  - static/app_v3.js"
    echo "  - static/styles_v3.css"
    exit 1
fi

echo -e "${GREEN}✅${NC} All new UI files present"
echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 4: Create toggle script for easy switching
# ═══════════════════════════════════════════════════════════════════════════════
echo "🔄 Step 4: Creating toggle script..."

cat > switch_ui_version.sh << 'EOF'
#!/bin/bash
# Toggle between old and new UI versions

echo "Enpro UI Version Switcher"
echo "========================="
echo ""
echo "1. Switch to NEW UI v3.0 (Andrew's review fixes)"
echo "2. Switch to OLD UI v2.x (legacy)"
echo "3. Show current version"
echo ""
read -p "Select option (1-3): " choice

case $choice in
    1)
        echo "Switching to NEW UI v3.0..."
        cp static/index.html static/index.html.tmp
        cat > static/index.html << 'HTMLEOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <meta name="theme-color" content="#0078d4">
    <title>Enpro Filtration Mastermind</title>
    <link rel="stylesheet" href="styles_v3.css">
</head>
<body>
    <div id="app-container">
        <header id="header">
            <div class="logo">Enpro Mastermind</div>
            <div id="contextBar">
                <span class="context-placeholder">New conversation</span>
            </div>
        </header>
        <main id="chatHistory"></main>
        <div id="typingIndicator" style="display: none;">
            <div class="typing-dots"><span></span><span></span><span></span></div>
            <span>Thinking...</span>
        </div>
        <footer id="inputArea">
            <button id="micBtn" class="mic-large" aria-label="Hold to speak">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path>
                    <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
                    <line x1="12" y1="19" x2="12" y2="23"></line>
                    <line x1="8" y1="23" x2="16" y2="23"></line>
                </svg>
                <span>Hold to speak</span>
            </button>
            <div class="text-input-row">
                <input type="text" id="textInput" placeholder="Ask me anything... part numbers, applications, meetings" autocomplete="off">
                <button id="sendBtn">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="22" y1="2" x2="11" y2="13"></line>
                        <polygon points="22,2 15,22 11,13 2,9 22,2"></polygon>
                    </svg>
                </button>
            </div>
        </footer>
    </div>
    <script src="app_v3.js"></script>
</body>
</html>
HTMLEOF
        echo "✅ Switched to NEW UI v3.0"
        echo "   - Natural conversation (no commands)"
        echo "   - Mobile-optimized"
        echo "   - Voice-first layout"
        echo "   - Max 3 products with reasoning"
        ;;
    2)
        echo "Switching to OLD UI v2.x..."
        if [ -f "static/backup_*/index.html.bak" ]; then
            latest_backup=$(ls -td static/backup_*/index.html.bak 2>/dev/null | head -1)
            cp "$latest_backup" static/index.html
            echo "✅ Restored old UI from backup"
        else
            echo "❌ No backup found! Cannot restore old UI."
            exit 1
        fi
        ;;
    3)
        if grep -q "app_v3.js" static/index.html 2>/dev/null; then
            echo "Current version: NEW UI v3.0"
        else
            echo "Current version: OLD UI v2.x"
        fi
        ;;
    *)
        echo "Invalid option"
        exit 1
        ;;
esac
EOF

chmod +x switch_ui_version.sh

echo -e "${GREEN}✅${NC} Created: switch_ui_version.sh"
echo "   Run ./switch_ui_version.sh anytime to toggle between old/new UI"
echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 5: Git commit
# ═══════════════════════════════════════════════════════════════════════════════
echo "📤 Step 5: Committing changes..."

git add static/index.html
if [ -d "$backup_dir" ]; then
    git add "$backup_dir"
fi
git add switch_ui_version.sh
git commit -m "Switch to new UI v3.0 - Andrew's review fixes

Changes:
- index.html now loads app_v3.js and styles_v3.css
- Old files backed up to: $backup_dir
- Added switch_ui_version.sh for easy toggling

New UI features:
- Natural conversation (no commands)
- Mobile-first layout (600px max)
- Voice-first input (big mic button)
- Context pills showing memory
- Max 3 products with reasoning"

echo -e "${GREEN}✅${NC} Changes committed to git"
echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════
echo "🎉 SUCCESS! New UI v3.0 is now active"
echo "======================================"
echo ""
echo "Files changed:"
echo "  - static/index.html → Now uses app_v3.js + styles_v3.css"
echo ""
echo "Backup location:"
echo "  - $backup_dir/"
echo ""
echo "Quick commands:"
echo "  ./switch_ui_version.sh    # Toggle between old/new UI"
echo "  git status                # See what changed"
echo "  git push                  # Deploy to Render"
echo ""
echo "What changed in the UI:"
echo "  ✅ No more 'lookup', 'pregame' commands"
echo "  ✅ No more '400 products found'"
echo "  ✅ Mobile-optimized (phones in parking lots)"
echo "  ✅ Voice-first (big mic button)"
echo "  ✅ Context pills (shows what system remembers)"
echo "  ✅ Cards with reasoning (not tables)"
echo ""
echo "To deploy:"
echo "  git push origin v3.0-modular-architecture"
echo ""

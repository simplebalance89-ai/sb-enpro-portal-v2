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

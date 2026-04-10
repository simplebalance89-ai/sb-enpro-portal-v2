# ═══════════════════════════════════════════════════════════════════════════════
# Switch to New UI v3.0 - PowerShell Script (Windows)
# Run this in PowerShell to activate the new UI
# ═══════════════════════════════════════════════════════════════════════════════

Write-Host "🚀 Switching to Enpro Mastermind UI v3.0" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Get current directory
$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectDir

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 1: Backup Old Files
# ═══════════════════════════════════════════════════════════════════════════════
Write-Host "📦 Step 1: Backing up old UI files..." -ForegroundColor Yellow

$backupDir = "static/backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
New-Item -ItemType Directory -Force -Path $backupDir | Out-Null

# Backup old files
if (Test-Path "static/app.js") {
    Copy-Item "static/app.js" "$backupDir/app.js.bak"
    Write-Host "  ✅ Backed up app.js" -ForegroundColor Green
}
if (Test-Path "static/index.html") {
    Copy-Item "static/index.html" "$backupDir/index.html.bak"
    Write-Host "  ✅ Backed up index.html" -ForegroundColor Green
}
if (Test-Path "static/styles.css") {
    Copy-Item "static/styles.css" "$backupDir/styles.css.bak"
    Write-Host "  ✅ Backed up styles.css" -ForegroundColor Green
}
if (Test-Path "static/chat.html") {
    Copy-Item "static/chat.html" "$backupDir/chat.html.bak"
    Write-Host "  ✅ Backed up chat.html" -ForegroundColor Green
}

Write-Host "  Backup location: $backupDir" -ForegroundColor Gray
Write-Host ""

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 2: Update index.html to use new files
# ═══════════════════════════════════════════════════════════════════════════════
Write-Host "🔧 Step 2: Updating index.html to use new UI files..." -ForegroundColor Yellow

$htmlContent = @"
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
"@

$htmlContent | Out-File -FilePath "static/index.html" -Encoding UTF8 -Force

Write-Host "  ✅ index.html updated to use app_v3.js + styles_v3.css" -ForegroundColor Green
Write-Host ""

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 3: Verify new files exist
# ═══════════════════════════════════════════════════════════════════════════════
Write-Host "🔍 Step 3: Verifying new UI files..." -ForegroundColor Yellow

$missing = $false

if (-not (Test-Path "static/app_v3.js")) {
    Write-Host "  ❌ Missing: static/app_v3.js" -ForegroundColor Red
    $missing = $true
}
else {
    Write-Host "  ✅ Found: static/app_v3.js" -ForegroundColor Green
}

if (-not (Test-Path "static/styles_v3.css")) {
    Write-Host "  ❌ Missing: static/styles_v3.css" -ForegroundColor Red
    $missing = $true
}
else {
    Write-Host "  ✅ Found: static/styles_v3.css" -ForegroundColor Green
}

if ($missing) {
    Write-Host ""
    Write-Host "❌ Error: Some new UI files are missing!" -ForegroundColor Red
    Write-Host "Make sure you have:" -ForegroundColor Yellow
    Write-Host "  - static/app_v3.js"
    Write-Host "  - static/styles_v3.css"
    exit 1
}

Write-Host ""

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 4: Create toggle script
# ═══════════════════════════════════════════════════════════════════════════════
Write-Host "🔄 Step 4: Creating toggle script..." -ForegroundColor Yellow

$toggleScript = @'
# Toggle between old and new UI versions
param(
    [Parameter()]
    [ValidateSet("new", "old", "status")]
    [string]$Version = "status"
)

Write-Host "Enpro UI Version Switcher" -ForegroundColor Cyan
Write-Host "=========================" -ForegroundColor Cyan
Write-Host ""

switch ($Version) {
    "new" {
        Write-Host "Switching to NEW UI v3.0..." -ForegroundColor Green
        
        $htmlContent = @"
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Enpro Filtration Mastermind</title>
    <link rel="stylesheet" href="styles_v3.css">
</head>
<body>
    <div id="app-container">
        <header id="header">
            <div class="logo">Enpro Mastermind</div>
            <div id="contextBar"><span class="context-placeholder">New conversation</span></div>
        </header>
        <main id="chatHistory"></main>
        <div id="typingIndicator" style="display: none;">
            <div class="typing-dots"><span></span><span></span><span></span></div>
            <span>Thinking...</span>
        </div>
        <footer id="inputArea">
            <button id="micBtn" class="mic-large">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
                    <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
                    <line x1="12" y1="19" x2="12" y2="23"/>
                    <line x1="8" y1="23" x2="16" y2="23"/>
                </svg>
                <span>Hold to speak</span>
            </button>
            <div class="text-input-row">
                <input type="text" id="textInput" placeholder="Ask me anything... part numbers, applications, meetings">
                <button id="sendBtn"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22,2 15,22 11,13 2,9 22,2"/></svg></button>
            </div>
        </footer>
    </div>
    <script src="app_v3.js"></script>
</body>
</html>
"@
        
        $htmlContent | Out-File -FilePath "static/index.html" -Encoding UTF8 -Force
        Write-Host "✅ Switched to NEW UI v3.0" -ForegroundColor Green
        Write-Host "   - Natural conversation (no commands)" -ForegroundColor Gray
        Write-Host "   - Mobile-optimized" -ForegroundColor Gray
        Write-Host "   - Voice-first layout" -ForegroundColor Gray
        Write-Host "   - Max 3 products with reasoning" -ForegroundColor Gray
    }
    
    "old" {
        Write-Host "Switching to OLD UI v2.x..." -ForegroundColor Yellow
        $backups = Get-ChildItem -Directory -Path "static" -Filter "backup_*" | Sort-Object Name -Descending
        if ($backups.Count -gt 0) {
            $latest = $backups[0]
            if (Test-Path "$latest/index.html.bak") {
                Copy-Item "$latest/index.html.bak" "static/index.html" -Force
                Write-Host "✅ Restored old UI from $latest" -ForegroundColor Green
            }
            else {
                Write-Host "❌ No backup found in $latest" -ForegroundColor Red
            }
        }
        else {
            Write-Host "❌ No backup directory found!" -ForegroundColor Red
        }
    }
    
    "status" {
        $content = Get-Content "static/index.html" -Raw
        if ($content -match "app_v3\.js") {
            Write-Host "Current version: NEW UI v3.0 ✅" -ForegroundColor Green
        }
        else {
            Write-Host "Current version: OLD UI v2.x" -ForegroundColor Yellow
        }
    }
}
'@

$toggleScript | Out-File -FilePath "switch_ui_version.ps1" -Encoding UTF8 -Force

Write-Host "  ✅ Created: switch_ui_version.ps1" -ForegroundColor Green
Write-Host "     Run .\switch_ui_version.ps1 -Version new/old/status" -ForegroundColor Gray
Write-Host ""

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 5: Git commit
# ═══════════════════════════════════════════════════════════════════════════════
Write-Host "📤 Step 5: Committing changes to git..." -ForegroundColor Yellow

git add static/index.html
git add $backupDir
git add switch_ui_version.ps1

git commit -m "Switch to new UI v3.0 - Andrew's review fixes

Changes:
- index.html now loads app_v3.js and styles_v3.css
- Old files backed up to: $backupDir
- Added switch_ui_version.ps1 for easy toggling

New UI features:
- Natural conversation (no commands)
- Mobile-first layout (600px max)
- Voice-first input (big mic button)
- Context pills showing memory
- Max 3 products with reasoning"

Write-Host "  ✅ Changes committed" -ForegroundColor Green
Write-Host ""

# ═══════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════
Write-Host "🎉 SUCCESS! New UI v3.0 is now active" -ForegroundColor Green
Write-Host "======================================" -ForegroundColor Green
Write-Host ""
Write-Host "Files changed:" -ForegroundColor White
Write-Host "  - static/index.html → Now uses app_v3.js + styles_v3.css" -ForegroundColor Gray
Write-Host ""
Write-Host "Backup location:" -ForegroundColor White
Write-Host "  - $backupDir" -ForegroundColor Gray
Write-Host ""
Write-Host "Quick commands:" -ForegroundColor White
Write-Host "  .\switch_ui_version.ps1 -Version new    # Switch to new UI" -ForegroundColor Cyan
Write-Host "  .\switch_ui_version.ps1 -Version old    # Switch to old UI" -ForegroundColor Cyan
Write-Host "  .\switch_ui_version.ps1 -Version status # Check current" -ForegroundColor Cyan
Write-Host "  git push                                # Deploy to Render" -ForegroundColor Cyan
Write-Host ""
Write-Host "What changed in the UI:" -ForegroundColor White
Write-Host "  ✅ No more 'lookup', 'pregame' commands" -ForegroundColor Green
Write-Host "  ✅ No more '400 products found'" -ForegroundColor Green
Write-Host "  ✅ Mobile-optimized (phones in parking lots)" -ForegroundColor Green
Write-Host "  ✅ Voice-first (big mic button)" -ForegroundColor Green
Write-Host "  ✅ Context pills (shows what system remembers)" -ForegroundColor Green
Write-Host "  ✅ Cards with reasoning (not tables)" -ForegroundColor Green
Write-Host ""
Write-Host "To deploy:" -ForegroundColor Yellow
Write-Host "  git push origin v3.0-modular-architecture" -ForegroundColor Cyan
Write-Host ""

Read-Host "Press Enter to exit"

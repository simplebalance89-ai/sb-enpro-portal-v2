// ==UserScript==
// @name         EnPro FM Portal - Test Recorder
// @namespace    http://tampermonkey.net/
// @version      1.0
// @description  Capture screenshots and log responses for testing
// @match        https://enpro-fm-portal*.onrender.com/*
// @grant        none
// ==/UserScript==

(function() {
    'use strict';

    let screenshotCount = 0;

    // Capture screenshot using html2canvas approach
    function captureScreenshot(name) {
        screenshotCount++;
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        const html = document.documentElement;

        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;

        // Simple capture (full page would need html2canvas library)
        html2canvas(document.body).then(canvas => {
            const link = document.createElement('a');
            link.download = `enpro-${screenshotCount}-${name}.png`;
            link.href = canvas.toDataURL();
            link.click();
            console.log(`📸 Screenshot saved: ${name}`);
        }).catch(() => {
            console.log('📸 Screenshot failed - install html2canvas extension');
        });
    }

    // Watch for new messages
    const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
            if (mutation.type === 'childList') {
                // Check if compare cards appeared
                const compareCards = document.querySelectorAll('[style*="border:2px solid"]');
                if (compareCards.length >= 2) {
                    console.log('✅ Compare cards detected');
                    setTimeout(() => captureScreenshot('compare'), 500);
                }

                // Check for pregame headline
                const headlines = document.querySelectorAll('.msg.bot');
                headlines.forEach(h => {
                    if (h.textContent.includes('care about') || h.textContent.includes('meeting')) {
                        console.log('✅ Pregame response detected');
                    }
                });
            }
        });
    });

    // Start watching chat area
    setTimeout(() => {
        const chatArea = document.querySelector('.chat-area');
        if (chatArea) {
            observer.observe(chatArea, { childList: true, subtree: true });
            console.log('🔴 EnPro Test Recorder ACTIVE');
        }
    }, 2000);

    // Add record button
    const btn = document.createElement('button');
    btn.textContent = '📸 Capture';
    btn.style.cssText = 'position:fixed;bottom:80px;right:20px;z-index:9999;padding:10px 20px;background:#003366;color:white;border:none;border-radius:8px;cursor:pointer;font-weight:bold;';
    btn.onclick = () => captureScreenshot('manual');
    document.body.appendChild(btn);

})();

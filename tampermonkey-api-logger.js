// ==UserScript==
// @name         EnPro API Logger
// @namespace    http://tampermonkey.net/
// @version      1.0
// @description  Log all API calls to browser console
// @match        https://enpro-fm-portal*.onrender.com/*
// @grant        none
// ==/UserScript==

(function() {
    'use strict';

    console.log('🔴 EnPro API Logger ACTIVE');

    // Hook into native fetch
    const originalFetch = window.fetch;
    window.fetch = async function(...args) {
        const [url, options] = args;
        const method = options?.method || 'GET';
        const body = options?.body;

        console.group(`📡 ${method} ${url}`);
        if (body) {
            try {
                console.log('Request:', JSON.parse(body));
            } catch {
                console.log('Request:', body);
            }
        }

        const response = await originalFetch.apply(this, args);

        // Clone response so we can read it
        const clone = response.clone();
        const contentType = clone.headers.get('content-type') || '';

        if (contentType.includes('application/json')) {
            const data = await clone.json();
            console.log('Response:', data);
        } else if (contentType.includes('text/event-stream')) {
            console.log('Response: [SSE Streaming]');
        } else {
            const text = await clone.text();
            console.log('Response:', text.substring(0, 500));
        }

        console.groupEnd();
        return response;
    };

    // Highlight important UI elements
    const style = document.createElement('style');
    style.textContent = `
        .highlight-compare { animation: flash 1s; }
        .highlight-pregame { animation: flash 1s; }
        @keyframes flash {
            0%, 100% { box-shadow: none; }
            50% { box-shadow: 0 0 20px #00ff00; }
        }
    `;
    document.head.appendChild(style);

    // Watch for compare cards
    const observer = new MutationObserver(() => {
        const cards = document.querySelectorAll('[style*="flex:1"]');
        if (cards.length >= 2) {
            cards.forEach(c => c.classList.add('highlight-compare'));
            console.log('✅ COMPARE CARDS DETECTED');
        }
    });

    setTimeout(() => {
        const chat = document.querySelector('.chat-area');
        if (chat) observer.observe(chat, { childList: true, subtree: true });
    }, 2000);

})();
